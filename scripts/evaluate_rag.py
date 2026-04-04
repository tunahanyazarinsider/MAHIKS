#!/usr/bin/env python3
"""
RAG Evaluation Script for MAHIKS-TR
Uses LLM-as-a-judge (Gemini) to evaluate the RAG pipeline on:
  - Faithfulness:       Is the answer grounded in retrieved context?
  - Answer Relevancy:   Does the answer address the question?
  - Context Relevancy:  Did retrieval fetch relevant chunks?
  - Correctness:        How correct vs ground truth? (only if provided)

Usage:
  docker compose run --rm backend python -m scripts.evaluate_rag
  docker compose run --rm backend python -m scripts.evaluate_rag --questions data/eval_questions.json
  docker compose run --rm backend python -m scripts.evaluate_rag --output reports/eval_result.json
"""
import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from database.mysql_handler import MySQLHandler
from database.chroma_handler import ChromaDBHandler
from database.neo4j_handler import Neo4jHandler
from database.bm25_handler import BM25Handler
from agents.retrieval_agent import RetrievalAgent
from agents.generation_agent_ollama import GenerationAgentOllama
from agents.orchestrator_agent import QueryOrchestratorAgent
from config import Config

try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Gemini judge
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator for a Turkish health insurance Q&A system (RAG pipeline).
Evaluate the following response and score each metric from 1 to 5.

QUESTION:
{question}

RETRIEVED CONTEXT (chunks shown to the model):
{context}

GENERATED ANSWER:
{answer}
{ground_truth_block}

SCORING CRITERIA:

1. FAITHFULNESS (1-5)
   Does the answer rely only on information present in the retrieved context?
   1 = Answer contains significant fabricated information not in context
   3 = Partially grounded, some unsupported claims
   5 = Fully grounded, every claim traceable to context

2. ANSWER_RELEVANCY (1-5)
   Does the answer directly address the question?
   1 = Completely off-topic
   3 = Partially answers the question
   5 = Fully and precisely answers the question

3. CONTEXT_RELEVANCY (1-5)
   Does the retrieved context contain the information needed to answer the question?
   1 = Retrieved chunks are irrelevant to the question
   3 = Context is partially relevant
   5 = Context is highly relevant and sufficient
{correctness_criteria}

