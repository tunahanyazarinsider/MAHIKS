#!/usr/bin/env python3
"""
Auto-generate evaluation questions from indexed document chunks.
Supports multiple LLM providers for high-quality Turkish Q&A pair generation.

Providers: openrouter (default) | openai | gemini | anthropic | ollama

Usage:
  # Inside Docker (recommended — has DB access):
  docker compose run --rm backend python -m scripts.generate_eval_questions
  docker compose run --rm backend python -m scripts.generate_eval_questions --count 20
  docker compose run --rm backend python -m scripts.generate_eval_questions --provider openrouter
  docker compose run --rm backend python -m scripts.generate_eval_questions --provider openai --model gpt-4o
  docker compose run --rm backend python -m scripts.generate_eval_questions --provider gemini --model gemini-2.5-flash
  docker compose run --rm backend python -m scripts.generate_eval_questions --provider anthropic --model claude-haiku-4-5-20251001
  docker compose run --rm backend python -m scripts.generate_eval_questions --provider ollama --ollama-url http://host.docker.internal:11434
"""
import sys
import json
import argparse
import os
import random
import re
import time
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from database.mysql_handler import MySQLHandler
from config import Config


# ─── Prompt ──────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are an expert at creating high-quality evaluation datasets for "
    "Turkish health insurance question-answering systems. "
    "You write precise, specific questions and factually accurate answers "
    "grounded strictly in the provided text."
)

_PROMPT = """\
Aşağıda bir Türk sağlık sigortası yönetmeliğinden alınmış bir metin parçası verilmiştir.

METİN:
{chunk_text}

Bu metni dikkatlice oku ve yalnızca bu metinden yanıtlanabilecek **spesifik, \
bilgi odaklı** bir soru yaz. Ardından, yalnızca bu metne dayanarak kesin ve \
doğru bir cevap yaz.

Yanıtını aşağıdaki JSON formatında ver — başka hiçbir şey yazma:
{{
  "question": "<Türkçe soru>",
  "ground_truth": "<Türkçe cevap, 1-3 cümle, maddeler veya sayısal veriler içerebilir>"
}}

Kurallar:
- Soru yalnızca bu metinden cevaplanabilir olmalı
- "Bu metne göre", "Metinde belirtildiğine göre" gibi ifadeler KULLANMA
- Genel veya belirsiz sorular sorma
- Sayısal değerler, oranlar, limitler veya prosedürler hakkında sorular tercih edilir
- Cevap doğrudan, özlü ve eksiksiz olmalı
"""


# ─── LLM provider implementations ────────────────────────────────────────────

