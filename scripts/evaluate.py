#!/usr/bin/env python3
"""
MAHIKS-TR: Unified Evaluation Script

Evaluates both retrieval quality (IR metrics) and generation quality
(LLM-as-a-judge) using a local Ollama model — no external API required.

RETRIEVAL METRICS  (3 pipeline stages)
  Stage 1 — Vector-only (BGE-M3 bi-encoder)
  Stage 2 — Hybrid: Vector + BM25 fused via RRF
  Stage 3 — Full pipeline: Hybrid + cross-encoder sub-chunk reranking
  Metrics: Hit@k (k=1,3,5,10), MRR, MAP, nDCG@k (k=5,10)

GENERATION METRICS  (LLM-as-a-judge via Ollama)
  - Faithfulness      — Is the answer grounded in retrieved context?
  - Answer Relevance  — Does the answer address the question?
  - Context Precision — Of retrieved chunks, how many were actually useful?
  - Context Recall    — Were all facts needed to answer actually retrieved? (when ground_truth present)

Requires eval_questions.json with source_chunk_id fields.

Usage:
  docker compose run --rm backend python -m scripts.evaluate
  docker compose run --rm backend python -m scripts.evaluate --output data/eval_report.json
  docker compose run --rm backend python -m scripts.evaluate --judge-model qwen2.5:14b
  docker compose run --rm backend python -m scripts.evaluate --top-k 10 --questions data/eval_questions.json
"""
import sys
import json
import math
import re
import time
import argparse
import requests
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


# ---------------------------------------------------------------------------
# IR Metric computations
# ---------------------------------------------------------------------------

def hit_at_k(ranked_ids: list, relevant_id: int, k: int) -> int:
    return 1 if relevant_id in ranked_ids[:k] else 0


def reciprocal_rank(ranked_ids: list, relevant_id: int) -> float:
    try:
        return 1.0 / (ranked_ids.index(relevant_id) + 1)
    except ValueError:
        return 0.0


def average_precision(ranked_ids: list, relevant_id: int) -> float:
    """AP for a single relevant document = Precision@rank if found, else 0."""
    try:
        rank = ranked_ids.index(relevant_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def ndcg_at_k(ranked_ids: list, relevant_id: int, k: int) -> float:
    """nDCG@k for a single binary-relevant document. IDCG@k = 1.0 (ideal: rank 1)."""
    try:
        rank = ranked_ids.index(relevant_id) + 1
        if rank > k:
            return 0.0
        return 1.0 / math.log2(rank + 1)
    except ValueError:
        return 0.0


def compute_retrieval_metrics(ranked_ids: list, relevant_id: int) -> dict:
    return {
        "hit@1":   hit_at_k(ranked_ids, relevant_id, 1),
        "hit@3":   hit_at_k(ranked_ids, relevant_id, 3),
        "hit@5":   hit_at_k(ranked_ids, relevant_id, 5),
        "hit@10":  hit_at_k(ranked_ids, relevant_id, 10),
        "mrr":     reciprocal_rank(ranked_ids, relevant_id),
        "map":     average_precision(ranked_ids, relevant_id),
        "ndcg@5":  ndcg_at_k(ranked_ids, relevant_id, 5),
        "ndcg@10": ndcg_at_k(ranked_ids, relevant_id, 10),
    }


def find_rank(ranked_ids: list, relevant_id: int) -> int:
    return (ranked_ids.index(relevant_id) + 1) if relevant_id in ranked_ids else -1


def average_metrics(metric_list: list) -> dict:
    if not metric_list:
        return {}
    keys = metric_list[0].keys()
    return {k: round(sum(m[k] for m in metric_list) / len(metric_list), 4) for k in keys}


# ---------------------------------------------------------------------------
# Retrieval stage helpers
# ---------------------------------------------------------------------------

def vector_ranked_ids(retrieval_agent, query: str, top_k: int) -> list:
    results = retrieval_agent.vector_search(query, top_k=top_k)
    seen, ranked = set(), []
    for chunk in results:
        cid = chunk.get('id')
        if cid and cid not in seen:
            seen.add(cid)
            ranked.append(cid)
    return ranked


def hybrid_ranked_ids(retrieval_agent, query: str, top_k: int) -> list:
    vec = retrieval_agent.vector_search(query, top_k=top_k)
    bm25 = retrieval_agent.bm25_search(query, top_k=top_k) if retrieval_agent.bm25 else []
    fused = retrieval_agent.fuse_results(vec, bm25) if bm25 else vec
    seen, ranked = set(), []
    for chunk in fused:
        cid = chunk.get('id')
        if cid and cid not in seen:
            seen.add(cid)
            ranked.append(cid)
    return ranked


def full_pipeline_ranked_ids(retrieval_agent, query: str, top_k: int) -> list:
    context = retrieval_agent.hybrid_retrieve(query, vector_top_k=top_k)
    sub_chunks = context.get('vector_context', [])
    seen, ranked = set(), []
    for sc in sub_chunks:
        cid = sc.get('parent_chunk_id') or sc.get('id')
        if cid and cid not in seen:
            seen.add(cid)
            ranked.append(cid)
    return ranked


# ---------------------------------------------------------------------------
# LLM-as-a-judge (local Ollama)
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are evaluating a Turkish health insurance Q&A system. Score the response on each metric from 1 to 5.

QUESTION:
{question}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}
{ground_truth_section}
SCORING CRITERIA:
1. FAITHFULNESS (1-5): Is every claim in the answer supported by the retrieved context?
   1=significant fabrication, 3=partially grounded, 5=fully grounded in context

