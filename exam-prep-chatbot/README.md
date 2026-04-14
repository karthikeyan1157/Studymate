# 🎓 ExamPrep AI — Semantic Exam Prep Chatbot

A full-stack AI-powered exam prep chatbot that uses **semantic vector search** to find relevant past exam questions and an **LLM** to explain concepts, present practice questions, and evaluate student answers with personalized feedback.

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────┐
│           Streamlit Frontend             │
│   (chat UI · practice questions · score) │
└───────────────────┬──────────────────────┘
                    │ HTTP (port 8000)
┌───────────────────▼──────────────────────┐
│           FastAPI Backend                │
│                                          │
│  1. Embed query (sentence-transformers) │
│  2. Semantic search → Endee             │
│  3. Build LLM prompt with context       │
│  4. Stream reply (Groq / OpenAI)        │
└──────────┬───────────────────┬──────────┘
           │                   │
  ┌────────▼────────┐  ┌───────▼────────┐
  │  Endee Vector DB│  │  LLM API       │
  │  (port 8080)    │  │  Groq / OpenAI │
  │                 │  │                │
  │ • question text │  │ • explain      │
  │ • topic/subopic │  │ • evaluate     │
  │ • difficulty    │  │ • hint         │
  │ • answer        │  │                │
  └─────────────────┘  └────────────────┘
```

## 📁 Folder Structure

```
exam-prep-chatbot/
├── data/
│   └── questions.json          # 40 curated exam questions
├── scripts/
│   └── ingest.py               # Embed + load questions into Endee
├── backend/
│   └── main.py                 # FastAPI app (3 endpoints)
├── frontend/
│   └── app.py                  # Streamlit chat UI
├── .env.example                # Environment variable template
├── requirements.txt
└── README.md
```

---

## ⚡ Tech Stack

| Layer        | Tool                              |
|-------------|-----------------------------------|
| Vector DB    | [Endee](https://endee.io/)       |
| Embeddings   | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local) |
| LLM          | Groq `llama-3.3-70b-versatile` (default) or OpenAI GPT-4o |
| Backend      | FastAPI + Uvicorn                |
| Frontend     | Streamlit                        |
| Data         | 40 curated ML/CS/DS/OS/Networks exam Q&As |

---

## 🚀 Setup Instructions

### 1. Clone & Create Virtual Environment

```bash
git clone <repo-url>
cd exam-prep-chatbot
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (or OPENAI_API_KEY)
```

Get a **free Groq API key** at → https://console.groq.com

### 3. Install & Start Endee

Endee is a self-hosted vector database (single binary, no Docker needed):

```bash
# Download and install (Linux, AVX2)
curl -O https://raw.githubusercontent.com/endee-io/endee/master/install.sh
curl -O https://raw.githubusercontent.com/endee-io/endee/master/run.sh
chmod +x install.sh run.sh
./install.sh --release --avx2

# Start Endee (runs on port 8080)
./run.sh
```

> **Cloud option:** Use [app.endee.io](https://app.endee.io/) and set `ENDEE_AUTH_TOKEN` in your `.env`.

### 4. Ingest Questions into Endee

> Make sure Endee is running before this step.

```bash
python scripts/ingest.py
# Output: 🎉 Successfully indexed 40 questions into Endee index 'exam_questions'!
```

### 5. Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
# Visit http://localhost:8000/docs for the Swagger UI
```

### 6. Start the Frontend

In a new terminal:

```bash
streamlit run frontend/app.py
# Opens at http://localhost:8501
```

---

## 💬 Example Queries

| Student Query | What Happens |
|---|---|
| *"Explain overfitting"* | Retrieves 5 related ML questions, explains bias-variance tradeoff |
| *"How does BFS differ from DFS?"* | Finds graph traversal questions, explains with complexity |
| *"What is L1 regularization?"* | Surfaces Lasso/Ridge questions for practice |
| *"Explain the TCP handshake"* | Finds networking questions, explains 3-way handshake |

---

## 🎯 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ask` | Main chatbot — embed, retrieve, explain |
| `POST` | `/evaluate` | Grade student answer, return feedback |
| `GET`  | `/topics` | List available topics + difficulties |
| `GET`  | `/health` | Check LLM provider + status |

### `/ask` Request Body
```json
{
  "query": "Explain gradient descent",
  "topic": "Machine Learning",     // optional filter
  "difficulty": "medium"           // optional filter
}
```

### `/evaluate` Request Body
```json
{
  "question": "What is L1 regularization?",
  "student_answer": "It adds absolute values of weights",
  "correct_answer": "L1 adds absolute value of weights, producing sparse models..."
}
```

---

## 📊 Question Bank

The dataset (`data/questions.json`) covers 40 curated exam questions across:

| Subject | Questions | Difficulties |
|---------|-----------|-------------|
| Machine Learning | 12 | Easy / Medium / Hard |
| Deep Learning | 7 | Easy / Medium / Hard |
| Data Structures | 6 | Easy / Medium |
| Algorithms | 6 | Easy / Medium / Hard |
| Operating Systems | 5 | Easy / Medium |
| Computer Networks | 5 | Easy / Medium / Hard |

---

## 🔮 How Endee is Used

1. **Indexing** — `ingest.py` embeds each question's text using `all-MiniLM-L6-v2` and upserts 384-dimensional vectors into an Endee index named `exam_questions`.
2. **Retrieval** — When a student asks a question, the query is embedded and `index.query(top_k=5)` finds the most semantically similar past exam questions.
3. **Filtering** — The Endee filter API (`{"topic": {"$eq": "Machine Learning"}}`) allows topic/difficulty-scoped retrieval.
4. **Context** — Retrieved questions + answers are injected into the LLM prompt as RAG context.

---

## 🚧 Future Improvements

- [ ] Student progress tracking (per-topic performance over time)
- [ ] Upload custom question sets (PDF/CSV ingestion)
- [ ] Difficulty progression (auto-advance easy → medium → hard)
- [ ] Hint system ("give me a hint without the full answer")
- [ ] Multi-subject expansion (Math, Biology, Physics)
- [ ] Voice input for accessibility
