#!/usr/bin/env python3
"""
Auto-generate evaluation questions from indexed document chunks.
Uses Gemini or Groq to create question + ground_truth pairs from random MySQL chunks,
then saves them to data/eval_questions.json.

Usage:
  docker compose run --rm backend python -m scripts.generate_eval_questions
  docker compose run --rm backend python -m scripts.generate_eval_questions --judge groq
  docker compose run --rm backend python -m scripts.generate_eval_questions --count 20
  docker compose run --rm backend python -m scripts.generate_eval_questions --output data/my_questions.json
"""
import os
import sys
import json
import argparse
import random
import re
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from database.mysql_handler import MySQLHandler
from config import Config

try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


GENERATION_PROMPT = """Aşağıda bir Türk sağlık sigortası belgesinden alınmış bir metin parçası verilmiştir.

METİN:
{chunk_text}

Bu metni dikkatlice oku. Yalnızca bu metinden yanıtlanabilecek, spesifik ve anlamlı bir soru yaz.
Ardından, yalnızca bu metne dayanarak kısa ve doğru bir cevap yaz.

Yanıtını aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{
  "question": "<Türkçe soru>",
  "ground_truth": "<Türkçe cevap, 1-3 cümle>"
}}

Kurallar:
- Soru yalnızca verilen metinden cevaplanabilir olmalı
- "Bu metne göre" veya "Metinde" gibi ifadeler kullanma
- Genel, belirsiz sorular sorma ("Bu metin ne hakkında?" gibi)
- Cevap doğrudan ve özlü olmalı
"""


def get_random_chunks(mysql: MySQLHandler, count: int, min_length: int = 200) -> list:
    """Fetch random chunks from MySQL with minimum text length."""
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
            (min_length, count * 3)  # fetch extra to account for failures
        )
        rows = mysql.cursor.fetchall()
        random.shuffle(rows)
        return rows
    except Exception as e:
        print(f"✗ Error fetching chunks: {e}")
        return []


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)
    if "question" not in parsed or "ground_truth" not in parsed:
        raise ValueError(f"Unexpected response format: {parsed}")
    return parsed


def generate_with_gemini(client, model: str, chunk_text: str) -> dict:
    prompt = GENERATION_PROMPT.format(chunk_text=chunk_text[:1500])
    response = client.models.generate_content(model=model, contents=prompt)
    return parse_json_response(response.text)


def generate_with_groq(client, model: str, chunk_text: str) -> dict:
    prompt = GENERATION_PROMPT.format(chunk_text=chunk_text[:1500])
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return parse_json_response(response.choices[0].message.content)


def main():
    parser = argparse.ArgumentParser(description="Generate eval questions from indexed chunks")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of questions to generate (default: 10)")
    parser.add_argument("--output", default="data/eval_questions.json",
                        help="Output path (default: data/eval_questions.json)")
    parser.add_argument("--judge", choices=["gemini", "groq"], default="groq",
                        help="LLM provider to use (default: groq)")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MAHIKS-TR: Eval Question Generator")
    print("=" * 70)
    print(f"Start:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Judge:    {args.judge}")
    print(f"Target:   {args.count} questions")
    print(f"Output:   {args.output}")
    print("=" * 70 + "\n")

    Config.validate()

    # Init judge client
    if args.judge == "groq":
        if not OPENAI_AVAILABLE:
            print("✗ openai package not installed.")
            sys.exit(1)
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            print("✗ GROQ_API_KEY not set in .env")
            sys.exit(1)
        judge_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        generate_fn = generate_with_groq
        sleep_seconds = 2  # Groq free tier: 30 req/min
        print(f"Model:    {judge_model}")
    else:
        if not GEMINI_AVAILABLE:
            print("✗ google-genai not installed.")
            sys.exit(1)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("✗ GOOGLE_API_KEY not set in .env")
            sys.exit(1)
        judge_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        client = google_genai.Client(api_key=google_api_key)
        generate_fn = generate_with_gemini
        sleep_seconds = 13  # Gemini free tier: 5 req/min
        print(f"Model:    {judge_model}")

    # Connect to MySQL
    mysql = MySQLHandler(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE
    )

    total_chunks = mysql.get_chunk_count()
    print(f"\nTotal chunks in DB: {total_chunks}")
    if total_chunks == 0:
        print("✗ No chunks found. Run vectorize_only first.")
        mysql.close()
        sys.exit(1)

    chunks = get_random_chunks(mysql, args.count)
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
        chunk_preview = chunk['chunk_text'][:80].replace('\n', ' ')
        print(f"[{len(questions)+1}/{args.count}] Chunk {chunk['id']} — \"{chunk_preview}...\"")

        try:
            time.sleep(sleep_seconds)
            result = generate_fn(client, judge_model, chunk['chunk_text'])
            questions.append({
                "id": len(questions) + 1,
                "question": result["question"],
                "ground_truth": result["ground_truth"],
                "source_chunk_id": chunk['id'],
                "source_name": chunk['source_name']
            })
            print(f"  Q: {result['question']}")
            print(f"  A: {result['ground_truth']}\n")
        except Exception as e:
            print(f"  ✗ Skipped (generation failed): {e}\n")

    print("=" * 70)
    print(f"Generated {len(questions)} questions from {attempted} chunks")
    print("=" * 70)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved to {output_path}")
    print("  Review the questions before running evaluate_rag.py")

    mysql.close()


if __name__ == "__main__":
    main()
