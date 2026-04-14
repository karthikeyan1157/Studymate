"""
StudyMate - Premium AI Assistant with Chain-of-Thought Reasoning
6 specialist modes, visible reasoning traces, Claude-quality responses.
Run: streamlit run app.py --server.port 8502
"""

import os
import re
import requests as req_lib
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="StudyMate",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load API key: Streamlit secrets (most secure) > .env fallback
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = "llama-3.3-70b-versatile"

# ── Reasoning instruction appended to ALL modes ────────────────────────────────
THINK_INSTRUCTION = """

---
REASONING PROTOCOL — apply to every non-trivial response:

Before writing your final answer, reason through the problem inside <think> tags.
In your thinking, freely explore:
- What exactly is being asked, and any ambiguity
- Multiple angles, approaches, or interpretations
- Potential errors, edge cases, counter-arguments
- The single best approach before committing

Skip the <think> block only for greetings or one-word factual answers.

Always format your full response exactly like this:
<think>
[Raw, honest, thorough reasoning — think out loud here]
</think>

[Polished, complete, well-structured final answer]

Only the text AFTER </think> is shown to the user as your answer.
"""


# Groq model fallback chain (fastest/lightest last)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # primary — best quality
    "llama-3.1-8b-instant",      # fallback 1 — faster, higher rate limit
    "gemma2-9b-it",              # fallback 2 — different provider sub
]


# ── Security Configuration ───────────────────────────────────────────────────
MAX_INPUT_LENGTH   = 2000   # Max chars per user message
MAX_REQUESTS_MIN   = 15     # Max messages per minute per session
MAX_HISTORY_TURNS  = 30     # Max stored messages per mode

def mask_secret(text: str, secret: str) -> str:
    """Remove any accidental API key leakage from error messages."""
    if secret and len(secret) > 8:
        return text.replace(secret, "***HIDDEN***")
    return text

def check_session_rate_limit() -> bool:
    """Return True if within rate limit, False if exceeded."""
    import time
    now = time.time()
    times = st.session_state.get("_req_times", [])
    # Keep only last 60 seconds
    times = [t for t in times if now - t < 60]
    if len(times) >= MAX_REQUESTS_MIN:
        st.session_state["_req_times"] = times
        return False
    times.append(now)
    st.session_state["_req_times"] = times
    return True

def sanitize_input(text: str) -> str:
    """Trim, length-cap, and strip dangerous patterns from user input."""
    text = text.strip()[:MAX_INPUT_LENGTH]
    # Remove null bytes and control chars (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text

def call_groq(messages, temperature=0.8, max_tokens=3000, _attempt=0):
    """Call Groq API with automatic retry + model fallback on 429 rate limits."""
    import time
    if not GROQ_API_KEY:
        return "API key not configured. Add GROQ_API_KEY to .streamlit/secrets.toml"

    model = GROQ_MODELS[min(_attempt, len(GROQ_MODELS) - 1)]
    # Use smaller token budget on fallback models to stay within limit
    effective_tokens = max_tokens if _attempt == 0 else min(max_tokens, 2048)

    try:
        r = req_lib.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": effective_tokens,
            },
            timeout=120,
        )

        # Handle rate limit — wait and retry with next model
        if r.status_code == 429:
            if _attempt < len(GROQ_MODELS) - 1:
                wait = 15 * (_attempt + 1)   # 15s, 30s
                time.sleep(wait)
                return call_groq(messages, temperature, max_tokens, _attempt + 1)
            return (
                "**Rate limit reached** — Groq free tier limit hit. "
                "Please wait 60 seconds and try again, or use shorter messages."
            )

        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    except req_lib.exceptions.Timeout:
        return "Request timed out. Please try again."
    except Exception as e:
        err = str(e)
        if "429" in err and _attempt < len(GROQ_MODELS) - 1:
            import time
            time.sleep(15)
            return call_groq(messages, temperature, max_tokens, _attempt + 1)
        return mask_secret(f"Error: {err}", GROQ_API_KEY)



def parse_response(raw: str):
    """Split LLM output into (thinking_trace | None, final_answer)."""
    m = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
    if not m:
        return None, raw.strip()
    thinking = m.group(1).strip()
    answer = raw[m.end():].strip()
    return (thinking, answer) if answer else (None, raw.strip())


