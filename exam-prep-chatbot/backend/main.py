"""
backend/main.py — FastAPI backend for the Exam Prep Chatbot.
Uses ChromaDB (local persistent) for vector search.

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import chromadb

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
DB_PATH      = str(Path(__file__).parent.parent / "chroma_db")
COLLECTION   = "exam_questions"

# ── LLM client ────────────────────────────────────────────────────────────────
if LLM_PROVIDER == "openai":
    from openai import OpenAI
    llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    LLM_MODEL  = "gpt-4o"
else:
    from groq import Groq
    llm_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    LLM_MODEL  = "llama-3.3-70b-versatile"

# ── ChromaDB + Embeddings ─────────────────────────────────────────────────────
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection    = chroma_client.get_collection(name=COLLECTION)
embed_model   = SentenceTransformer("all-MiniLM-L6-v2")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Exam Prep Chatbot API",
    description="Semantic question retrieval + LLM-powered exam tutoring",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────
class AskRequest(BaseModel):
    query:      str
    topic:      Optional[str] = None
    difficulty: Optional[str] = None
    top_k:      int = 10

class AskResponse(BaseModel):
    reply:           str
    questions:       list[dict]
    retrieved_count: int
    concept:         str    # short concept name for image generation

class EvaluateRequest(BaseModel):
    question:       str
    student_answer: str
    correct_answer: str

class EvaluateResponse(BaseModel):
    score:      int   # 1–10
    feedback:   str
    hint:       str
    is_correct: bool

# ── Helper: call LLM ──────────────────────────────────────────────────────────
def call_llm(messages: list[dict], temperature: float = 0.7, max_tokens: int = 2000) -> str:
    resp = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


# ── Helper: build ChromaDB where-filter ──────────────────────────────────────
def build_where(topic: Optional[str], difficulty: Optional[str]) -> Optional[dict]:
    conditions = []
    if topic:
        conditions.append({"topic": {"$eq": topic}})
    if difficulty:
        conditions.append({"difficulty": {"$eq": difficulty}})

    if len(conditions) == 0:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 0. Smart intent detection — handle greetings/casual chat naturally
    CASUAL_PATTERNS = [
        r"^(hi|hello|hey|howdy|hiya|sup|yo|greetings|good\s*(morning|afternoon|evening|night))[!?.]*$",
        r"^(how are you|how's it going|what'?s up|how do you do)[!?.]*$",
        r"^(thanks|thank you|thx|ty|cheers)[!?.]*$",
        r"^(ok|okay|sure|alright|cool|got it|nice|great|awesome)[!?.]*$",
        r"^(bye|goodbye|see you|cya)[!?.]*$",
        r"^who are you[?!.]*$",
        r"^what can you do[?!.]*$",
        r"^help[?!.]*$",
    ]
    import re
    q_lower = req.query.strip().lower()
    is_casual = any(re.match(p, q_lower) for p in CASUAL_PATTERNS) or len(q_lower.split()) < 3

    if is_casual:
        casual_system = (
            "You are ExamPrep AI — a friendly, smart exam preparation assistant. "
            "You help students with any academic subject. Be warm, natural, and conversational. "
            "Keep responses concise and friendly. If the student greets you, greet them back warmly "
            "and let them know what you can help with."
        )
        reply = call_llm(
            [{"role": "system", "content": casual_system},
             {"role": "user",   "content": req.query.strip()}],
            temperature=0.8, max_tokens=300
        )
        return AskResponse(reply=reply, questions=[], retrieved_count=0, concept="")

    # 1. Embed query
    vector = embed_model.encode(req.query).tolist()

    # 2. Query ChromaDB
    where = build_where(req.topic, req.difficulty)
    query_kwargs: dict = {
        "query_embeddings": [vector],
        "n_results": req.top_k,
        "include": ["metadatas", "documents", "distances"],
    }
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)
    metadatas = results.get("metadatas", [[]])[0]

    if not metadatas:
        # Fallback: LLM answers from own knowledge (no RAG)
        fallback_system = (
            "You are ExamPrep AI — a brilliant exam tutor. Answer the student's question "
            "thoroughly from your own knowledge. Structure the answer clearly with examples."
        )
        reply = call_llm(
            [{"role": "system", "content": fallback_system},
             {"role": "user",   "content": req.query.strip()}],
            temperature=0.7, max_tokens=1500
        )
        concept = call_llm(
            [{"role": "user", "content": f'2-5 word concept name for: "{req.query}". Only output the concept.'}],
            temperature=0.1, max_tokens=20
        ).strip()
        return AskResponse(reply=reply, questions=[], retrieved_count=0, concept=concept)


    # 3. Build rich training context
    context_lines = []
    for i, m in enumerate(metadatas[:10], 1):
        topic = m.get('topic', 'General')
        subtopic = m.get('subtopic', '')
        diff = m.get('difficulty', 'medium')
        context_lines.append(
            f"[KB-{i}] Topic: {topic}{' > ' + subtopic if subtopic else ''} | Difficulty: {diff}\n"
            f"Q: {m.get('question', '')}\n"
            f"A: {m.get('answer', '')}"
        )
    context = "\n\n".join(context_lines)
    topics_covered = list({m.get('topic', 'General') for m in metadatas})

    system_prompt = f"""
You are ExamPrep AI — a world-class exam preparation tutor trained on a curated knowledge base
of real exam questions and expert model answers.

You have been trained on questions covering: {', '.join(topics_covered)}.
For this query, you retrieved {len(metadatas)} highly relevant Q&A pairs from your knowledge base.