def _call_openai_compat(base_url: str, api_key: str, model: str,
                        prompt: str, timeout: int = 120) -> str:
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(api_key: str, model: str, prompt: str, timeout: int = 120) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{model}:generateContent?key={api_key}"
    )
    r = requests.post(
        url,
        json={
            "contents": [{"role": "user", "parts": [
                {"text": _SYSTEM + "\n\n" + prompt}
            ]}],
            "generationConfig": {"temperature": 0.3},
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_anthropic(api_key: str, model: str, prompt: str, timeout: int = 120) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":       model,
            "max_tokens":  512,
            "temperature": 0.3,
            "system":      _SYSTEM,
            "messages":    [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["content"][0]["text"]


def _call_ollama(base_url: str, model: str, prompt: str, timeout: int = 180) -> str:
    r = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
    return r.json().get("message", {}).get("content", "")


def call_llm(provider: str, cfg: dict, chunk_text: str, retries: int = 2) -> dict:
    prompt = _PROMPT.format(chunk_text=chunk_text[:2000])
    last_err = None

    for attempt in range(retries + 1):
        try:
            if provider == "openai":
                raw = _call_openai_compat(
                    "https://api.openai.com/v1", cfg["api_key"], cfg["model"], prompt)
            elif provider == "openrouter":
                raw = _call_openai_compat(
                    "https://openrouter.ai/api/v1", cfg["api_key"], cfg["model"], prompt)
            elif provider == "gemini":
                raw = _call_gemini(cfg["api_key"], cfg["model"], prompt)
            elif provider == "anthropic":
                raw = _call_anthropic(cfg["api_key"], cfg["model"], prompt)
            elif provider == "ollama":
                raw = _call_ollama(cfg["base_url"], cfg["model"], prompt)
            else:
                raise ValueError(f"Unknown provider: {provider}")

            return parse_json_response(raw)

        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)

    raise last_err


# ─── JSON parsing ─────────────────────────────────────────────────────────────

def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            raise ValueError(f"No valid JSON in response: {raw[:300]}")
    if "question" not in parsed or "ground_truth" not in parsed:
        raise ValueError(f"Missing question/ground_truth keys: {parsed}")
    return parsed


# ─── DB helper ────────────────────────────────────────────────────────────────

def get_random_chunks(mysql: MySQLHandler, count: int, min_length: int = 200) -> list:
    try:
        mysql.cursor.execute(
            """
            SELECT c.id, c.chunk_text, c.chunk_order, d.source_name
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE CHAR_LENGTH(c.chunk_text) >= %s
            ORDER BY RAND()
            LIMIT %s
            """,
            (min_length, count * 3),
        )
        rows = mysql.cursor.fetchall()
        random.shuffle(rows)
        return rows
    except Exception as e:
        print(f"✗ Error fetching chunks: {e}")
        return []


# ─── Config builder ───────────────────────────────────────────────────────────

def build_provider_config(args) -> dict:
    p = args.provider

    if p == "openai":
        key   = args.api_key or os.getenv("OPENAI_API_KEY", "")
        model = args.model   or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not key:
            raise ValueError("OpenAI requires OPENAI_API_KEY or --api-key")
        return {"api_key": key, "model": model}

    elif p == "openrouter":
        key   = args.api_key or os.getenv("OPENROUTER_API_KEY", "")
        model = args.model   or os.getenv("OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-72b-instruct")
        if not key:
            raise ValueError("OpenRouter requires OPENROUTER_API_KEY or --api-key")
        return {"api_key": key, "model": model}

    elif p == "gemini":
        key   = args.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        model = args.model   or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not key:
            raise ValueError("Gemini requires GEMINI_API_KEY or --api-key")
        return {"api_key": key, "model": model}

    elif p == "anthropic":
        key   = args.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        model = args.model   or "claude-haiku-4-5-20251001"
        if not key:
            raise ValueError("Anthropic requires ANTHROPIC_API_KEY or --api-key")
        return {"api_key": key, "model": model}

    elif p == "ollama":
        base_url = args.ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model    = args.model      or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        return {"base_url": base_url, "model": model}

    else:
        raise ValueError(f"Unknown provider: {p}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate eval questions from indexed chunks using a configurable LLM provider"
    )
    parser.add_argument("--count",    type=int, default=10,
                        help="Number of questions to generate (default: 10)")
    parser.add_argument("--output",   default="data/eval_questions.json",
                        help="Output path (default: data/eval_questions.json)")
    parser.add_argument("--provider",
                        choices=["openrouter", "openai", "gemini", "anthropic", "ollama"],
                        default="openrouter",
                        help="LLM provider (default: openrouter)")
    parser.add_argument("--model",     default=None,
                        help="Model name (overrides env-var default for chosen provider)")
    parser.add_argument("--api-key",   default=None,
                        help="API key for the provider (overrides env-var)")
    parser.add_argument("--ollama-url", default=None,
                        help="Ollama base URL when using ollama provider")
    parser.add_argument("--min-chunk-length", type=int, default=200,
                        help="Minimum chunk character length to sample (default: 200)")
    args = parser.parse_args()

    # Auto-load .env so API keys are available when running outside Docker
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    Config.validate()

    try:
        cfg = build_provider_config(args)
    except ValueError as e:
        print(f"✗ Provider config error: {e}")
        sys.exit(1)

    model_label = cfg.get("model") or cfg.get("base_url")

    print("\n" + "=" * 70)
    print("MAHIKS-TR: Eval Question Generator")
    print("=" * 70)
    print(f"Start:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Provider: {args.provider} / {model_label}")
    print(f"Target:   {args.count} questions")
    print(f"Output:   {args.output}")
    print("=" * 70 + "\n")

    mysql = MySQLHandler(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
    )

    total_chunks = mysql.get_chunk_count()
    print(f"Total chunks in DB: {total_chunks}")
    if total_chunks == 0:
        print("✗ No chunks found. Run vectorize_only first.")
        mysql.close()
        sys.exit(1)

    chunks = get_random_chunks(mysql, args.count, min_length=args.min_chunk_length)
    if not chunks:
        print("✗ Could not fetch chunks from MySQL.")
        mysql.close()
        sys.exit(1)

    print(f"Fetched {len(chunks)} candidate chunks\n")

    questions = []
    attempted = 0

    for chunk in chunks:
        if len(questions) >= args.count:
            break

        attempted += 1
        preview = chunk['chunk_text'][:80].replace('\n', ' ')
        print(f"[{len(questions)+1}/{args.count}] Chunk {chunk['id']} — \"{preview}...\"")

        try:
            result = call_llm(args.provider, cfg, chunk['chunk_text'])
            questions.append({
                "id":             len(questions) + 1,
                "question":       result["question"],
                "ground_truth":   result["ground_truth"],
                "source_chunk_id": chunk['id'],
                "source_name":    chunk['source_name'],
            })
            print(f"  Q: {result['question']}")
            print(f"  A: {result['ground_truth']}\n")
        except Exception as e:
            print(f"  ✗ Skipped (generation failed): {e}\n")

    print("=" * 70)
    print(f"Generated {len(questions)} questions from {attempted} attempted chunks")
    print("=" * 70)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved to {output_path}")
    print("  Review the questions before running evaluate_api.py")

    mysql.close()


if __name__ == "__main__":
    main()