# ── Image Generation ─────────────────────────────────────────────────────
IMG_KEYWORDS = [
    "generate image", "create image", "make image", "draw",
    "generate a picture", "create a picture", "generate picture",
    "generate a photo", "create a photo", "generate photo",
    "paint", "illustrate", "visualize", "render", "sketch",
    "generate art", "create art", "make art", "make a picture",
    "make a photo", "make a drawing", "make drawing",
    "show me a picture", "show me an image", "show me a photo",
    "image of", "picture of", "photo of", "artwork of",
]

def is_image_request(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in IMG_KEYWORDS)

def build_image_prompt(user_query: str) -> str:
    """Use LLM to craft a rich Stable Diffusion / Flux style prompt."""
    msgs = [
        {
            "role": "system",
            "content": (
                "You are an expert AI image prompt engineer specializing in Flux/Stable Diffusion prompts. "
                "Given a user's image request, output ONLY a single, richly detailed prompt string. "
                "Include: subject, art style, lighting, colour palette, mood, camera/perspective, and quality tags. "
                "Do NOT include explanations, labels, or preamble. Just the prompt text. Max 120 words."
            ),
        },
        {"role": "user", "content": f"Create an image generation prompt for: {user_query}"},
    ]
    return call_groq(msgs, temperature=0.75, max_tokens=200)

def fetch_image_bytes(prompt: str):
    """Download image from Pollinations.ai. Returns bytes or None on failure."""
    import urllib.parse
    encoded = urllib.parse.quote(prompt, safe="")
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        "?width=1024&height=768&model=flux&nologo=true&enhance=true"
    )
    try:
        resp = req_lib.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content, url
    except Exception as e:
        return None, str(e)


# ── Diagram Generation ────────────────────────────────────────────────────────
DIAGRAM_KEYWORDS = [
    "diagram", "flowchart", "flow chart", "mindmap", "mind map",
    "chart", "graph", "visualize", "visualise", "visualization",
    "draw a diagram", "create a diagram", "generate a diagram",
    "show a diagram", "make a diagram", "show a flowchart",
    "architecture diagram", "sequence diagram", "erd", "uml",
    "tree diagram", "hierarchy", "process flow", "workflow",
]

def is_diagram_request(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in DIAGRAM_KEYWORDS)

def generate_diagram_code(topic: str) -> str:
    """Ask LLM to produce a Mermaid diagram for the topic."""
    msgs = [
        {
            "role": "system",
            "content": (
                "You are a diagram expert. Generate a clear, well-structured Mermaid diagram "
                "for the given topic. Choose the best diagram type (flowchart, mindmap, graph, etc.). "
                "Output ONLY a valid Mermaid code block like:\n"
                "```mermaid\n<diagram code here>\n```\n"
                "No explanations before or after the code block. "
                "Keep node labels short (3-5 words max). Ensure valid Mermaid syntax."
            ),
        },
        {"role": "user", "content": f"Create a Mermaid diagram for: {topic}"},
    ]
    return call_groq(msgs, temperature=0.3, max_tokens=800)

