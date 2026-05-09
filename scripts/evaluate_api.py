#!/usr/bin/env python3
"""
MAHIKS-TR: API-Based Evaluation Script

Evaluates retrieval and RAG quality by calling the running backend API.
No internal imports required — works against any deployed instance.

RETRIEVAL METRICS  (from /api/rag/debug)
  Stage 1 — Vector search chunk ranking
  Stage 2 — Full pipeline: sub-chunk cross-encoder reranking
  Metrics: Hit@k (k=1,3,5,10), MRR, MAP, nDCG@k (k=5,10)

GENERATION METRICS  (LLM-as-judge via external API)
  - Faithfulness      — Is the answer grounded in retrieved context?
  - Answer Relevance  — Does the answer directly address the question?
  - Context Precision — Were retrieved sub-chunks useful for the answer?
  - Context Recall    — Were ground-truth facts covered by context? (when ground_truth present)

LATENCY
  - Retrieval latency (ms) from /api/rag/debug server measurement
  - Generation latency (ms) wall-clock from /api/ask
  - Statistics: mean, median, p95, p99, min, max

Judge providers: openai | openrouter | gemini | anthropic | ollama

Usage:
  python scripts/evaluate_api.py
  python scripts/evaluate_api.py --api-url http://localhost:8000
  python scripts/evaluate_api.py --judge-provider openai --judge-model gpt-4o-mini
  python scripts/evaluate_api.py --judge-provider openrouter --judge-model qwen/qwen-2.5-72b-instruct
  python scripts/evaluate_api.py --judge-provider gemini --judge-model gemini-2.5-flash
  python scripts/evaluate_api.py --judge-provider anthropic --judge-model claude-haiku-4-5-20251001
  python scripts/evaluate_api.py --judge-provider ollama --judge-model qwen2.5:7b --ollama-url http://localhost:11434
  python scripts/evaluate_api.py --skip-generation       # retrieval metrics only
  python scripts/evaluate_api.py --skip-retrieval        # generation + judge only
  python scripts/evaluate_api.py --limit 10              # first 10 questions
"""
import sys
import json
import math
import re
import time
import argparse
import os
import statistics
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


# ─── IR metric helpers ────────────────────────────────────────────────────────

def hit_at_k(ranked_ids: list, relevant_id: int, k: int) -> int:
    return 1 if relevant_id in ranked_ids[:k] else 0


def reciprocal_rank(ranked_ids: list, relevant_id: int) -> float:
    try:
        return 1.0 / (ranked_ids.index(relevant_id) + 1)
    except ValueError:
        return 0.0


