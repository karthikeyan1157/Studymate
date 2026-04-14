"""
frontend/app.py — ExamPrep AI Streamlit UI
Vibrant Emerald + Gold theme | Concept image generation | Rich structured answers
"""

import os
import urllib.parse
import requests
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ExamPrep AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── IMAGE GENERATION via Pollinations.ai (free, no API key) ──────────────────
def concept_image_url(concept: str) -> str:
    prompt = (
        f"educational concept diagram of '{concept}', "
        "clean minimalist illustration, dark background, "
        "bright emerald and gold accents, infographic style, "
        "no text, high quality digital art"
    )
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=380&nologo=true&seed=42"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    --bg0:    #06060f;
    --bg1:    #0c0b1e;
    --bg2:    #111028;
    --bg3:    #181633;
    --em:     #9333ea;     /* violet */
    --em2:    #7c3aed;
    --gold:   #fbbf24;
    --gold2:  #d97706;
    --coral:  #f43f5e;
    --blue:   #60a5fa;
    --text:   #ede9ff;
    --muted:  #6b5fa0;
    --border: rgba(147,51,234,.18);
    --glow:   0 0 36px rgba(147,51,234,.15);
    --gshadow:0 0 30px rgba(251,191,36,.1);
}

html, body, [class*="css"] { font-family:'Inter',sans-serif !important; }
.stApp { background:var(--bg0) !important; color:var(--text) !important; }
.main .block-container { max-width:920px !important; padding:1rem 1.5rem !important; }
#MainMenu, footer, header { visibility:hidden; }

/* Scrollbar */
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background:var(--bg1); }
::-webkit-scrollbar-thumb { background:var(--em); border-radius:99px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background:var(--bg1) !important;
    border-right:1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color:var(--text) !important; }

