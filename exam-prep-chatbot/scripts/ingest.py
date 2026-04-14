#!/usr/bin/env python3
"""
ingest.py — Embeds exam questions and loads them into ChromaDB (local, no server needed).
Run once after setting up .env.

Usage:
    python scripts/ingest.py
"""

import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
import chromadb

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH   = Path(__file__).parent.parent / "data" / "questions.json"
DB_PATH     = Path(__file__).parent.parent / "chroma_db"   # persisted locally
COLLECTION  = "exam_questions"
BATCH_SIZE  = 16

# ── Load embedding model ──────────────────────────────────────────────────────
print("🤖 Loading embedding model (all-MiniLM-L6-v2)…")
model = SentenceTransformer("all-MiniLM-L6-v2")

# ── Load questions ────────────────────────────────────────────────────────────
with open(DATA_PATH) as f:
    questions = json.load(f)
print(f"📄 Loaded {len(questions)} questions from {DATA_PATH}")

# ── Connect to ChromaDB (persistent, local) ───────────────────────────────────
print(f"🗄️  Opening ChromaDB at {DB_PATH}")
client = chromadb.PersistentClient(path=str(DB_PATH))

# Drop + recreate collection for a clean ingest
try:
    client.delete_collection(COLLECTION)
    print(f"⚠️  Old collection '{COLLECTION}' deleted — re-indexing…")
except Exception:
    pass

collection = client.create_collection(
    name=COLLECTION,
    metadata={"hnsw:space": "cosine"},
)
print(f"✅ Collection '{COLLECTION}' created")

# ── Embed and upsert in batches ───────────────────────────────────────────────
total = 0
for i in range(0, len(questions), BATCH_SIZE):
    batch = questions[i : i + BATCH_SIZE]
    texts = [q["question"] for q in batch]

    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    collection.upsert(
        ids=[q["id"] for q in batch],
        embeddings=embeddings,
        documents=[q["question"] for q in batch],
        metadatas=[
            {
                "question":   q["question"],
                "answer":     q["answer"],
                "topic":      q["topic"],
                "subtopic":   q.get("subtopic", ""),
                "difficulty": q.get("difficulty", "medium"),
            }
            for q in batch
        ],
    )
    total += len(batch)
    print(f"   Upserted {total}/{len(questions)} questions…")

print(f"\n🎉 Successfully indexed {total} questions into ChromaDB collection '{COLLECTION}'!")
print("   You can now start the backend:  uvicorn backend.main:app --reload")