def extract_mermaid(raw: str) -> str | None:
    """Extract Mermaid code from ```mermaid ... ``` block."""
    m = re.search(r"```mermaid\s*(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: if raw starts with a known mermaid keyword
    for kw in ("graph", "flowchart", "mindmap", "sequenceDiagram", "erDiagram", "classDiagram"):
        if raw.strip().startswith(kw):
            return raw.strip()
    return None

def render_mermaid(code: str) -> str:
    """Return an HTML string that renders a Mermaid diagram via CDN."""
    escaped = code.replace("`", "&#96;").replace("\\", "\\\\").replace("\n", "\\n")
    return f"""
<div style="background:#0d0c22;border:1px solid rgba(147,51,234,.3);border-radius:14px;
            padding:1.5rem;margin:.5rem 0;overflow-x:auto;">
  <div class="mermaid" style="font-size:14px;">{code}</div>
</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {{
      primaryColor: '#7c3aed',
      primaryTextColor: '#e8e8ff',
      primaryBorderColor: '#9333ea',
      lineColor: '#a855f7',
      secondaryColor: '#1e1e3a',
      tertiaryColor: '#111124',
      background: '#0d0c22',
      mainBkg: '#111124',
      nodeBorder: '#9333ea',
      clusterBkg: '#16162e',
      titleColor: '#e8e8ff',
      edgeLabelBackground: '#1e1e3a',
      fontFamily: 'Inter, sans-serif',
    }}
  }});
</script>
"""

MODES = {
    "Chat": {
        "icon": "💬",
        "color": "#a855f7",
        "gradient": "linear-gradient(135deg,#7c3aed,#a855f7)",
        "placeholder": "Ask me anything — facts, opinions, science, philosophy, life…",
        "temp": 0.8,
        "system": (
            "You are an exceptionally intelligent AI assistant — curious, warm, and uncommonly wise.\n"
            "You combine deep knowledge across all domains with the ability to make anything clear.\n\n"
            "Think of yourself as a brilliant friend who knows everything: give real, specific answers\n"
            "based on the actual situation — not overly cautious boilerplate. Be direct and confident,\n"
            "but honest about genuine uncertainty with 'I'm not certain, but...' rather than hedging.\n\n"
            "Core traits:\n"
            "- Intellectually curious: you find genuine interest in whatever topic comes up\n"
            "- Comprehensive when depth matters; concise when brevity is better\n"
            "- Warm and human — you have personality, opinions, and a sense of humour\n"
            "- You adapt tone: formal for serious topics, relaxed for casual chat\n"
            "- If someone says hi, say hi back warmly and ask what's on their mind\n\n"
            "Never start with 'Certainly!' or 'Great question!' — just answer naturally."
            + THINK_INSTRUCTION
        ),
    },
    "Code": {
        "icon": "💻",
        "color": "#10b981",
        "gradient": "linear-gradient(135deg,#059669,#10b981)",
        "placeholder": "Write, debug, explain, or optimize code in any language…",
        "temp": 0.3,
        "system": (
            "You are a brilliant senior software engineer with 15+ years experience across\n"
            "all programming languages, frameworks, algorithms, and system design patterns.\n\n"
            "You don't just write code — you TEACH through it. Every non-trivial piece includes:\n"
            "1. A brief explanation of your approach and why you chose it\n"
            "2. Clean, well-commented, production-ready code\n"
            "3. A working usage example\n"
            "4. Notes on edge cases, performance, or alternatives\n\n"
            "Code quality standards:\n"
            "- Idiomatic style for the language (Pythonic Python, modern JS, etc.)\n"
            "- Meaningful variable names; error handling where it matters\n"
            "- No unnecessary complexity\n\n"
            "When debugging: root cause first, then explain, then fix.\n"
            "Always format code in markdown code blocks with language specified."
            + THINK_INSTRUCTION
        ),
    },
    "Think": {
        "icon": "🧠",
        "color": "#f59e0b",
        "gradient": "linear-gradient(135deg,#d97706,#f59e0b)",
        "placeholder": "Any complex problem, decision, or question to reason through…",
        "temp": 0.6,
        "system": (
            "You are an expert at structured, rigorous reasoning — combining the thoroughness of a\n"
            "scientist, the precision of a philosopher, and the wisdom of a strategist.\n\n"
            "For any problem, you:\n"
            "1. Clarify — restate exactly what's being asked, note ambiguities\n"
            "2. Decompose — break into component sub-problems\n"
            "3. Reason — work through each piece explicitly, showing logic\n"
            "4. Challenge — steelman the alternative view; devil's advocate yourself\n"
            "5. Synthesize — clear conclusion\n"
            "6. Caveat — important uncertainties or assumptions\n\n"
            "You think out loud. Use headers, numbered steps, and bold key terms.\n"
            "Never pretend certainty; commit to conclusions when warranted."
            + THINK_INSTRUCTION
        ),
    },
    "Create": {
        "icon": "🎨",
        "color": "#f43f5e",
        "gradient": "linear-gradient(135deg,#e11d48,#f43f5e)",
        "placeholder": "Ideas, stories, world-building, brainstorming, art direction…",
        "temp": 1.0,
        "system": (
            "You are a visionary creative director with mastery across storytelling, design,\n"
            "games, products, and all creative domains. Your ideas are original, unexpected,\n"
            "and specific — never vague, clichéd, or predictable.\n\n"
            "Creative philosophy:\n"
            "- Constraints fuel creativity\n"
            "- The first idea is never the best — push further\n"
            "- Specific > generic always\n"
            "- Surprise is the soul of creativity\n\n"
            "When generating ideas: give 3-5 genuinely different options, each with a distinctive angle.\n"
            "When writing fiction: show don't tell, use sensory details, give characters real voices.\n"
            "When brainstorming: quantity first, then depth on the best.\n"
            "Make it vivid. Original. Memorable."
            + THINK_INSTRUCTION
        ),
    },
    "Write": {
        "icon": "✍️",
        "color": "#60a5fa",
        "gradient": "linear-gradient(135deg,#2563eb,#60a5fa)",
        "placeholder": "Draft emails, essays, cover letters, or paste text to edit…",
        "temp": 0.7,
        "system": (
            "You are a master writer and editor combining clarity, precision, and elegance.\n"
            "You write like the best writers: direct, vivid, with rhythm and purpose.\n\n"
            "Writing principles:\n"
            "- Every sentence earns its place — no filler, no padding, no corporate speak\n"
            "- Active voice; concrete over abstract; specific over vague\n"
            "- Vary sentence length for rhythm — short for impact. Longer to build and develop.\n"
            "- The first sentence is crucial — make it land\n"
            "- Know when to break the rules (and why)\n\n"
            "When WRITING: produce complete, polished work — not outlines.\n"
            "When EDITING: show before/after with explanation of each significant change.\n"
            "Match tone to context — formal for business, personal for casual."
            + THINK_INSTRUCTION
        ),
    },
    "Humor": {
        "icon": "😄",
        "color": "#fb923c",
        "gradient": "linear-gradient(135deg,#ea580c,#fb923c)",
        "placeholder": "Jokes, roasts, witty replies, puns, absurdist scenarios…",
        "temp": 1.0,
        "system": (
            "You are a genuinely funny AI with the wit of a great stand-up comedian and the\n"
            "intelligence of a satirist. Your humor is smart, original, and never cheap.\n\n"
            "Comedy toolkit:\n"
            "- Wit and wordplay: puns done well, double meanings, linguistic cleverness\n"
            "- Observational: the absurd truth in everyday situations\n"
            "- Absurdist: taking logic to its delightfully ridiculous conclusion\n"
            "- Dry humor: saying something insane with complete deadpan seriousness\n"
            "- Self-aware: the AI comedy situation is actually rich material\n\n"
            "Rules:\n"
            "- Never punch down\n"
            "- Don't explain the joke (unless that IS the joke)\n"
            "- Be genuinely funny, not just humor-shaped\n"
            "- If asked to roast, be sharp but fair\n\n"
            "Read the room. Match the energy."
            + THINK_INSTRUCTION
        ),
    },
}

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:    #07070f;
    --bg1:   #0d0d1a;
    --bg2:   #111124;
    --bg3:   #16162e;
    --text:  #e8e8ff;
    --muted: #5a5a8a;
    --border:#1e1e3a;
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family:'Inter',sans-serif !important; }
.stApp { background:var(--bg) !important; color:var(--text) !important; }
.main .block-container { max-width:870px !important; padding:1rem 1.5rem !important; }
#MainMenu, footer, header { visibility:hidden; }

