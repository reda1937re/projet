import os

import streamlit as st
from compare_agent import compare_documents, ocr_pdf

st.set_page_config(page_title="Comparateur de Documents", page_icon="◆", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --ink: #0f172a; --muted: #64748b; --accent: #1d4ed8; --accent-solid: #1d4ed8;
        --border: #e2e8f0; --surface: rgba(15, 23, 42, 0.02); --card-bg: #ffffff;
        --green: #16a34a; --green-bg: rgba(22, 163, 74, 0.1);
        --red: #dc2626; --red-bg: rgba(220, 38, 38, 0.1);
        --amber: #d97706; --amber-bg: rgba(217, 119, 6, 0.1);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ink: #f1f5f9; --muted: #94a3b8; --accent: #60a5fa;
            --border: rgba(255, 255, 255, 0.14); --surface: rgba(255, 255, 255, 0.04); --card-bg: #1e293b;
            --green: #4ade80; --green-bg: rgba(74, 222, 128, 0.12);
            --red: #f87171; --red-bg: rgba(248, 113, 113, 0.12);
            --amber: #fbbf24; --amber-bg: rgba(251, 191, 36, 0.12);
        }
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; }
    .block-container { padding-top: 2.2rem; max-width: 900px; }

    .eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.5rem; }
    .hero-title { font-weight: 700; font-size: 2rem; color: var(--ink); margin-bottom: 0.35rem; line-height: 1.25; }
    .hero-subtitle { color: var(--muted); font-size: 0.98rem; margin-bottom: 1.4rem; max-width: 660px; line-height: 1.5; }
    .hero-rule { border: none; border-top: 1px solid var(--border); margin: 0 0 1.8rem 0; }

    div[data-testid="stFormSubmitButton"] button {
        background: var(--accent-solid) !important; color: white !important; border: none !important;
        border-radius: 6px !important; padding: 0.6rem 1.4rem !important; font-weight: 600 !important;
        letter-spacing: 0.01em; transition: background .12s ease;
    }
    div[data-testid="stFormSubmitButton"] button:hover { background: #1e40af !important; }
    div[data-testid="stFormSubmitButton"] button p { color: white !important; font-weight: 600; }

    .doc-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 0.4rem; }

    div[class*="st-key-summary_card"] {
        border-radius: 8px !important; border: 1px solid var(--border) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); background: var(--surface) !important;
    }
    .summary-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 0.5rem; }
    .summary-text { color: var(--ink); font-size: 0.98rem; line-height: 1.5; }

    div[class*="st-key-chg_"] {
        border-radius: 8px !important; border: 1px solid var(--border) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .chg-badge {
        display: inline-block; font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.04em; border-radius: 4px; padding: 0.15rem 0.5rem; margin-bottom: 0.5rem;
    }
    .chg-badge.Ajout { color: var(--green); background: var(--green-bg); }
    .chg-badge.Suppression { color: var(--red); background: var(--red-bg); }
    .chg-badge.Modification { color: var(--amber); background: var(--amber-bg); }
    .chg-clause { font-weight: 600; font-size: 0.95rem; color: var(--ink); margin-bottom: 0.3rem; }
    .chg-detail { font-size: 0.87rem; color: var(--muted); line-height: 1.5; }

    .empty-state { padding: 2.4rem 1rem; text-align: center; color: var(--muted); border: 1px dashed var(--border); border-radius: 8px; font-size: 0.92rem; }
    .no-changes { padding: 1.2rem; text-align: center; color: var(--green); background: var(--green-bg); border-radius: 8px; font-size: 0.92rem; font-weight: 500; }
    .error-box { padding: 1rem 1.1rem; border: 1px solid rgba(220, 38, 38, 0.3); background: var(--red-bg); color: var(--red); border-radius: 8px; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Mistral OCR · Comparaison</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Comparateur de Documents</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Extrait le texte de deux versions d’un document par OCR '
    'et identifie précisément les clauses ajoutées, supprimées ou modifiées entre les deux.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)

with st.form("compare_form"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="doc-label">Document A — version précédente</div>', unsafe_allow_html=True)
        file_a = st.file_uploader("Document A", type=["pdf"], label_visibility="collapsed", key="file_a")
    with col_b:
        st.markdown('<div class="doc-label">Document B — version actuelle</div>', unsafe_allow_html=True)
        file_b = st.file_uploader("Document B", type=["pdf"], label_visibility="collapsed", key="file_b")
    submitted = st.form_submit_button("Comparer les documents")

if "result" not in st.session_state:
    st.session_state.result = None

if submitted:
    if not file_a or not file_b:
        st.markdown('<div class="error-box">Merci d’ajouter les deux documents avant de lancer la comparaison.</div>', unsafe_allow_html=True)
    else:
        os.makedirs("uploads", exist_ok=True)
        path_a = os.path.join("uploads", file_a.name)
        path_b = os.path.join("uploads", file_b.name)
        with open(path_a, "wb") as f:
            f.write(file_a.read())
        with open(path_b, "wb") as f:
            f.write(file_b.read())

        try:
            with st.spinner("Extraction du texte (OCR) des deux documents..."):
                text_a = ocr_pdf(path_a)
                text_b = ocr_pdf(path_b)
            with st.spinner("Comparaison des deux versions en cours..."):
                result = compare_documents(text_a, text_b)
            st.session_state.result = {"name_a": file_a.name, "name_b": file_b.name, "result": result}
        except Exception as e:
            st.session_state.result = {"error": str(e)}

if not st.session_state.result:
    st.markdown(
        '<div class="empty-state">Aucune comparaison pour l’instant. '
        "Ajoutez les deux versions d’un document ci-dessus pour commencer.</div>",
        unsafe_allow_html=True,
    )
elif st.session_state.result.get("error"):
    st.markdown(f'<div class="error-box">Erreur pendant la comparaison : {st.session_state.result["error"]}</div>', unsafe_allow_html=True)
else:
    res = st.session_state.result
    comparison = res["result"]

    with st.container(border=True, key="summary_card"):
        st.markdown('<div class="summary-label">Résumé</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="summary-text">{comparison.summary}</div>', unsafe_allow_html=True)
        st.caption(f'{res["name_a"]} → {res["name_b"]}')

    st.write("")

    if not comparison.changes:
        st.markdown('<div class="no-changes">Aucun changement de fond détecté entre les deux versions.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"**{len(comparison.changes)} changement(s) détecté(s)**")
        for i, change in enumerate(comparison.changes):
            with st.container(border=True, key=f"chg_{i}"):
                st.markdown(
                    f'<span class="chg-badge {change.type}">{change.type}</span>'
                    f'<div class="chg-clause">{change.clause}</div>'
                    f'<div class="chg-detail">{change.detail}</div>',
                    unsafe_allow_html=True,
                )
