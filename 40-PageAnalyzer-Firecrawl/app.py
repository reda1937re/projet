import streamlit as st
from scrape_agent import analyze_page

st.set_page_config(page_title="Analyseur de Page", page_icon="◆", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --ink: #0f172a; --muted: #64748b; --accent: #1d4ed8; --accent-solid: #1d4ed8;
        --border: #e2e8f0; --surface: rgba(15, 23, 42, 0.02); --card-bg: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ink: #f1f5f9; --muted: #94a3b8; --accent: #60a5fa;
            --border: rgba(255, 255, 255, 0.14); --surface: rgba(255, 255, 255, 0.04); --card-bg: #1e293b;
        }
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; }
    .block-container { padding-top: 2.2rem; max-width: 880px; }

    .eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.5rem; }
    .hero-title { font-weight: 700; font-size: 2rem; color: var(--ink); margin-bottom: 0.35rem; line-height: 1.25; }
    .hero-subtitle { color: var(--muted); font-size: 0.98rem; margin-bottom: 1.4rem; max-width: 640px; line-height: 1.5; }
    .hero-rule { border: none; border-top: 1px solid var(--border); margin: 0 0 1.8rem 0; }

    div[data-testid="stTextInput"] input {
        border-radius: 6px !important; padding: 0.7rem 0.9rem !important; font-size: 0.98rem !important;
        border: 1px solid var(--border) !important; box-shadow: none !important; transition: border-color .12s ease;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.12) !important;
    }

    div[data-testid="stFormSubmitButton"] button {
        background: var(--accent-solid) !important; color: white !important; border: none !important;
        border-radius: 6px !important; padding: 0.6rem 1.4rem !important; font-weight: 600 !important;
        letter-spacing: 0.01em; transition: background .12s ease;
    }
    div[data-testid="stFormSubmitButton"] button:hover { background: #1e40af !important; }
    div[data-testid="stFormSubmitButton"] button p { color: white !important; font-weight: 600; }

    div[class*="st-key-report_card"] {
        border-radius: 8px !important; border: 1px solid var(--border) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); padding: 0.3rem 0.3rem;
    }
    div[class*="st-key-report_card"] h2 {
        font-size: 0.78rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.08em;
        color: var(--muted) !important; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; margin-bottom: 0.9rem !important;
    }
    div[class*="st-key-report_card"] h3 { font-size: 1rem !important; color: var(--ink) !important; }

    .query-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.15rem; }
    .query-text { font-size: 1.05rem; font-weight: 600; color: var(--ink); margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }

    .empty-state { padding: 2.4rem 1rem; text-align: center; color: var(--muted); border: 1px dashed var(--border); border-radius: 8px; font-size: 0.92rem; }
    .error-box { padding: 1rem 1.1rem; border: 1px solid rgba(220, 38, 38, 0.3); background: rgba(220, 38, 38, 0.06); color: #dc2626; border-radius: 8px; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Firecrawl · scrape()</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Analyseur de Page</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Lit le contenu d’une page web et répond à une question précise à son sujet, '
    'ou en produit un résumé si aucune question n’est posée.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)

with st.form("page_form"):
    url = st.text_input("URL de la page :", placeholder="Ex : https://docs.firecrawl.dev/introduction")
    question = st.text_input("Question (optionnel) :", placeholder="Laisser vide pour un résumé général")
    submitted = st.form_submit_button("Analyser la page")

if "result" not in st.session_state:
    st.session_state.result = None

if submitted and url.strip():
    with st.spinner("Lecture de la page en cours..."):
        answer, error = analyze_page(url.strip(), question=question.strip() or None)
    st.session_state.result = {"url": url.strip(), "question": question.strip(), "answer": answer, "error": error}

if not st.session_state.result:
    st.markdown(
        '<div class="empty-state">Aucune analyse pour l’instant. '
        "Saisissez une URL ci-dessus pour commencer.</div>",
        unsafe_allow_html=True,
    )
else:
    res = st.session_state.result
    if res["error"]:
        st.markdown(f'<div class="error-box">{res["error"]}</div>', unsafe_allow_html=True)
    else:
        with st.container(border=True, key="report_card"):
            st.markdown('<div class="query-label">Page analysée</div>', unsafe_allow_html=True)
            label = res["question"] if res["question"] else "Résumé général"
            st.markdown(
                f'<div class="query-text">{res["url"]}<br>'
                f'<span style="font-weight:400; font-size:0.85rem; color:var(--muted);">{label}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(res["answer"])