/* Animated background */
.stApp::before {
    content:'';
    position:fixed; inset:0; z-index:0; pointer-events:none;
    background:
        radial-gradient(ellipse 600px 500px at 10% 20%, rgba(124,58,237,.07) 0%, transparent 70%),
        radial-gradient(ellipse 500px 400px at 90% 70%, rgba(168,85,247,.05) 0%, transparent 70%),
        radial-gradient(ellipse 400px 300px at 50% 90%, rgba(99,102,241,.04) 0%, transparent 70%);
    animation: orb-drift 20s ease-in-out infinite alternate;
}
@keyframes orb-drift {
    0%   { transform: translate(0,0); }
    33%  { transform: translate(20px,-15px); }
    66%  { transform: translate(-10px,25px); }
    100% { transform: translate(15px,-5px); }
}

::-webkit-scrollbar { width:4px; }
::-webkit-scrollbar-track { background:var(--bg1); }
::-webkit-scrollbar-thumb { background:#7c3aed; border-radius:99px; }

[data-testid="stSidebar"] {
    background:var(--bg1) !important;
    border-right:1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color:var(--text) !important; }

.app-header {
    background: linear-gradient(135deg, var(--bg2), var(--bg3));
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1.4rem 1.8rem;
    margin-bottom: 1rem;
    position: relative; overflow: hidden;
    box-shadow: 0 0 40px rgba(124,58,237,.1), inset 0 1px 0 rgba(255,255,255,.04);
}
.app-header::after {
    content:''; position:absolute; top:-60px; right:-60px;
    width:220px; height:220px;
    background:radial-gradient(circle, rgba(168,85,247,.18) 0%, transparent 70%);
    pointer-events:none;
}
.app-title {
    font-size:2.2rem; font-weight:900; margin:0; letter-spacing:-0.03em;
    background:linear-gradient(90deg, #a855f7, #818cf8, #60a5fa);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.app-subtitle { color:var(--muted); font-size:.875rem; margin:4px 0 0; }

.mode-bar { display:flex; gap:.4rem; flex-wrap:wrap; margin-bottom:1rem; }
.mode-chip {
    padding:.3rem .8rem; border-radius:999px; font-size:.75rem; font-weight:700;
    border:1px solid var(--border); background:var(--bg2); color:var(--muted);
}
.mode-chip.active { color:#fff !important; border-color:transparent !important;
    box-shadow: 0 2px 12px rgba(124,58,237,.35); }

/* ── User messages: violet gradient bubble ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"]:first-child) {
    animation: msg-in .3s ease;
}
@keyframes msg-in { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }

/* All chat messages baseline */
[data-testid="stChatMessage"] {
    border-radius:18px !important;
    padding:1rem 1.3rem !important;
    margin-bottom:.85rem !important;
    animation: msg-in .3s ease;
}

/* User message bubble — deeper violet */
[data-testid="stChatMessage"]:nth-child(odd) {
    background: linear-gradient(135deg, #160e40, #1c1460) !important;
    border: 1px solid rgba(147,51,234,.55) !important;
    box-shadow: 0 2px 20px rgba(124,58,237,.22) !important;
}

/* AI message bubble — near-black with vivid left accent */
[data-testid="stChatMessage"]:nth-child(even) {
    background: #0d0c22 !important;
    border: 1px solid rgba(147,51,234,.35) !important;
    border-left: 4px solid #9333ea !important;
    box-shadow: 0 4px 28px rgba(0,0,0,.55), -1px 0 20px rgba(147,51,234,.12) !important;
}

/* Answer text — bright and easy to read */
[data-testid="stChatMessageContent"] {
    background:transparent !important;
    font-size: 1rem !important;
    line-height: 1.85 !important;
    color: #f0eeff !important;
    letter-spacing: .012em !important;
}

/* Bold and headings inside AI answers — high contrast */
[data-testid="stChatMessageContent"] strong { color:#e9d5ff !important; font-weight:800 !important; }
[data-testid="stChatMessageContent"] h1,
[data-testid="stChatMessageContent"] h2 {
    color:#ffffff !important; font-size:1.18rem !important;
    margin-top:1.1rem !important; border-bottom:1px solid rgba(147,51,234,.3) !important;
    padding-bottom:.25rem !important;
}
[data-testid="stChatMessageContent"] h3 { color:#ddd6fe !important; font-size:1.02rem !important; margin-top:.8rem !important; }
[data-testid="stChatMessageContent"] li { color:#ede9ff !important; margin-bottom:.3rem !important; }
[data-testid="stChatMessageContent"] p  { color:#f4f0ff !important; margin-bottom:.55rem !important; }
[data-testid="stChatMessageContent"] code {
    background:#240e44 !important; color:#c4b5fd !important;
    border:1px solid rgba(147,51,234,.4) !important;
    padding:.12em .45em !important; border-radius:5px !important;
    font-size:.88rem !important; font-weight:600 !important;
}

/* Code blocks */
code, pre { font-family:'JetBrains Mono','Fira Code',monospace !important; font-size:.88rem !important; }
[data-testid="stCodeBlock"] {
    border-radius:12px !important;
    border:1px solid rgba(99,102,241,.3) !important;
    background:#0b0b20 !important;
}

/* Thinking expander — clearly distinct from the answer */
[data-testid="stExpander"] {
    background: #080820 !important;
    border: 1px solid rgba(124,58,237,.25) !important;
    border-radius: 12px !important;
    margin-bottom: .65rem !important;
}
[data-testid="stExpander"] summary {
    color: #a78bfa !important;
    font-size: .8rem !important;
    font-weight: 700 !important;
    letter-spacing: .04em !important;
    text-transform: uppercase !important;
}
[data-testid="stExpander"] p,
[data-testid="stExpander"] li { color: #6e6e9e !important; font-size: .84rem !important; line-height:1.7 !important; }

[data-testid="stChatInput"] {
    background:var(--bg2) !important;
    border:1px solid #2d2d5e !important;
    border-radius:16px !important;
    color:var(--text) !important;
    font-size:.94rem !important;
    transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color:#7c3aed !important;
    box-shadow:0 0 0 3px rgba(124,58,237,.15) !important;
}
[data-testid="stChatInput"] textarea::placeholder { color:#5a5a8a !important; }

[data-testid="stSidebar"] .stButton>button {
    width:100% !important; background:var(--bg2) !important;
    color:var(--text) !important; border:1px solid var(--border) !important;
    border-radius:12px !important; font-weight:600 !important;
    font-size:.875rem !important; padding:.55rem 1rem !important;
    text-align:left !important; transition: all .18s !important;
}
[data-testid="stSidebar"] .stButton>button:hover {
    background:var(--bg3) !important; border-color:#7c3aed !important;
    transform:translateX(3px) !important;
}
.stButton>button {
    background:var(--bg3) !important; color:var(--text) !important;
    border:1px solid var(--border) !important; border-radius:10px !important;
    font-weight:600 !important; transition: all .15s !important;
}
.stButton>button:hover { border-color:#7c3aed !important; }

.stat-box {
    background:var(--bg2); border:1px solid var(--border);
    border-radius:12px; padding:.6rem 1rem; margin-bottom:.4rem; text-align:center;
}
.stat-val { font-size:1.5rem; font-weight:800; color:#a855f7; }
.stat-lbl { font-size:.7rem; color:var(--muted); }

.welcome-wrap { text-align:center; padding:2.5rem 1rem 2rem; }
.welcome-icon { font-size:3.5rem; margin-bottom:.7rem; animation: float 3s ease-in-out infinite; }
@keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
.welcome-title { font-size:1.4rem; font-weight:800; color:var(--text); margin-bottom:.4rem; }
.welcome-sub { font-size:.9rem; color:var(--muted); }
.cap-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:.5rem; margin-top:1.5rem; }
.cap-card {
    background:var(--bg2); border:1px solid var(--border); border-radius:12px;
    padding:.7rem .9rem; text-align:center;
}
.cap-icon { font-size:1.4rem; margin-bottom:.3rem; }
.cap-name { font-size:.78rem; font-weight:700; color:var(--text); }
.cap-desc { font-size:.69rem; color:var(--muted); margin-top:.15rem; }

label { color:#8888c0 !important; font-size:.82rem !important; font-weight:600 !important; }
hr { border-color:var(--border) !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────
for k, v in {"mode": "Chat", "conversations": {}, "total_messages": 0}.items():
    if k not in st.session_state:
        st.session_state[k] = v

mode = st.session_state.mode
m = MODES[mode]
history = st.session_state.conversations.get(mode, [])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## StudyMate")
    st.caption("Intelligent · Fast · Versatile")
    st.markdown("---")

    total = st.session_state.total_messages
    modes_used = sum(1 for k in st.session_state.conversations if st.session_state.conversations[k])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="stat-val">{total}</div><div class="stat-lbl">Messages</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><div class="stat-val">{modes_used}</div><div class="stat-lbl">Modes</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<p style="font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin-bottom:.5rem">Mode</p>', unsafe_allow_html=True)

    for mname, minfo in MODES.items():
        if mname == mode:
            st.markdown(
                f'<div style="background:{minfo["color"]}18;border:1px solid {minfo["color"]}55;'
                f'border-radius:12px;padding:.55rem 1rem;font-weight:700;font-size:.875rem;'
                f'color:{minfo["color"]};margin-bottom:.35rem">{minfo["icon"]} {mname}</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(f'{minfo["icon"]}  {mname}', key=f"mb_{mname}", use_container_width=True):
                st.session_state.mode = mname
                st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin-bottom:.5rem">Quick Prompts</p>', unsafe_allow_html=True)

    quick_prompts = {
        "Chat":   ["What's the meaning of life?", "Explain black holes simply", "Best advice for staying focused?"],
        "Code":   ["Build a Python web scraper", "Explain Big O notation with examples", "Write a FastAPI REST API"],
        "Think":  ["Should I start a startup or take a job?", "Trolley problem — what's the right call?", "How do I make a hard decision?"],
        "Create": ["5 unique startup ideas using AI", "Write a thriller opening paragraph", "Describe an alien civilization"],
        "Write":  ["Write a cold email that gets replies", "Improve: [paste your text]", "LinkedIn post about resilience"],
        "Humor":  ["Roast Python programmers", "Write 3 jokes about AI", "Make doing laundry sound epic"],
    }
    for qp in quick_prompts.get(mode, []):
        if st.button(qp[:46] + ("..." if len(qp) > 46 else ""), key=f"qp_{qp}", use_container_width=True):
            st.session_state["_prefill"] = qp
            st.rerun()

    st.markdown("---")
    if st.button("Clear This Chat", use_container_width=True):
        st.session_state.conversations[mode] = []
        st.rerun()
    if st.button("Clear All Chats", use_container_width=True):
        st.session_state.conversations = {}
        st.session_state.total_messages = 0
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="app-header">'
    f'<div class="app-title">StudyMate</div>'
    f'<div class="app-subtitle">Mode: <strong style="color:{m["color"]}">{m["icon"]} {mode}</strong>'
    f' &nbsp;·&nbsp; Deep reasoning enabled &nbsp;·&nbsp; Llama 3.3 70B</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# Mode pill bar
chips = "".join(
    '<span class="mode-chip {cls}" style="{style}">{icon} {name}</span>'.format(
        cls="active" if n == mode else "",
        style=f"background:{MODES[n]['gradient']}" if n == mode else "",
        icon=MODES[n]["icon"],
        name=n,
    )
    for n in MODES
)
st.markdown(f'<div class="mode-bar">{chips}</div>', unsafe_allow_html=True)

# ── Welcome screen ────────────────────────────────────────────────────────────
if not history:
    st.markdown(
        f'<div class="welcome-wrap">'
        f'<div class="welcome-icon">{m["icon"]}</div>'
        f'<div class="welcome-title">{m["icon"]} {mode} Mode</div>'
        f'<div class="welcome-sub">{m["placeholder"]}</div>'
        f'<div class="cap-grid">'
        + "".join(
            f'<div class="cap-card"><div class="cap-icon">{MODES[n]["icon"]}</div>'
            f'<div class="cap-name">{n}</div></div>'
            for n in MODES
        )
        + '</div></div>',
        unsafe_allow_html=True,
    )

# ── Chat History ─────────────────────────────────────────────────────────────
for msg in history:
    avatar = "👤" if msg["role"] == "user" else "⚡"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("type") == "image":
            st.markdown(f'**Generated image** for: *"{msg.get("image_prompt", "")[:80]}..."*')
            if msg.get("image_bytes"):
                st.image(msg["image_bytes"], use_container_width=True)
            else:
                st.warning(msg.get("error", "Image unavailable"))
        elif msg["role"] == "assistant":
            thinking, answer = parse_response(msg["content"])
            if thinking:
                with st.expander("🧠 Thought process", expanded=False):
                    st.markdown(thinking)
            st.markdown(answer)
        else:
            st.markdown(msg["content"])

# ── Auto-scroll to latest message ─────────────────────────────────────────────
st.markdown("""
<script>
    (function() {
        // Scroll the Streamlit main content pane to the bottom
        function scrollToBottom() {
            var parent = window.parent;
            var containers = parent.document.querySelectorAll('[data-testid="stChatMessage"]');
            if (containers.length > 0) {
                containers[containers.length - 1].scrollIntoView({
                    behavior: 'smooth', block: 'end'
                });
            }
            // Also scroll the main scroll area
            var main = parent.document.querySelector('[data-testid="stAppViewBlockContainer"]');
            if (!main) main = parent.document.querySelector('.main');
            if (main) main.scrollTop = main.scrollHeight;
        }
        // Run on load and after short delay for render
        scrollToBottom();
        setTimeout(scrollToBottom, 300);
        setTimeout(scrollToBottom, 800);
    })();
</script>
""", unsafe_allow_html=True)

# ── Input ─────────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("_prefill", "")
user_input = st.chat_input(m["placeholder"], key="ci")

if prefill and not user_input:
    user_input = prefill

if user_input and user_input.strip():
    query = user_input.strip()

    if mode not in st.session_state.conversations:
        st.session_state.conversations[mode] = []

    # Security: sanitize input
    query = sanitize_input(query)
    if not query:
        st.stop()

    # Security: per-session rate limit
    if not check_session_rate_limit():
        st.warning(f"Rate limit: max {MAX_REQUESTS_MIN} messages/minute. Please wait a moment.")
        st.stop()

    # Security: cap conversation history size
    if mode in st.session_state.conversations:
        if len(st.session_state.conversations[mode]) > MAX_HISTORY_TURNS:
            st.session_state.conversations[mode] = \
                st.session_state.conversations[mode][-MAX_HISTORY_TURNS:]

    st.session_state.conversations[mode].append({"role": "user", "content": query})
    st.session_state.total_messages += 1

    with st.chat_message("user", avatar="👤"):
        st.markdown(query)

    # Build clean message history (strip <think> from past AI turns)
    clean_history = []
    for h in st.session_state.conversations[mode][-20:]:
        if h["role"] == "assistant":
            _, clean = parse_response(h["content"])
            clean_history.append({"role": "assistant", "content": clean})
        else:
            clean_history.append(h)

    messages = [{"role": "system", "content": m["system"]}] + clean_history

    # ── DIAGRAM GENERATION ───────────────────────────────────────────────────────
    if is_diagram_request(query) and not is_image_request(query):
        import streamlit.components.v1 as components

        # Step 1: Text answer (strip diagram keywords so LLM just explains)
        clean_q = query.replace("generate a diagram", "").replace("generate diagram", "")
        clean_q = clean_q.replace("and diagram", "").replace("draw a diagram", "").strip()
        if clean_q:
            clean_history = []
            for h in st.session_state.conversations[mode][-10:]:
                if h["role"] == "user":
                    clean_history.append(h)
                elif h["role"] == "assistant" and h.get("type") not in ("image", "diagram"):
                    _, clean = parse_response(h["content"])
                    clean_history.append({"role": "assistant", "content": clean})
            text_messages = [{"role": "system", "content": m["system"]}] + clean_history
            with st.chat_message("assistant", avatar="⚡"):
                with st.spinner("Thinking..."):
                    raw_text = call_groq(text_messages, temperature=m["temp"], max_tokens=2000)
                thinking, answer = parse_response(raw_text)
                if thinking:
                    with st.expander("🧠 Thought process", expanded=False):
                        st.markdown(thinking)
                st.markdown(answer)
            st.session_state.conversations[mode].append({"role": "assistant", "content": raw_text})
            st.session_state.total_messages += 1

        # Step 2: Generate and render diagram
        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Generating diagram..."):
                raw_code = generate_diagram_code(query)
            mermaid_code = extract_mermaid(raw_code)
            if mermaid_code:
                st.markdown("**📊 Diagram:**")
                components.html(render_mermaid(mermaid_code), height=520, scrolling=False)
                with st.expander("Mermaid code", expanded=False):
                    st.code(mermaid_code, language="text")
                saved_content = mermaid_code
            else:
                st.code(raw_code, language="text")
                saved_content = raw_code
        st.session_state.conversations[mode].append({
            "role": "assistant", "content": saved_content, "type": "diagram"
        })
        st.session_state.total_messages += 1
        st.rerun()

    # ── IMAGE GENERATION ─────────────────────────────────────────────────────────
    elif is_image_request(query):
        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Generating image... (~15 seconds)"):
                img_prompt = build_image_prompt(query)
                img_bytes, img_url = fetch_image_bytes(img_prompt)

            if img_bytes:
                st.markdown(
                    f"**Here is your AI-generated image!**\n\n"
                    f'*Prompt:* `{img_prompt[:120]}...`'
                )
                st.image(img_bytes, use_container_width=True)
                st.caption("Generated by Flux AI • Pollinations.ai")
                saved = {
                    "role": "assistant", "content": f"[Image] {img_prompt}",
                    "type": "image", "image_prompt": img_prompt, "image_bytes": img_bytes,
                }
            else:
                st.warning(f"Image generation failed: {img_url}\nTry a more specific description.")
                saved = {
                    "role": "assistant", "content": "Image generation failed.",
                    "type": "image", "image_prompt": img_prompt,
                    "image_bytes": None, "error": str(img_url),
                }

        st.session_state.conversations[mode].append(saved)
        st.session_state.total_messages += 1
        st.rerun()

    # ── TEXT RESPONSE ─────────────────────────────────────────────────────────────
    else:
        clean_history = []
        for h in st.session_state.conversations[mode][-20:]:
            if h["role"] == "assistant" and h.get("type") != "image":
                _, clean = parse_response(h["content"])
                clean_history.append({"role": "assistant", "content": clean})
            elif h["role"] == "user":
                clean_history.append(h)

        messages = [{"role": "system", "content": m["system"]}] + clean_history

        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Thinking deeply..."):
                raw = call_groq(messages, temperature=m["temp"], max_tokens=6000)
            thinking, answer = parse_response(raw)
            if thinking:
                with st.expander("🧠 Thought process", expanded=True):
                    st.markdown(thinking)
            st.markdown(answer)

        st.session_state.conversations[mode].append({"role": "assistant", "content": raw})
        st.session_state.total_messages += 1
        st.rerun()