2. ANSWER_RELEVANCE (1-5): Does the answer directly address the question?
   1=off-topic, 3=partially answers, 5=fully and precisely answers

3. CONTEXT_PRECISION (1-5): Of the retrieved chunks, how many were actually useful for the answer?
   1=all chunks irrelevant, 3=some chunks useful, 5=all chunks directly useful
{correctness_section}
Respond with ONLY a valid JSON object — no explanation, no markdown:
{json_template}"""

CONTEXT_RECALL_CRITERIA = """4. CONTEXT_RECALL (1-5): What fraction of the facts in the ground truth answer are supported by the retrieved context?
   1=almost none of the ground truth is in context, 3=about half, 5=all ground truth facts are in context"""

JSON_TEMPLATE_BASE = """{
  "faithfulness": <1-5>,
  "answer_relevance": <1-5>,
  "context_precision": <1-5>,
  "faithfulness_reason": "<one sentence>",
  "answer_relevance_reason": "<one sentence>",
  "context_precision_reason": "<one sentence>"
}"""

JSON_TEMPLATE_WITH_GROUND_TRUTH = """{
  "faithfulness": <1-5>,
  "answer_relevance": <1-5>,
  "context_precision": <1-5>,
  "context_recall": <1-5>,
  "faithfulness_reason": "<one sentence>",
  "answer_relevance_reason": "<one sentence>",
  "context_precision_reason": "<one sentence>",
  "context_recall_reason": "<one sentence>"
}"""


def build_judge_prompt(question: str, context: str, answer: str,
                       ground_truth: str = None) -> str:
    if ground_truth:
        gt_section = f"\nGROUND TRUTH ANSWER:\n{ground_truth}\n"
        correctness_section = CONTEXT_RECALL_CRITERIA + "\n"
        json_template = JSON_TEMPLATE_WITH_GROUND_TRUTH
    else:
        gt_section = ""
        correctness_section = ""
        json_template = JSON_TEMPLATE_BASE

    return JUDGE_PROMPT.format(
        question=question,
        context=context,
        answer=answer,
        ground_truth_section=gt_section,
        correctness_section=correctness_section,
        json_template=json_template,
    )


def format_context(rag_response: dict, max_chunks: int = 5) -> str:
    chunks = rag_response.get('sources', {}).get('documents', [])[:max_chunks]
    if not chunks:
        return "(no context retrieved)"
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[Chunk {i} — {chunk.get('name', 'Unknown')}]\n{chunk.get('text', '')}")
    return "\n\n".join(parts)


def parse_judge_response(raw: str) -> dict:
    """Extract JSON from Ollama response, tolerating markdown fences and extra text."""
    raw = raw.strip()
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Find the first {...} block in the response
    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON found in judge response: {raw[:300]}")


def call_local_judge(ollama_base_url: str, model: str, prompt: str,
                     retries: int = 2) -> dict:
    """Call Ollama as judge with retry on JSON parse failure."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                f"{ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=180,
            )
            if response.status_code != 200:
                raise Exception(f"Ollama returned HTTP {response.status_code}")
            content = response.json().get('message', {}).get('content', '')
            return parse_judge_response(content)
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(2)
    raise last_error


# ---------------------------------------------------------------------------
# Pipeline init
# ---------------------------------------------------------------------------