Respond ONLY with a valid JSON object, no explanation outside it:
{{
  "faithfulness": <1-5>,
  "answer_relevancy": <1-5>,
  "context_relevancy": <1-5>{correctness_field},
  "faithfulness_reason": "<one sentence>",
  "answer_relevancy_reason": "<one sentence>",
  "context_relevancy_reason": "<one sentence>"{correctness_reason_field}
}}"""

CORRECTNESS_CRITERIA = """
4. CORRECTNESS (1-5)
   Compared to the ground truth answer, how correct is the generated answer?
   1 = Factually wrong or contradicts ground truth
   3 = Partially correct
   5 = Fully correct and consistent with ground truth"""

GROUND_TRUTH_BLOCK = """
GROUND TRUTH ANSWER:
{ground_truth}"""


def build_judge_prompt(question: str, context: str, answer: str,
                       ground_truth: str = None) -> str:
    gt_block = ""
    correctness_criteria = ""
    correctness_field = ""
    correctness_reason_field = ""

    if ground_truth:
        gt_block = GROUND_TRUTH_BLOCK.format(ground_truth=ground_truth)
        correctness_criteria = CORRECTNESS_CRITERIA
        correctness_field = ',\n  "correctness": <1-5>'
        correctness_reason_field = ',\n  "correctness_reason": "<one sentence>"'

    return JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        context=context,
        answer=answer,
        ground_truth_block=gt_block,
        correctness_criteria=correctness_criteria,
        correctness_field=correctness_field,
        correctness_reason_field=correctness_reason_field,
    )


def format_context_for_judge(rag_response: dict, max_chunks: int = 5) -> str:
    chunks = rag_response.get('sources', {}).get('documents', [])[:max_chunks]
    if not chunks:
        return "(no context retrieved)"
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Chunk {i} - {chunk.get('name', 'Unknown')}]\n{chunk.get('text', '')}"
        )
    return "\n\n".join(parts)


def call_gemini_judge(client, model: str, prompt: str) -> dict:
    response = client.models.generate_content(model=model, contents=prompt)
    raw = response.text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Pipeline initialisation (mirrors vectorize_only.py)
# ---------------------------------------------------------------------------

def init_pipeline():
    print("Initializing databases...")
    mysql = MySQLHandler(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE
    )
    mysql.create_tables()

    chroma = ChromaDBHandler(
        persist_directory=Config.CHROMA_PERSIST_DIR,
        collection_name=Config.CHROMA_COLLECTION_NAME,
        embedding_model_name=Config.EMBEDDING_MODEL
    )

    neo4j = Neo4jHandler(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD
    )

    bm25 = BM25Handler(
        persist_directory=Config.BM25_PERSIST_DIR,
        k1=Config.BM25_K1,
        b=Config.BM25_B
    )

    retrieval = RetrievalAgent(chroma, neo4j, mysql, bm25)
    generation = GenerationAgentOllama(
        base_url=Config.OLLAMA_BASE_URL,
        model=Config.OLLAMA_MODEL
    )
    orchestrator = QueryOrchestratorAgent(retrieval, generation, mysql)

    return orchestrator, mysql


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate MAHIKS-TR RAG pipeline")
    parser.add_argument(
        "--questions",
        default="data/eval_questions.json",
        help="Path to eval questions JSON (default: data/eval_questions.json)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON report (default: reports/eval_<timestamp>.json)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MAHIKS-TR: RAG Evaluation (LLM-as-a-Judge)")
    print("=" * 70)
    print(f"Start:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Questions: {args.questions}")
    judge_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"Judge:     {judge_model}")
    print("=" * 70 + "\n")

    # Validate config
    Config.validate()

    if not GEMINI_AVAILABLE:
        print("✗ google-genai not installed. Run: pip install google-genai")
        sys.exit(1)

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("✗ GOOGLE_API_KEY not set.")
        sys.exit(1)

    # Load questions
    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"✗ Questions file not found: {questions_path}")
        sys.exit(1)

    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions from {questions_path}\n")

    # Init Gemini judge
    gemini_client = google_genai.Client(api_key=google_api_key)

    # Init RAG pipeline
    orchestrator, mysql = init_pipeline()

    # Prepare output path
    if args.output:
        output_path = Path(args.output)
    else:
        Path("reports").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"reports/eval_{timestamp}.json")

    # Evaluate
    results = []
    metric_totals = {"faithfulness": 0, "answer_relevancy": 0, "context_relevancy": 0}
    correctness_scores = []

    for idx, item in enumerate(questions, 1):
        question = item["question"]
        ground_truth = item.get("ground_truth")
        q_id = item.get("id", idx)

        print(f"[{idx}/{len(questions)}] Q{q_id}: {question}")

        # Step 1: Run RAG pipeline
        try:
            rag_response = orchestrator.process_query(question, include_citations=False)
            answer = rag_response.get("answer", "")
            context_str = format_context_for_judge(rag_response)
            chunks_retrieved = rag_response.get("metadata", {}).get("chunks_retrieved", 0)
            response_time_ms = rag_response.get("metadata", {}).get("response_time_ms", 0)
        except Exception as e:
            print(f"  ✗ RAG pipeline error: {e}\n")
            results.append({
                "id": q_id,
                "question": question,
                "error": str(e),
                "scores": None
            })
            continue

        print(f"  Retrieved {chunks_retrieved} chunks, answered in {response_time_ms}ms")

        # Step 2: Judge with Gemini
        try:
            prompt = build_judge_prompt(question, context_str, answer, ground_truth)
            scores = call_gemini_judge(gemini_client, judge_model, prompt)
        except Exception as e:
            print(f"  ✗ Judge error: {e}\n")
            results.append({
                "id": q_id,
                "question": question,
                "answer": answer,
                "error_judge": str(e),
                "scores": None
            })
            continue

        # Accumulate metrics
        for metric in ("faithfulness", "answer_relevancy", "context_relevancy"):
            metric_totals[metric] += scores.get(metric, 0)
        if "correctness" in scores:
            correctness_scores.append(scores["correctness"])

        print(f"  Faithfulness:      {scores.get('faithfulness')}/5  — {scores.get('faithfulness_reason', '')}")
        print(f"  Answer Relevancy:  {scores.get('answer_relevancy')}/5  — {scores.get('answer_relevancy_reason', '')}")
        print(f"  Context Relevancy: {scores.get('context_relevancy')}/5  — {scores.get('context_relevancy_reason', '')}")
        if "correctness" in scores:
            print(f"  Correctness:       {scores.get('correctness')}/5  — {scores.get('correctness_reason', '')}")
        print()

        results.append({
            "id": q_id,
            "question": question,
            "ground_truth": ground_truth,
            "answer": answer,
            "chunks_retrieved": chunks_retrieved,
            "response_time_ms": response_time_ms,
            "scores": scores
        })

    # Summary
    n = len([r for r in results if r.get("scores") is not None])
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    if n > 0:
        avg_faith = metric_totals["faithfulness"] / n
        avg_rel = metric_totals["answer_relevancy"] / n
        avg_ctx = metric_totals["context_relevancy"] / n
        print(f"Questions evaluated:  {n}/{len(questions)}")
        print(f"Avg Faithfulness:     {avg_faith:.2f}/5")
        print(f"Avg Answer Relevancy: {avg_rel:.2f}/5")
        print(f"Avg Context Relevancy:{avg_ctx:.2f}/5")
        if correctness_scores:
            print(f"Avg Correctness:      {sum(correctness_scores)/len(correctness_scores):.2f}/5")

        summary = {
            "evaluated": n,
            "total": len(questions),
            "avg_faithfulness": round(avg_faith, 3),
            "avg_answer_relevancy": round(avg_rel, 3),
            "avg_context_relevancy": round(avg_ctx, 3),
        }
        if correctness_scores:
            summary["avg_correctness"] = round(sum(correctness_scores) / len(correctness_scores), 3)
    else:
        print("No questions were successfully evaluated.")
        summary = {"evaluated": 0, "total": len(questions)}

    print("=" * 70)

    # Write report
    report = {
        "timestamp": datetime.now().isoformat(),
        "judge_model": judge_model,
        "questions_file": str(questions_path),
        "summary": summary,
        "results": results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Report saved to: {output_path}")
    mysql.close()


if __name__ == "__main__":
    main()
