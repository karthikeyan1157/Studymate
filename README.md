# StudyMate & ExamPrep AI

Two premium AI applications built using Llama 3.3 70B (via Groq), FastAPI, and Streamlit. Features deep chain-of-thought reasoning, custom UI components, and RAG capabilities.

## 1. StudyMate (AI Agent)
A powerful standalone AI assistant that features **Chain-of-Thought Reasoning** (inspired by OpenAI o1 / DeepSeek-R1). The AI reasons through complex problems inside a `<think>` tag before generating its final answer.

Features:
- **6 Specialist Modes**: Chat, Code, Think, Create, Write, Humor.
- **Deep Reasoning**: Collapsible `🧠 Thought process` expander showing internal logic.
- **Image Generation**: Uses Pollinations.ai (Flux) seamlessly for text-to-image.
- **Diagram Generation**: AI can spawn interactive Mermaid.js diagrams out of thin air.
- **Security Hardened**: Rate limits, secret masking, input validation.

Run:
```bash
cd ai-agent
streamlit run app.py --server.port 8502
```

## 2. ExamPrep AI Chatbot
An AI tutoring assistant designed to test knowledge using Retrieval-Augmented Generation (RAG).

Features:
- **Knowledge Base Integration**: Retrieves top chunks of data to give factual, syllabus-aligned answers.
- **Trained Persona**: Answers strictly using real-world analogies, memory tricks, and specific references to `[KB-N]` chunks.
- **FastAPI backend**: Fast semantic search.

Run Backend:
```bash
uvicorn exam-prep-chatbot.backend.main:app --app-dir . --port 8000
```
Run Frontend:
```bash
streamlit run exam-prep-chatbot/frontend/app.py --server.port 8501
```

## Setup & Environment
1. Clone this repository.
2. Initialize virtual environment: `python3 -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Setup Groq API keys securely inside `.streamlit/secrets.toml` or fallback to `.env`. See `.env.example`.