def init_pipeline(judge_model: str, ollama_base_url: str):
    print("Initializing databases and agents...")
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
    generation = GenerationAgentOllama(base_url=ollama_base_url, model=Config.OLLAMA_MODEL)
    orchestrator = QueryOrchestratorAgent(retrieval, generation, mysql)

    return retrieval, orchestrator, mysql


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MAHIKS-TR Unified Evaluation")
    parser.add_argument("--questions", default="data/eval_questions.json",
                        help="Path to eval questions JSON (default: data/eval_questions.json)")
    parser.add_argument("--output", default=None,
                        help="Output report path (default: data/eval_report_<timestamp>.json)")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Chunks to retrieve per query (default: 10)")
    parser.add_argument("--judge-model", default=None,
                        help="Ollama model to use as judge (default: OLLAMA_MODEL from config)")
    parser.add_argument("--ollama-url", default=None,
                        help="Ollama base URL (default: OLLAMA_BASE_URL from config)")
    args = parser.parse_args()

    Config.validate()

    ollama_url = args.ollama_url or Config.OLLAMA_BASE_URL
    judge_model = args.judge_model or Config.OLLAMA_MODEL

    print("\n" + "=" * 70)
    print("MAHIKS-TR: Unified Evaluation (Retrieval + Generation)")
    print("=" * 70)
    print(f"Date:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Questions:   {args.questions}")
    print(f"Top-K:       {args.top_k}")
    print(f"Judge model: {judge_model} (local Ollama)")
    print(f"Ollama URL:  {ollama_url}")
    print("=" * 70 + "\n")

    # Load questions
    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"✗ Questions file not found: {questions_path}")
        sys.exit(1)

    with open(questions_path, "r", encoding="utf-8") as f:
        all_questions = json.load(f)

    print(f"Loaded {len(all_questions)} questions\n")

    # Init pipeline
    retrieval_agent, orchestrator, mysql = init_pipeline(judge_model, ollama_url)

    # Per-question results
    results = []
    stage1_metrics, stage2_metrics, stage3_metrics = [], [], []
    gen_metrics = []

    for idx, item in enumerate(all_questions, 1):
        question   = item["question"]
        ground_truth = item.get("ground_truth")
        relevant_id  = int(item["source_chunk_id"]) if item.get("source_chunk_id") else None
        q_id = item.get("id", idx)

        print(f"[{idx}/{len(all_questions)}] Q{q_id}: {question[:70]}")

        result_entry = {
            "id": q_id,
            "question": question,
            "ground_truth": ground_truth,
            "source_chunk_id": relevant_id,
        }

        # ── Retrieval evaluation ──────────────────────────────────────────
        if relevant_id is not None:
            try:
                s1_ids = vector_ranked_ids(retrieval_agent, question, args.top_k)
                s1 = compute_retrieval_metrics(s1_ids, relevant_id)

                s2_ids = hybrid_ranked_ids(retrieval_agent, question, args.top_k)
                s2 = compute_retrieval_metrics(s2_ids, relevant_id)

                s3_ids = full_pipeline_ranked_ids(retrieval_agent, question, args.top_k)
                s3 = compute_retrieval_metrics(s3_ids, relevant_id)

                stage1_metrics.append(s1)
                stage2_metrics.append(s2)
                stage3_metrics.append(s3)

                rank_str = lambda r: f"rank {r}" if r > 0 else "NOT FOUND"
                print(f"  [Retrieval]")
                print(f"    Vector only:   Hit@5={s1['hit@5']} MRR={s1['mrr']:.3f} nDCG@5={s1['ndcg@5']:.3f}  ({rank_str(find_rank(s1_ids, relevant_id))})")
                print(f"    Hybrid (RRF):  Hit@5={s2['hit@5']} MRR={s2['mrr']:.3f} nDCG@5={s2['ndcg@5']:.3f}  ({rank_str(find_rank(s2_ids, relevant_id))})")
                print(f"    Full pipeline: Hit@5={s3['hit@5']} MRR={s3['mrr']:.3f} nDCG@5={s3['ndcg@5']:.3f}  ({rank_str(find_rank(s3_ids, relevant_id))})")

                result_entry["retrieval"] = {
                    "stage1_vector": s1,
                    "stage2_hybrid": s2,
                    "stage3_full":   s3,
                }
            except Exception as e:
                print(f"  ✗ Retrieval error: {e}")
                result_entry["retrieval_error"] = str(e)
        else:
            print("  ⚠ No source_chunk_id — skipping retrieval metrics")

        # ── Generation evaluation ─────────────────────────────────────────
        try:
            rag_response = orchestrator.process_query(question, include_citations=False)
            answer = rag_response.get("answer", "")
            context_str = format_context(rag_response)
            chunks_retrieved = rag_response.get("metadata", {}).get("chunks_retrieved", 0)
            response_time_ms = rag_response.get("metadata", {}).get("response_time_ms", 0)

            print(f"  [Generation] {chunks_retrieved} chunks, {response_time_ms}ms")

            prompt = build_judge_prompt(question, context_str, answer, ground_truth)
            scores = call_local_judge(ollama_url, judge_model, prompt)

            gen_metrics.append(scores)

            print(f"    Faithfulness:      {scores.get('faithfulness')}/5  — {scores.get('faithfulness_reason', '')}")
            print(f"    Answer Relevance:  {scores.get('answer_relevance')}/5  — {scores.get('answer_relevance_reason', '')}")
            print(f"    Context Precision: {scores.get('context_precision')}/5  — {scores.get('context_precision_reason', '')}")
            if "context_recall" in scores:
                print(f"    Context Recall:    {scores.get('context_recall')}/5  — {scores.get('context_recall_reason', '')}")

            result_entry["generation"] = {
                "answer": answer,
                "chunks_retrieved": chunks_retrieved,
                "response_time_ms": response_time_ms,
                "scores": scores,
            }

        except Exception as e:
            print(f"  ✗ Generation/judge error: {e}")
            result_entry["generation_error"] = str(e)

        print()
        results.append(result_entry)

    # ── Retrieval summary ─────────────────────────────────────────────────
    avg1 = average_metrics(stage1_metrics)
    avg2 = average_metrics(stage2_metrics)
    avg3 = average_metrics(stage3_metrics)

    print("=" * 70)
    print("RETRIEVAL EVALUATION SUMMARY")
    print("=" * 70)
    if avg1:
        print(f"{'Metric':<14} {'Vector':>10} {'Hybrid':>10} {'Full Pipeline':>14}")
        print("-" * 52)
        for metric in ["hit@1", "hit@3", "hit@5", "hit@10", "mrr", "map", "ndcg@5", "ndcg@10"]:
            v1 = avg1.get(metric, 0)
            v2 = avg2.get(metric, 0)
            v3 = avg3.get(metric, 0)
            best = max(v1, v2, v3)
            def fmt(v): return f"{'*' if v == best else ' '}{v:.4f}"
            print(f"  {metric:<12} {fmt(v1):>10} {fmt(v2):>10} {fmt(v3):>14}")
        print("-" * 52)
        print("  * = best stage for that metric")
    else:
        print("  No retrieval metrics computed (source_chunk_id missing from all questions)")
    print()

    # ── Generation summary ────────────────────────────────────────────────
    print("=" * 70)
    print("GENERATION EVALUATION SUMMARY")
    print("=" * 70)
    n_gen = len(gen_metrics)
    if n_gen > 0:
        def avg_score(key):
            vals = [m[key] for m in gen_metrics if key in m]
            return sum(vals) / len(vals) if vals else 0.0

        avg_faith    = avg_score("faithfulness")
        avg_rel      = avg_score("answer_relevance")
        avg_ctx_prec = avg_score("context_precision")
        ctx_recall_vals = [m["context_recall"] for m in gen_metrics if "context_recall" in m]

        print(f"  Questions evaluated:   {n_gen}/{len(all_questions)}")
        print(f"  Avg Faithfulness:      {avg_faith:.2f}/5")
        print(f"  Avg Answer Relevance:  {avg_rel:.2f}/5")
        print(f"  Avg Context Precision: {avg_ctx_prec:.2f}/5")
        if ctx_recall_vals:
            print(f"  Avg Context Recall:    {sum(ctx_recall_vals)/len(ctx_recall_vals):.2f}/5")

        gen_summary = {
            "evaluated": n_gen,
            "total": len(all_questions),
            "avg_faithfulness":      round(avg_faith, 3),
            "avg_answer_relevance":  round(avg_rel, 3),
            "avg_context_precision": round(avg_ctx_prec, 3),
        }
        if ctx_recall_vals:
            gen_summary["avg_context_recall"] = round(
                sum(ctx_recall_vals) / len(ctx_recall_vals), 3
            )
    else:
        print("  No generation metrics computed.")
        gen_summary = {"evaluated": 0, "total": len(all_questions)}
    print("=" * 70)

    # ── Save report ───────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output) if args.output else Path(f"data/eval_report_{timestamp}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "questions_file": str(questions_path),
        "top_k": args.top_k,
        "judge_model": judge_model,
        "judge_type": "local_ollama",
        "summary": {
            "retrieval": {
                "evaluated": len(stage1_metrics),
                "total": len(all_questions),
                "stage1_vector_only":    avg1,
                "stage2_hybrid_rrf":     avg2,
                "stage3_full_pipeline":  avg3,
            },
            "generation": gen_summary,
        },
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Report saved to: {output_path}")
    mysql.close()


if __name__ == "__main__":
    main()