/* ── Brand header ── */
.brand {
    background:linear-gradient(135deg, var(--bg2) 0%, #0e0a26 100%);
    border:1px solid rgba(147,51,234,.28);
    border-radius:20px;
    padding:1.5rem 1.8rem;
    margin-bottom:1rem;
    display:flex; align-items:center; gap:1.2rem;
    box-shadow: var(--glow), inset 0 1px 0 rgba(147,51,234,.12);
    position:relative; overflow:hidden;
}
.brand::before {
    content:'';
    position:absolute; top:-40px; right:-40px;
    width:180px; height:180px;
    background:radial-gradient(circle, rgba(147,51,234,.15) 0%, transparent 70%);
    pointer-events:none;
}
.brand-icon { font-size:2.6rem; filter:drop-shadow(0 0 12px rgba(147,51,234,.7)); }
.brand-title {
    font-size:2rem; font-weight:800; margin:0;
    background:linear-gradient(90deg, #a855f7, #7c3aed, #60a5fa);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.brand-sub { margin:4px 0 0; color:var(--muted); font-size:.875rem; }

/* ── Stat pills ── */
.pills { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1rem; }
.pill {
    background:var(--bg3); border:1px solid var(--border); border-radius:999px;
    padding:.3rem .85rem; font-size:.75rem; font-weight:600; color:var(--muted);
}
.pill b { color:var(--em); }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background:var(--bg2) !important;
    border:1px solid var(--border) !important;
    border-radius:14px !important;
    padding:.3rem !important; gap:.3rem !important;
}
.stTabs [data-baseweb="tab"] {
    background:transparent !important; color:var(--muted) !important;
    border-radius:10px !important; font-weight:600 !important;
    padding:.45rem 1.2rem !important;
}
.stTabs [aria-selected="true"] {
    background:linear-gradient(135deg, var(--em), #009982) !important;
    color:#000 !important; font-weight:700 !important;
}

/* ── Chat messages ── */
.msg { display:flex; gap:.7rem; align-items:flex-start; margin-bottom:1.1rem; animation:pop .3s ease; }
@keyframes pop { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
.msg.right { flex-direction:row-reverse; }
.av {
    width:36px; height:36px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:1.1rem; flex-shrink:0;
}
.av-ai { background:linear-gradient(135deg,var(--em),#009982); color:#000; }
.av-u  { background:linear-gradient(135deg,var(--gold),var(--gold2)); color:#000; }
.bub { border-radius:16px; padding:.85rem 1.15rem; max-width:85%; font-size:.92rem; line-height:1.7; }
.bub.ai {
    background:var(--bg2);
    border:1px solid rgba(0,212,170,.2);
    box-shadow: 0 2px 12px rgba(0,212,170,.06);
}
.bub.user {
    background:linear-gradient(135deg,#0d2a20,#0a2018);
    border:1px solid rgba(0,212,170,.25);
}

/* ── Concept image ── */
.concept-img-wrap {
    border:1px solid rgba(245,200,66,.2);
    border-radius:14px; overflow:hidden; margin:1rem 0;
    box-shadow: var(--gshadow);
}
.concept-img-label {
    background:linear-gradient(135deg,var(--bg2),var(--bg3));
    padding:.45rem 1rem; font-size:.75rem; font-weight:700;
    color:var(--gold); letter-spacing:.05em; text-transform:uppercase;
    border-bottom:1px solid rgba(245,200,66,.15);
}
.concept-img-wrap img { width:100%; display:block; }

/* ── Question cards ── */
.qs-label {
    font-size:.72rem; font-weight:700; color:var(--muted);
    text-transform:uppercase; letter-spacing:.07em; margin:1.2rem 0 .5rem;
}
.q-card {
    background:var(--bg2); border:1px solid var(--border);
    border-radius:13px; padding:.85rem 1.1rem;
    margin-bottom:.55rem; transition:border-color .2s,transform .2s;
}
.q-card:hover { border-color:var(--em); transform:translateX(4px); }
.q-top { display:flex; align-items:center; gap:.5rem; margin-bottom:.45rem; }
.q-topic { font-size:.7rem; font-weight:700; color:var(--em); text-transform:uppercase; letter-spacing:.05em; }
.q-txt { font-size:.9rem; color:var(--text); }
.badge {
    display:inline-block; border-radius:999px;
    padding:.1rem .5rem; font-size:.67rem; font-weight:700; text-transform:uppercase;
}
.b-easy   { background:rgba(0,212,170,.1); color:var(--em); }
.b-medium { background:rgba(245,200,66,.1); color:var(--gold); }
.b-hard   { background:rgba(255,107,107,.1); color:var(--coral); }
.b-custom { background:rgba(77,166,255,.1); color:var(--blue); }

/* ── Score card ── */
.score-card {
    background:linear-gradient(135deg,var(--bg1),var(--bg2));
    border:1px solid var(--border); border-radius:16px;
    padding:1.1rem 1.3rem; margin-top:.8rem;
    box-shadow: var(--glow);
}
.score-top   { display:flex; justify-content:space-between; align-items:center; }
.score-track { height:8px; border-radius:999px; background:rgba(255,255,255,.06); margin:.6rem 0; overflow:hidden; }
.score-fill  { height:100%; border-radius:999px; transition:width .7s ease; }
.score-body  { font-size:.88rem; line-height:1.6; color:var(--text); margin:.4rem 0 0; }
.hint-body   { font-size:.83rem; color:var(--gold); font-style:italic; margin:.5rem 0 0; }

/* ── Add question card ── */
.add-card {
    background:linear-gradient(135deg,var(--bg1),var(--bg2));
    border:1px solid var(--border); border-radius:18px;
    padding:1.5rem 1.8rem; margin-bottom:1.2rem;
    box-shadow: var(--glow);
}
.add-title { font-size:1.15rem; font-weight:800; color:var(--em); margin-bottom:.3rem; }
.add-sub   { font-size:.85rem; color:var(--muted); }
.success-box {
    background:rgba(0,212,170,.08); border:1px solid rgba(0,212,170,.3);
    border-radius:12px; padding:.85rem 1rem;
    color:var(--em); font-weight:700; text-align:center; margin-top:.5rem;
}
.how-card {
    background:var(--bg2); border:1px solid var(--border);
    border-radius:13px; padding:1rem; text-align:center;
}
.how-icon  { font-size:1.8rem; margin-bottom:.5rem; }
.how-title { font-weight:700; font-size:.88rem; color:var(--em); margin-bottom:.25rem; }
.how-body  { font-size:.78rem; color:var(--muted); }

/* ── Sidebar cards ── */
.s-card {
    background:var(--bg2); border:1px solid var(--border);
    border-radius:12px; padding:.7rem 1rem; margin-bottom:.5rem; text-align:center;
}
.s-val { font-size:1.7rem; font-weight:800; color:var(--em); }
.s-lbl { font-size:.72rem; color:var(--muted); }

/* ── Inputs ── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stSelectbox>div>div>div {
    background:var(--bg2) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
    color:var(--text) !important;
    font-size:.92rem !important;
}

/* Placeholder text — fully visible */
.stTextInput>div>div>input::placeholder,
.stTextArea>div>div>textarea::placeholder {
    color:#7ab8a4 !important;
    opacity:1 !important;
}

/* Labels — brighter so they're clearly readable */
label, .stTextInput label, .stTextArea label, .stSelectbox label {
    color:#a8d4c8 !important;
    font-size:.82rem !important;
    font-weight:600 !important;
}

/* Selectbox dropdown text */
.stSelectbox [data-baseweb="select"] * { color:var(--text) !important; }
.stSelectbox [data-baseweb="select"] [data-baseweb="popover"] {
    background:var(--bg2) !important;
    border:1px solid var(--border) !important;
}

/* ── Sidebar buttons (quick queries) — emerald, dark text ── */
[data-testid="stSidebar"] .stButton>button {
    background:linear-gradient(135deg, var(--em), var(--em2)) !important;
    color:#001a14 !important; border:none !important;
    border-radius:10px !important; font-weight:700 !important;
    font-size:.83rem !important; padding:.4rem 1rem !important;
    box-shadow: 0 3px 10px rgba(0,212,170,.2) !important;
    width:100% !important;
}
[data-testid="stSidebar"] .stButton>button:hover { opacity:.85 !important; transform:translateY(-1px) !important; }

/* ── Main area buttons (Clear chat icon button) ── */
.stButton>button {
    background:var(--bg3) !important;
    color:var(--text) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important; font-weight:700 !important;
    padding:.45rem 1rem !important;
    transition:background .2s, border-color .2s !important;
}
.stButton>button:hover { background:var(--bg2) !important; border-color:var(--em) !important; }

/* ── Form submit buttons — distinct emerald style, WHITE text ── */
.stFormSubmitButton>button {
    background:linear-gradient(135deg, var(--em), var(--em2)) !important;
    color:#fff !important; border:none !important;
    border-radius:11px !important; font-weight:800 !important;
    font-size:.95rem !important; letter-spacing:.03em !important;
    padding:.55rem 1.3rem !important;
    box-shadow: 0 4px 18px rgba(0,212,170,.3) !important;
    transition:opacity .2s, transform .15s, box-shadow .2s !important;
    width:100% !important;
}
.stFormSubmitButton>button:hover { opacity:.9 !important; transform:translateY(-2px) !important; box-shadow: 0 6px 24px rgba(0,212,170,.4) !important; }

/* ── Info / warning boxes ── */
.stAlert { background:var(--bg2) !important; border-radius:12px !important; color:var(--text) !important; }

/* divider */
hr { border-color:var(--border) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "messages": [], "current_questions": [], "evaluating_q": None,
    "last_concept": "", "session_score": {"total": 0, "attempts": 0, "correct": 0},
    "q_count": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── API helper ────────────────────────────────────────────────────────────────
def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{BACKEND_URL}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        st.error("⚡ Backend not running — start: `uvicorn backend.main:app --port 8000`")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None

if st.session_state.q_count is None:
    r = api("get", "/count")
    st.session_state.q_count = r["count"] if r else "—"

# ── Helpers ───────────────────────────────────────────────────────────────────
def badge(diff):
    cls = {"easy": "b-easy", "medium": "b-medium", "hard": "b-hard"}.get(diff, "b-custom")
    return f'<span class="badge {cls}">{diff}</span>'

def score_color(s):
    if s >= 8: return "var(--em)"
    if s >= 5: return "var(--gold)"
    return "var(--coral)"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 ExamPrep AI")
    st.caption("Your AI-powered exam preparation assistant")
    st.markdown("---")

    sc = st.session_state.session_score
    avg = round(sc["total"] / sc["attempts"], 1) if sc["attempts"] else "—"
    pct = int(sc["correct"] / sc["attempts"] * 100) if sc["attempts"] else 0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="s-card"><div class="s-val">{sc["attempts"]}</div><div class="s-lbl">Attempts</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="s-card"><div class="s-val">{avg}</div><div class="s-lbl">Avg Score</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="s-card"><div class="s-val" style="color:var(--gold)">{pct}%</div><div class="s-lbl">Pass Rate ≥7/10</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="s-card"><div class="s-val" style="color:var(--blue)">{st.session_state.q_count}</div><div class="s-lbl">Questions in DB</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    meta = api("get", "/topics") or {"topics": [], "difficulties": []}
    sel_topic = st.selectbox("📚 Topic Filter", ["All Topics"] + meta.get("topics", []))
    sel_diff  = st.selectbox("⚡ Difficulty",   ["Any Difficulty"] + meta.get("difficulties", []))
    f_topic = None if sel_topic == "All Topics" else sel_topic
    f_diff  = None if sel_diff == "Any Difficulty" else sel_diff

    st.markdown("---")
    st.markdown('<p style="font-size:.72rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.06em">✨ Quick Queries</p>', unsafe_allow_html=True)
    for ex in ["Explain gradient descent", "What is overfitting?", "How does BFS differ from DFS?", "Explain the TCP handshake", "What is dynamic programming?"]:
        if st.button(ex, use_container_width=True, key=f"ex_{ex}"):
            st.session_state["_prefill"] = ex
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_questions = []
        st.session_state.evaluating_q = None
        st.session_state.last_concept = ""
        st.rerun()

# ── Brand header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="brand">
  <span class="brand-icon">🎓</span>
  <div>
    <p class="brand-title">ExamPrep AI</p>
    <p class="brand-sub">Ask any concept · Get AI explanations + visual diagrams · Practice with instant feedback</p>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="pills">
  <span class="pill">📚 Questions: <b>{st.session_state.q_count}</b></span>
  <span class="pill">�️ Visual Explanations: <b>Enabled</b></span>
  <span class="pill">🤖 AI Feedback: <b>Instant</b></span>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_add = st.tabs(["💬 Chat & Practice", "➕ Add Your Questions"])

# ════════════════════════════════════════════════════
# TAB 1 — CHAT
# ════════════════════════════════════════════════════
with tab_chat:

    # Show concept image if we have one
    if st.session_state.last_concept:
        img_url = concept_image_url(st.session_state.last_concept)
        st.markdown(f"""
        <div class="concept-img-wrap">
          <div class="concept-img-label">🖼️ Concept Visualisation · {st.session_state.last_concept}</div>
          <img src="{img_url}" alt="Concept diagram for {st.session_state.last_concept}" loading="lazy"/>
        </div>
        """, unsafe_allow_html=True)

    # Chat messages
    for msg in st.session_state.messages:
        is_user = msg["role"] == "user"
        if is_user:
            safe = msg["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            st.markdown(f"""
            <div class="msg right">
              <div class="av av-u">&#128100;</div>
              <div class="bub user">{safe}</div>
            </div>""", unsafe_allow_html=True)
        else:
            # AI: icon + full markdown rendering side by side
            col_icon, col_body = st.columns([1, 16])
            with col_icon:
                st.markdown('<div class="av av-ai" style="margin-top:.25rem;">&#129302;</div>', unsafe_allow_html=True)
            with col_body:
                st.markdown(
                    f'<div style="background:var(--bg2);border:1px solid rgba(0,212,170,.2);'
                    f'border-radius:16px;padding:.85rem 1.15rem;font-size:.93rem;line-height:1.75;">',
                    unsafe_allow_html=True,
                )
                st.markdown(msg["content"])
                st.markdown('</div>', unsafe_allow_html=True)


    # Practice question cards
    if st.session_state.current_questions:
        st.markdown('<div class="qs-label">📋 Semantically Retrieved Practice Questions &nbsp;—&nbsp; Click ✏️ to attempt</div>', unsafe_allow_html=True)
        for i, q in enumerate(st.session_state.current_questions[:5]):
            diff  = q.get("difficulty", "medium")
            topic = q.get("topic", "")
            is_custom = topic == "Custom"
            c_l, c_r = st.columns([7, 1])
            with c_l:
                st.markdown(f"""
                <div class="q-card">
                  <div class="q-top">
                    <span class="q-topic">{"🌟 " if is_custom else ""}Q{i+1} · {topic}</span>
                    {badge(diff)}
                  </div>
                  <div class="q-txt">{q.get('question','')}</div>
                </div>""", unsafe_allow_html=True)
            with c_r:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✏️", key=f"att_{i}", help="Attempt this question"):
                    st.session_state.evaluating_q = q
                    st.rerun()

    # Answer attempt
    if st.session_state.evaluating_q:
        q = st.session_state.evaluating_q
        st.markdown("---")
        st.markdown("**✏️ Attempt this question:**")
        st.info(q.get("question", ""))
        with st.form("ans_form", clear_on_submit=True):
            ans = st.text_area("Your answer", placeholder="Write your best answer here…", height=110, label_visibility="collapsed")
            c1, c2 = st.columns(2)
            with c1: sub = st.form_submit_button("🚀 Submit Answer", use_container_width=True)
            with c2: can = st.form_submit_button("✖ Cancel", use_container_width=True)

        if can:
            st.session_state.evaluating_q = None
            st.rerun()

        if sub and ans.strip():
            with st.spinner("🤔 AI is evaluating your answer…"):
                res = api("post", "/evaluate", json={
                    "question": q.get("question", ""),
                    "student_answer": ans,
                    "correct_answer": q.get("answer", ""),
                })
            if res:
                score = res["score"]
                sc = st.session_state.session_score
                sc["attempts"] += 1; sc["total"] += score
                if res["is_correct"] or score >= 7: sc["correct"] += 1
                col = score_color(score)
                ico = "✅" if (res["is_correct"] or score >= 7) else ("⚠️" if score >= 5 else "❌")
                st.markdown(f"""
                <div class="score-card">
                  <div class="score-top">
                    <span style="font-weight:800;font-size:1.05rem">{ico} &nbsp;Score: <span style="color:{col}">{score} / 10</span></span>
                    <span style="font-size:.8rem;color:var(--muted)">{"Correct ✓" if (res["is_correct"] or score>=7) else "Keep practising"}</span>
                  </div>
                  <div class="score-track"><div class="score-fill" style="width:{score*10}%;background:{col}"></div></div>
                  <div class="score-body">{res["feedback"]}</div>
                  <div class="hint-body">💡 {res["hint"]}</div>
                </div>""", unsafe_allow_html=True)
                st.session_state.messages += [
                    {"role": "user",      "content": f"**My answer to:** _{q.get('question','')[:80]}…_\n\n{ans}"},
                    {"role": "assistant", "content": f"**{ico} {score}/10** — {res['feedback']}\n\n💡 _{res['hint']}_"},
                ]
                st.session_state.evaluating_q = None
                st.rerun()

    # ── Chat input ────────────────────────────────────────────────────────────
    st.markdown("---")
    prefill = st.session_state.get("_prefill", "")
    if "_prefill" in st.session_state:
        del st.session_state["_prefill"]

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Ask",
            value=prefill,
            placeholder="e.g. 'What is gradient descent?' or 'Explain the OSI model'",
            label_visibility="collapsed",
        )
        send = st.form_submit_button("Send ➤", use_container_width=True)

    if send and user_input.strip():
        st.session_state.messages.append({"role": "user", "content": user_input.strip()})
        with st.spinner("🔍 Searching knowledge base + generating explanation + creating concept image…"):
            res = api("post", "/ask", json={
                "query": user_input.strip(),
                "topic": f_topic,
                "difficulty": f_diff,
            })
        if res:
            st.session_state.messages.append({"role": "assistant", "content": res["reply"]})
            st.session_state.current_questions = res.get("questions", [])
            st.session_state.last_concept = res.get("concept", user_input.strip())
        st.rerun()


# ════════════════════════════════════════════════════
# TAB 2 — ADD QUESTION
# ════════════════════════════════════════════════════
with tab_add:
    st.markdown("""
    <div class="add-card">
      <div class="add-title">📥 Submit Your Own Question</div>
      <div class="add-sub">Add any exam Q&amp;A — it gets <strong>embedded immediately</strong> and the AI can retrieve it for future searches.</div>
    </div>
    """, unsafe_allow_html=True)

    topics_list = ["Machine Learning", "Deep Learning", "Data Structures",
                   "Algorithms", "Operating Systems", "Computer Networks", "Custom"]

    with st.form("add_q_form", clear_on_submit=True):
        new_q = st.text_area("✏️ Question", placeholder="e.g. What is the difference between supervised and unsupervised learning?", height=90, label_visibility="visible")
        new_a = st.text_area("📖 Model Answer", placeholder="e.g. Supervised learning uses labelled data to train a model…", height=120, label_visibility="visible")

        c1, c2, c3 = st.columns(3)
        with c1: new_topic = st.selectbox("📚 Topic", topics_list)
        with c2: new_sub   = st.text_input("🏷️ Subtopic", placeholder="e.g. Regularization")
        with c3: new_diff  = st.selectbox("⚡ Difficulty", ["easy", "medium", "hard"], index=1)

        add_btn = st.form_submit_button("➕ Add to Knowledge Base", use_container_width=True)

    if add_btn:
        if not new_q.strip() or not new_a.strip():
            st.warning("⚠️ Please fill in both the question and answer fields.")
        else:
            with st.spinner("🧠 Embedding and storing your question…"):
                res = api("post", "/add_question", json={
                    "question":   new_q.strip(),
                    "answer":     new_a.strip(),
                    "topic":      new_topic,
                    "subtopic":   new_sub,
                    "difficulty": new_diff,
                })
            if res and res.get("success"):
                st.session_state.q_count = res["total"]
                st.markdown(f'<div class="success-box">✅ {res["message"]} &nbsp;|&nbsp; Total in DB: <strong>{res["total"]}</strong></div>', unsafe_allow_html=True)
                st.balloons()

    st.markdown("---")
    st.markdown('<p style="font-size:.72rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:.8rem">How it works</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc in [
        (c1, "✍️", "You Submit", "Type any Q&A from your textbook, notes, or past papers."),
        (c2, "🧠", "AI Learns", "The question is processed and stored in the knowledge base instantly."),
        (c3, "🔍", "AI Retrieves", "Next time you ask a related concept, your question surfaces automatically."),
    ]:
        with col:
            st.markdown(f"""
            <div class="how-card">
              <div class="how-icon">{icon}</div>
              <div class="how-title">{title}</div>
              <div class="how-body">{desc}</div>
            </div>""", unsafe_allow_html=True)
