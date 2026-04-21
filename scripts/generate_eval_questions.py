#!/usr/bin/env python3
"""
Auto-generate evaluation questions from indexed document chunks.
Uses local Ollama to create question + ground_truth pairs from random MySQL chunks,
then saves them to data/eval_questions.json.

Usage:
  docker compose run --rm backend python -m scripts.generate_eval_questions
  docker compose run --rm backend python -m scripts.generate_eval_questions --count 20
  docker compose run --rm backend python -m scripts.generate_eval_questions --output data/my_questions.json
  docker compose run --rm backend python -m scripts.generate_eval_questions --model qwen2.5:14b
  docker compose run --rm backend python -m scripts.generate_eval_questions --ollama-url http://host.docker.internal:11434
"""
import sys
import json
import argparse
import random
import re
import time
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from database.mysql_handler import MySQLHandler
from config import Config


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
            (min_length, count * 3)
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
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            raise ValueError(f"No valid JSON found in response: {raw[:300]}")
    if "question" not in parsed or "ground_truth" not in parsed:
        raise ValueError(f"Unexpected response format: {parsed}")
    return parsed


def generate_with_ollama(ollama_url: str, model: str, chunk_text: str,
                         retries: int = 2) -> dict:
    prompt = GENERATION_PROMPT.format(chunk_text=chunk_text[:1500])
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=180,
            )
            if response.status_code != 200:
                raise Exception(f"Ollama returned HTTP {response.status_code}")
            content = response.json().get('message', {}).get('content', '')
            return parse_json_response(content)
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(2)
    raise last_error


def main():
    parser = argparse.ArgumentParser(description="Generate eval questions from indexed chunks using local Ollama")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of questions to generate (default: 10)")
    parser.add_argument("--output", default="data/eval_questions.json",
                        help="Output path (default: data/eval_questions.json)")
    parser.add_argument("--model", default=None,
                        help="Ollama model to use (default: OLLAMA_MODEL from config)")
    parser.add_argument("--ollama-url", default=None,
                        help="Ollama base URL (default: OLLAMA_BASE_URL from config)")
    args = parser.parse_args()

    Config.validate()

    ollama_url = args.ollama_url or Config.OLLAMA_BASE_URL
    model = args.model or Config.OLLAMA_MODEL

    print("\n" + "=" * 70)
    print("MAHIKS-TR: Eval Question Generator")
    print("=" * 70)
    print(f"Start:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model:      {model} (local Ollama)")
    print(f"Ollama URL: {ollama_url}")
    print(f"Target:     {args.count} questions")
    print(f"Output:     {args.output}")
    print("=" * 70 + "\n")

    mysql = MySQLHandler(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE
    )

    total_chunks = mysql.get_chunk_count()
    print(f"Total chunks in DB: {total_chunks}")
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
            result = generate_with_ollama(ollama_url, model, chunk['chunk_text'])
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
    print("  Review the questions before running scripts.evaluate")

    mysql.close()


if __name__ == "__main__":
    main()