Your mission: Deliver the most thorough, memorable, exam-ready explanation possible.
You genuinely care about this student passing their exam.

Your trained capabilities:
- Deep knowledge of every question in your knowledge base
- Ability to connect this exact concept to past exam patterns
- Predicting what the examiner REALLY wants to see
- Knowing the top traps students fall into on this topic
- Making any concept unforgettable with the right analogy
"""

    user_prompt = f"""Student query: \"{req.query}\"

Your Knowledge Base retrieved {len(metadatas)} relevant Q&A pairs:
{context}

Deliver an OUTSTANDING, exam-winning response:

## 🧠 Concept Explanation
Explain in 4-6 powerful sentences. Start from first principles, then build. **Bold** all key terms.
Be authoritative — you KNOW this topic deeply from your training data.

## 🌐 Real-World Analogy
One vivid, memorable analogy from everyday life that makes this click instantly.

## 🔑 Key Exam Takeaways
- **[Term]:** [crisp definition]
- **[Term]:** [crisp definition]
- **[Term]:** [crisp definition]
- **⚠️ Exam Trap:** [the #1 mistake examiners catch students on]

## 💡 Memory Trick
One powerful mnemonic, acronym, or mental image to lock this in forever.

## 🧪 From Your Knowledge Base — Practice Questions
Here are questions directly from the trained knowledge base:

**[KB-1]:** [question from KB-1 above]

**[KB-2]:** [question from KB-2 above]

**[KB-3]:** [question from KB-3 above]

---
✏️ *Pick any question and type your answer — I'll score it 1-10 with expert feedback!*

Rules:
- Reference specific [KB-N] numbers when pulling questions
- Make every sentence earn its place
- End with genuine, specific encouragement based on the topic"""

    reply = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ], temperature=0.72)

    # Extract short concept name for frontend image generation
    concept = call_llm([
        {"role": "user", "content": f'State the main concept in this query in 2-5 words, no punctuation: "{req.query}". Only output the concept name.'}
    ], temperature=0.1, max_tokens=20).strip().strip('"').strip("'")

    return AskResponse(
        reply=reply,
        questions=metadatas,
        retrieved_count=len(metadatas),
        concept=concept,
    )


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest):
    if not req.student_answer.strip():
        raise HTTPException(status_code=400, detail="Student answer cannot be empty.")

    system_prompt = """
You are an expert exam marker with 20 years of experience. You are strict but deeply
encouraging. Your feedback doesn't just say what's wrong — it lights the path forward.
You score answers on both correctness AND quality of explanation.
"""
    user_prompt = f"""Evaluate this student's answer with expert precision:

**Question:** {req.question}
**Expert Model Answer:** {req.correct_answer}
**Student's Answer:** {req.student_answer}

Scoring rubric:
- 9-10: Complete, correct, well-explained. Could be used as a model answer.
- 7-8: Mostly correct with minor gaps or imprecise language.
- 5-6: Core idea present but key details missing or partially wrong.
- 3-4: Some relevant points but significant misunderstandings.
- 1-2: Fundamentally incorrect or irrelevant.

Respond with EXACTLY this JSON (no markdown, no extra text outside the JSON):
{{
  "score": <integer 1-10>,
  "is_correct": <true if score >= 7, else false>,
  "feedback": "<3-4 sentences: (1) what they got right, (2) what was missing or wrong, (3) why the correct answer matters>",
  "hint": "<One powerful study tip or the single most important fact to memorise for this topic>"
}}"""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ])

    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data  = json.loads(clean)
        return EvaluateResponse(
            score=int(data.get("score", 5)),
            feedback=data.get("feedback", ""),
            hint=data.get("hint", ""),
            is_correct=bool(data.get("is_correct", False)),
        )
    except Exception:
        return EvaluateResponse(
            score=5,
            feedback=raw[:500],
            hint="Review the model answer carefully.",
            is_correct=False,
        )


@app.get("/topics")
def get_topics():
    return {
        "topics": [
            "Machine Learning", "Deep Learning", "Data Structures",
            "Algorithms", "Operating Systems", "Computer Networks",
            "Custom",
        ],
        "difficulties": ["easy", "medium", "hard"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "llm": LLM_PROVIDER, "model": LLM_MODEL, "vector_db": "chromadb"}


@app.get("/count")
def count():
    """Return total number of questions in the vector DB."""
    return {"count": collection.count()}


class AddQuestionRequest(BaseModel):
    question:   str
    answer:     str
    topic:      str = "Custom"
    subtopic:   str = ""
    difficulty: str = "medium"


class AddQuestionResponse(BaseModel):
    success:  bool
    id:       str
    message:  str
    total:    int


@app.post("/add_question", response_model=AddQuestionResponse)
def add_question(req: AddQuestionRequest):
    """
    Embed and store a user-submitted question + answer into ChromaDB.
    The new question immediately becomes searchable for future /ask calls.
    """
    if not req.question.strip() or not req.answer.strip():
        raise HTTPException(status_code=400, detail="Both question and answer are required.")

    import uuid, time
    qid = f"user_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    vector = embed_model.encode(req.question).tolist()

    collection.upsert(
        ids=[qid],
        embeddings=[vector],
        documents=[req.question],
        metadatas=[{
            "question":   req.question.strip(),
            "answer":     req.answer.strip(),
            "topic":      req.topic,
            "subtopic":   req.subtopic,
            "difficulty": req.difficulty,
        }],
    )

    return AddQuestionResponse(
        success=True,
        id=qid,
        message=f"Question added successfully to '{req.topic}' topic!",
        total=collection.count(),
    )