def average_precision(ranked_ids: list, relevant_id: int) -> float:
    try:
        rank = ranked_ids.index(relevant_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def ndcg_at_k(ranked_ids: list, relevant_id: int, k: int) -> float:
    try:
        rank = ranked_ids.index(relevant_id) + 1
        if rank > k:
            return 0.0
        return 1.0 / math.log2(rank + 1)
    except ValueError:
        return 0.0


def compute_ir_metrics(ranked_ids: list, relevant_id: int) -> dict:
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


# ─── Latency statistics ───────────────────────────────────────────────────────

def latency_stats(values_ms: list) -> dict:
    if not values_ms:
        return {}
    sv = sorted(values_ms)
    n = len(sv)

    def pct(p: float) -> float:
        idx = max(0, int(math.ceil(p / 100.0 * n)) - 1)
        return sv[idx]

    return {
        "count":     n,
        "mean_ms":   round(statistics.mean(sv), 1),
        "median_ms": round(statistics.median(sv), 1),
        "p95_ms":    round(pct(95), 1),
        "p99_ms":    round(pct(99), 1),
        "min_ms":    round(sv[0], 1),
        "max_ms":    round(sv[-1], 1),
    }


# ─── Backend API calls ────────────────────────────────────────────────────────

def api_health_check(api_url: str, timeout: int = 10) -> bool:
    try:
        r = requests.get(f"{api_url}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def call_rag_debug(api_url: str, question: str, timeout: int = 90) -> tuple:
    """
    Call /api/rag/debug.
    Returns (debug_payload, retrieval_ms) or (None, None) on error.
    Prefers the server-measured retrieval_time_ms for accuracy.
    """
    t0 = time.time()
    try:
        r = requests.post(
            f"{api_url}/api/rag/debug",
            json={"question": question},
            timeout=timeout,
        )
        wall_ms = (time.time() - t0) * 1000
        if r.status_code != 200:
            return None, None
        data = r.json()
        server_ms = data.get("pipeline", {}).get("retrieval_time_ms")
        return data, float(server_ms if server_ms is not None else wall_ms)
    except Exception:
        return None, None


def call_ask(api_url: str, question: str, include_citations: bool = True,
             timeout: int = 120) -> tuple:
    """
    Call /api/ask and return (response_payload, wall_clock_ms).
    Returns (None, None) on error.
    """
    t0 = time.time()
    try:
        r = requests.post(
            f"{api_url}/api/ask",
            json={"question": question, "include_citations": include_citations},
            timeout=timeout,
        )
        wall_ms = (time.time() - t0) * 1000
        if r.status_code != 200:
            return None, None
        return r.json(), wall_ms
    except Exception:
        return None, None


# ─── Judge: prompt construction ───────────────────────────────────────────────

_JUDGE_SYSTEM = (
    "You are evaluating a Turkish health insurance Q&A (RAG) system. "
    "Be objective, strict, and base scores solely on the provided criteria."
)

_JUDGE_TEMPLATE = """\
Evaluate the following response from a Turkish health insurance RAG system. \
Score each metric from 1 to 5.

QUESTION:
{question}

RETRIEVED CONTEXT (sub-chunks sent to the LLM, ranked by relevance):
{context}

GENERATED ANSWER:
{answer}
{ground_truth_block}
SCORING CRITERIA:

1. FAITHFULNESS (1-5): Is every factual claim in the answer supported by the retrieved context?
   1 = significant hallucination / fabrication
   3 = partially grounded, some unsupported claims
   5 = every claim is directly supported by context

2. ANSWER_RELEVANCE (1-5): Does the answer directly and completely address the question?
   1 = off-topic or misses the point entirely
   3 = partially answers the question
   5 = complete, precise, and directly on-topic

3. CONTEXT_PRECISION (1-5): What fraction of the retrieved sub-chunks were actually useful?
   1 = almost all retrieved chunks irrelevant to the answer
   3 = roughly half the chunks were useful
   5 = all retrieved chunks directly contributed to the answer
{context_recall_block}
Respond ONLY with a valid JSON object — no markdown fences, no explanation outside JSON:
{json_schema}"""

_RECALL_CRITERION = """\
4. CONTEXT_RECALL (1-5): What fraction of the facts in the ground-truth answer \
are present in the retrieved context?
   1 = almost none of the ground-truth facts are in context
   3 = about half the ground-truth facts are covered
   5 = all ground-truth facts are present in the retrieved context
"""

_JSON_BASE = """{
  "faithfulness": <integer 1-5>,
  "answer_relevance": <integer 1-5>,
  "context_precision": <integer 1-5>,
  "faithfulness_reason": "<one concise sentence>",
  "answer_relevance_reason": "<one concise sentence>",
  "context_precision_reason": "<one concise sentence>"
}"""

_JSON_WITH_RECALL = """{
  "faithfulness": <integer 1-5>,
  "answer_relevance": <integer 1-5>,
  "context_precision": <integer 1-5>,
  "context_recall": <integer 1-5>,
  "faithfulness_reason": "<one concise sentence>",
  "answer_relevance_reason": "<one concise sentence>",
  "context_precision_reason": "<one concise sentence>",
  "context_recall_reason": "<one concise sentence>"
}"""


def build_judge_prompt(question: str, sub_chunks: list, answer: str,
                       ground_truth: str = None) -> str:
    context_parts = []
    for i, sc in enumerate(sub_chunks[:6], 1):
        src = sc.get("source", "Unknown")
        ce  = sc.get("ce_score")
        score_note = f"  [CE score: {ce:.3f}]" if ce is not None else ""
        context_parts.append(
            f"[Sub-chunk {i} — {src}{score_note}]\n{sc.get('text', '')}"
        )
    context_str = "\n\n".join(context_parts) if context_parts else "(no context retrieved)"

    gt_block = f"\nGROUND TRUTH ANSWER:\n{ground_truth}\n" if ground_truth else ""
    cr_block  = _RECALL_CRITERION if ground_truth else ""
    schema    = _JSON_WITH_RECALL if ground_truth else _JSON_BASE

    return _JUDGE_TEMPLATE.format(
        question=question,
        context=context_str,
        answer=answer,
        ground_truth_block=gt_block,
        context_recall_block=cr_block,
        json_schema=schema,
    )


# ─── Judge: response parsing ──────────────────────────────────────────────────

def parse_judge_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON in judge response: {raw[:300]}")


# ─── Judge: provider implementations ─────────────────────────────────────────

def _judge_openai_compat(base_url: str, api_key: str, model: str,
                         prompt: str, timeout: int = 120) -> dict:
    """Handles both OpenAI and OpenRouter (identical wire format)."""
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.0,
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return parse_judge_response(r.json()["choices"][0]["message"]["content"])


def _judge_gemini(api_key: str, model: str, prompt: str, timeout: int = 120) -> dict:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{model}:generateContent?key={api_key}"
    )
    r = requests.post(
        url,
        json={
            "contents": [{"role": "user", "parts": [
                {"text": _JUDGE_SYSTEM + "\n\n" + prompt}
            ]}],
            "generationConfig": {"temperature": 0.0},
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return parse_judge_response(text)


def _judge_anthropic(api_key: str, model: str, prompt: str, timeout: int = 120) -> dict:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      model,
            "max_tokens": 512,
            "temperature": 0.0,
            "system":     _JUDGE_SYSTEM,
            "messages":   [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
    return parse_judge_response(r.json()["content"][0]["text"])


def _judge_ollama(base_url: str, model: str, prompt: str, timeout: int = 180) -> dict:
    r = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
    return parse_judge_response(r.json().get("message", {}).get("content", ""))


def call_judge(provider: str, cfg: dict, prompt: str, retries: int = 2) -> dict:
    def _attempt():
        if provider == "openai":
            return _judge_openai_compat(
                "https://api.openai.com/v1", cfg["api_key"], cfg["model"], prompt)
        elif provider == "openrouter":
            return _judge_openai_compat(
                "https://openrouter.ai/api/v1", cfg["api_key"], cfg["model"], prompt)
        elif provider == "gemini":
            return _judge_gemini(cfg["api_key"], cfg["model"], prompt)
        elif provider == "anthropic":
            return _judge_anthropic(cfg["api_key"], cfg["model"], prompt)
        elif provider == "ollama":
            return _judge_ollama(cfg["base_url"], cfg["model"], prompt)
        else:
            raise ValueError(f"Unknown judge provider: {provider}")

    last_err = None
    for attempt in range(retries + 1):
        try:
            return _attempt()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise last_err


# ─── Config builder ───────────────────────────────────────────────────────────

def build_judge_config(args) -> dict:
    p = args.judge_provider

    if p == "openai":
        key   = args.judge_api_key or os.getenv("OPENAI_API_KEY", "")
        model = args.judge_model   or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not key:
            raise ValueError("OpenAI judge requires OPENAI_API_KEY or --judge-api-key")
        return {"api_key": key, "model": model}

    elif p == "openrouter":
        key   = args.judge_api_key or os.getenv("OPENROUTER_API_KEY", "")
        model = args.judge_model   or os.getenv("OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-72b-instruct")
        if not key:
            raise ValueError("OpenRouter judge requires OPENROUTER_API_KEY or --judge-api-key")
        return {"api_key": key, "model": model}

    elif p == "gemini":
        key   = args.judge_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        model = args.judge_model   or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not key:
            raise ValueError("Gemini judge requires GEMINI_API_KEY or --judge-api-key")
        return {"api_key": key, "model": model}

    elif p == "anthropic":
        key   = args.judge_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        model = args.judge_model   or "claude-haiku-4-5-20251001"
        if not key:
            raise ValueError("Anthropic judge requires ANTHROPIC_API_KEY or --judge-api-key")
        return {"api_key": key, "model": model}

    elif p == "ollama":
        base_url = args.ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model    = args.judge_model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        return {"base_url": base_url, "model": model}

    else:
        raise ValueError(f"Unknown judge provider: {p}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MAHIKS-TR API-Based Evaluation (Retrieval + Generation + Latency)"
    )
    parser.add_argument("--questions",  default="data/eval_questions.json",
                        help="Path to eval questions JSON (default: data/eval_questions.json)")
    parser.add_argument("--output",     default=None,
                        help="Output report path (default: data/eval_api_report_<ts>.json)")
    parser.add_argument("--api-url",    default=os.getenv("MAHIKS_API_URL", "http://localhost:8000"),
                        help="Backend base URL (default: MAHIKS_API_URL env var or http://localhost:8000)")
    parser.add_argument("--top-k",      type=int, default=10,
                        help="Top-K for retrieval (default: 10)")
    parser.add_argument("--judge-provider",
                        choices=["openai", "openrouter", "gemini", "anthropic", "ollama"],
                        default="openrouter",
                        help="LLM provider for judging (default: openrouter)")
    parser.add_argument("--judge-model",   default=None,
                        help="Model name for judge LLM (overrides env-var default)")
    parser.add_argument("--judge-api-key", default=None,
                        help="API key for judge provider (overrides env-var)")
    parser.add_argument("--ollama-url",    default=None,
                        help="Ollama base URL when using ollama judge provider")
    parser.add_argument("--skip-generation", action="store_true",
                        help="Run retrieval metrics only — skip /api/ask + judge")
    parser.add_argument("--skip-retrieval",  action="store_true",
                        help="Run generation + judge only — skip /api/rag/debug IR metrics")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only the first N questions")
    args = parser.parse_args()

    # Auto-load .env so the script picks up OPENROUTER_API_KEY etc. when run locally
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    # Build judge config (skip if generation is disabled)
    judge_cfg = None
    if not args.skip_generation:
        try:
            judge_cfg = build_judge_config(args)
        except ValueError as e:
            print(f"✗ Judge config error: {e}")
            sys.exit(1)

    judge_label = (
        f"{args.judge_provider} / {judge_cfg.get('model') or judge_cfg.get('base_url')}"
        if judge_cfg else "disabled"
    )

    print("\n" + "=" * 74)
    print("MAHIKS-TR: API-Based Evaluation  (Retrieval + Generation + Latency)")
    print("=" * 74)
    print(f"Date:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend:      {args.api_url}")
    print(f"Questions:    {args.questions}")
    print(f"Top-K:        {args.top_k}")
    print(f"Judge:        {judge_label}")
    if args.limit:
        print(f"Limit:        first {args.limit} questions")
    if args.skip_retrieval:
        print("Mode:         generation + judge only")
    elif args.skip_generation:
        print("Mode:         retrieval metrics only")
    print("=" * 74 + "\n")

    # Health check
    print("Checking backend...", end=" ", flush=True)
    if not api_health_check(args.api_url):
        print(f"FAILED\n  Is the backend running at {args.api_url}?")
        sys.exit(1)
    print("OK\n")

    # Load questions
    qpath = Path(args.questions)
    if not qpath.exists():
        print(f"✗ Questions file not found: {qpath}")
        sys.exit(1)
    all_questions = json.loads(qpath.read_text(encoding="utf-8"))
    if args.limit:
        all_questions = all_questions[: args.limit]
    print(f"Loaded {len(all_questions)} questions\n")

    # Accumulators
    results:             list = []
    stage1_metrics:      list = []
    stage2_metrics:      list = []
    gen_metrics:         list = []
    retrieval_lats_ms:   list = []
    generation_lats_ms:  list = []

    for idx, item in enumerate(all_questions, 1):
        question     = item["question"]
        ground_truth = item.get("ground_truth")
        relevant_id  = int(item["source_chunk_id"]) if item.get("source_chunk_id") else None
        q_id         = item.get("id", idx)

        print(f"[{idx}/{len(all_questions)}] Q{q_id}: {question[:74]}")

        entry = {
            "id":            q_id,
            "question":      question,
            "ground_truth":  ground_truth,
            "source_chunk_id": relevant_id,
        }

        # ── Retrieval evaluation via /api/rag/debug ───────────────────────
        debug_data = None
        if not args.skip_retrieval:
            debug_data, ret_ms = call_rag_debug(args.api_url, question)
            if debug_data is None:
                print("  ✗ /api/rag/debug failed — skipping retrieval metrics")
                entry["retrieval_error"] = "API call failed or timeout"
            else:
                retrieval_lats_ms.append(ret_ms)
                pipeline = debug_data.get("pipeline", {})

                if relevant_id is not None:
                    # Stage 1: ranked chunk IDs from the vector (Qdrant RRF) search
                    s1_ids = debug_data.get("vector_chunk_ids", [])
                    s1     = compute_ir_metrics(s1_ids, relevant_id)
                    stage1_metrics.append(s1)

                    # Stage 2: deduplicated parent_chunk_ids from reranked final sub-chunks
                    seen_s2: set = set()
                    s2_ids:  list = []
                    for sc in debug_data.get("final_sub_chunks", []):
                        pid = sc.get("parent_chunk_id")
                        if pid is not None and pid not in seen_s2:
                            seen_s2.add(pid)
                            s2_ids.append(pid)
                    s2 = compute_ir_metrics(s2_ids, relevant_id)
                    stage2_metrics.append(s2)

                    def rank_str(ids, rid):
                        r = find_rank(ids, rid)
                        return f"rank {r}" if r > 0 else "NOT FOUND"

                    print(
                        f"  [Retrieval] {ret_ms:.0f}ms | "
                        f"Vector — Hit@5={s1['hit@5']} MRR={s1['mrr']:.3f} nDCG@5={s1['ndcg@5']:.3f} ({rank_str(s1_ids, relevant_id)}) | "
                        f"Pipeline — Hit@5={s2['hit@5']} MRR={s2['mrr']:.3f} nDCG@5={s2['ndcg@5']:.3f} ({rank_str(s2_ids, relevant_id)})"
                    )

                    entry["retrieval"] = {
                        "latency_ms":       round(ret_ms, 1),
                        "pipeline_stats":   pipeline,
                        "stage1_vector":    s1,
                        "stage2_pipeline":  s2,
                        "stage1_rank":      find_rank(s1_ids, relevant_id),
                        "stage2_rank":      find_rank(s2_ids, relevant_id),
                    }
                else:
                    print(f"  [Retrieval] {ret_ms:.0f}ms | no source_chunk_id — IR metrics skipped")
                    entry["retrieval"] = {
                        "latency_ms":     round(ret_ms, 1),
                        "pipeline_stats": pipeline,
                    }

        # ── Generation + LLM judge via /api/ask ──────────────────────────
        if not args.skip_generation:
            rag_data, gen_ms = call_ask(args.api_url, question, include_citations=True)
            if rag_data is None:
                print("  ✗ /api/ask failed — skipping generation metrics")
                entry["generation_error"] = "API call failed or timeout"
            else:
                generation_lats_ms.append(gen_ms)
                answer       = rag_data.get("answer", "")
                server_meta  = rag_data.get("metadata", {})
                chunks_retr  = server_meta.get("chunks_retrieved", 0)
                server_ms    = server_meta.get("response_time_ms")

                # Use sub-chunks from the debug call as judge context (if available),
                # otherwise fall back to citations from the ask response.
                if debug_data and debug_data.get("final_sub_chunks"):
                    judge_context = debug_data["final_sub_chunks"]
                else:
                    cites = rag_data.get("citations") or []
                    judge_context = [
                        {"source": c.get("source", ""), "text": c.get("source", "")}
                        for c in cites
                    ]

                print(
                    f"  [Generation] wall={gen_ms:.0f}ms"
                    + (f" server={server_ms}ms" if server_ms else "")
                    + f" chunks={chunks_retr}"
                )

                try:
                    prompt = build_judge_prompt(question, judge_context, answer, ground_truth)
                    scores = call_judge(args.judge_provider, judge_cfg, prompt)
                    gen_metrics.append(scores)

                    def _sc(key, label):
                        v = scores.get(key)
                        r = scores.get(f"{key}_reason", "")[:64]
                        print(f"    {label:<20} {v}/5  {r}")

                    _sc("faithfulness",      "Faithfulness:")
                    _sc("answer_relevance",  "Answer Relevance:")
                    _sc("context_precision", "Context Precision:")
                    if "context_recall" in scores:
                        _sc("context_recall", "Context Recall:")

                    entry["generation"] = {
                        "answer":          answer,
                        "chunks_retrieved": chunks_retr,
                        "wall_latency_ms":  round(gen_ms, 1),
                        "server_latency_ms": server_ms,
                        "judge_scores":    scores,
                    }

                except Exception as e:
                    print(f"  ✗ Judge error: {e}")
                    entry["generation"] = {
                        "answer":           answer,
                        "chunks_retrieved": chunks_retr,
                        "wall_latency_ms":  round(gen_ms, 1),
                        "server_latency_ms": server_ms,
                        "judge_error":      str(e),
                    }

        print()
        results.append(entry)

    # ── Retrieval summary ─────────────────────────────────────────────────────
    avg1 = average_metrics(stage1_metrics)
    avg2 = average_metrics(stage2_metrics)

    print("=" * 74)
    print("RETRIEVAL EVALUATION SUMMARY")
    print("=" * 74)
    if avg1:
        print(f"  {'Metric':<12}  {'Vector (Stage 1)':>17}  {'Full Pipeline (Stage 2)':>24}  Best")
        print("  " + "-" * 60)
        for m in ["hit@1", "hit@3", "hit@5", "hit@10", "mrr", "map", "ndcg@5", "ndcg@10"]:
            v1 = avg1.get(m, 0)
            v2 = avg2.get(m, 0)
            best = "pipeline" if v2 > v1 else ("vector" if v1 > v2 else "tie")
            print(f"  {m:<12}  {v1:>17.4f}  {v2:>24.4f}  {best}")
        print("  " + "-" * 60)
        n_ir = len(stage1_metrics)
        print(f"  Evaluated: {n_ir}/{len(all_questions)} questions with source_chunk_id")
    else:
        print("  No IR metrics (all questions missing source_chunk_id, or --skip-retrieval set)")

    if retrieval_lats_ms:
        rs = latency_stats(retrieval_lats_ms)
        print(
            f"\n  Retrieval latency — "
            f"mean: {rs['mean_ms']}ms  median: {rs['median_ms']}ms  "
            f"p95: {rs['p95_ms']}ms  p99: {rs['p99_ms']}ms  "
            f"min: {rs['min_ms']}ms  max: {rs['max_ms']}ms"
        )
    print()

    # ── Generation summary ────────────────────────────────────────────────────
    print("=" * 74)
    print("GENERATION EVALUATION SUMMARY")
    print("=" * 74)
    n_gen = len(gen_metrics)
    gen_summary = {"evaluated": n_gen, "total": len(all_questions)}

    if n_gen > 0:
        def avg_score(key):
            vals = [m[key] for m in gen_metrics if key in m]
            return sum(vals) / len(vals) if vals else 0.0

        avg_f  = avg_score("faithfulness")
        avg_r  = avg_score("answer_relevance")
        avg_cp = avg_score("context_precision")
        cr_vals = [m["context_recall"] for m in gen_metrics if "context_recall" in m]

        print(f"  Evaluated:             {n_gen}/{len(all_questions)}")
        print(f"  Avg Faithfulness:      {avg_f:.2f}/5")
        print(f"  Avg Answer Relevance:  {avg_r:.2f}/5")
        print(f"  Avg Context Precision: {avg_cp:.2f}/5")
        if cr_vals:
            avg_cr = sum(cr_vals) / len(cr_vals)
            print(f"  Avg Context Recall:    {avg_cr:.2f}/5  (from {len(cr_vals)} questions with ground truth)")

        gen_summary.update({
            "avg_faithfulness":      round(avg_f, 3),
            "avg_answer_relevance":  round(avg_r, 3),
            "avg_context_precision": round(avg_cp, 3),
        })
        if cr_vals:
            gen_summary["avg_context_recall"] = round(sum(cr_vals) / len(cr_vals), 3)
    else:
        print("  No generation metrics computed.")

    if generation_lats_ms:
        gs = latency_stats(generation_lats_ms)
        print(
            f"\n  Generation latency  — "
            f"mean: {gs['mean_ms']}ms  median: {gs['median_ms']}ms  "
            f"p95: {gs['p95_ms']}ms  p99: {gs['p99_ms']}ms  "
            f"min: {gs['min_ms']}ms  max: {gs['max_ms']}ms"
        )
    print("=" * 74)

    # ── Save report ───────────────────────────────────────────────────────────
    ts = datetime.now()
    output_path = (
        Path(args.output)
        if args.output
        else Path(f"data/eval_api_report_{ts.strftime('%Y%m%d_%H%M%S')}.json")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp":      ts.isoformat(),
        "api_url":        args.api_url,
        "questions_file": str(qpath),
        "top_k":          args.top_k,
        "judge": {
            "provider": args.judge_provider if not args.skip_generation else None,
            "model":    (judge_cfg or {}).get("model"),
        },
        "summary": {
            "retrieval": {
                "evaluated":          len(stage1_metrics),
                "total":              len(all_questions),
                "stage1_vector":      avg1,
                "stage2_full_pipeline": avg2,
                "latency":            latency_stats(retrieval_lats_ms),
            },
            "generation":         gen_summary,
            "generation_latency": latency_stats(generation_lats_ms),
        },
        "results": results,
    }

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✓ Report saved to: {output_path}\n")


if __name__ == "__main__":
    main()
