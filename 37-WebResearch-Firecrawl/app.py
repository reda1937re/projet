import streamlit as st
from research_agent import research, SEARCH_LIMIT

st.set_page_config(page_title="Assistant de Recherche Web", page_icon="◆", layout="wide")

# ---------------------------------------------------------------------------
# Design : palette neutre, un seul accent, typographie sobre. Surcharge des
# composants Streamlit via leurs data-testid (stables sur 1.4x) et les
# classes st-key-* générées par le paramètre key= des conteneurs, pour
# cibler précisément sans casser le moteur de layout de Streamlit.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* --ink/--muted/--accent/--border/--surface adaptent le texte au thème
       clair ou sombre choisi dans Streamlit (Settings > Theme, ou "Use system
       setting" qui suit prefers-color-scheme) ; --accent-solid reste fixe car
       il est toujours posé sur un fond plein avec du texte blanc, donc lisible
       quel que soit le thème de la page. */
    :root {
        --ink: #0f172a;
        --muted: #64748b;
        --accent: #1d4ed8;
        --accent-solid: #1d4ed8;
        --border: #e2e8f0;
        --surface: rgba(15, 23, 42, 0.02);
        --card-bg: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ink: #f1f5f9;
            --muted: #94a3b8;
            --accent: #60a5fa;
            --border: rgba(255, 255, 255, 0.14);
            --surface: rgba(255, 255, 255, 0.04);
            --card-bg: #1e293b;
        }
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; }

    .block-container { padding-top: 2.2rem; max-width: 880px; }

    /* --- En-tête --- */
    .eyebrow {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.5rem;
    }
    .hero-title {
        font-weight: 700;
        font-size: 2rem;
        color: var(--ink);
        margin-bottom: 0.35rem;
        line-height: 1.25;
    }
    .hero-subtitle {
        color: var(--muted);
        font-size: 0.98rem;
        margin-bottom: 1.4rem;
        max-width: 640px;
        line-height: 1.5;
    }
    .hero-rule { border: none; border-top: 1px solid var(--border); margin: 0 0 1.8rem 0; }

    /* --- Champ de recherche --- */
    div[data-testid="stTextInput"] input {
        border-radius: 6px !important;
        padding: 0.7rem 0.9rem !important;
        font-size: 0.98rem !important;
        border: 1px solid var(--border) !important;
        box-shadow: none !important;
        transition: border-color .12s ease;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.12) !important;
    }

    /* --- Bouton principal (submit du formulaire) --- */
    div[data-testid="stFormSubmitButton"] button {
        background: var(--accent-solid) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.6rem 1.4rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        transition: background .12s ease;
    }
    div[data-testid="stFormSubmitButton"] button:hover { background: #1e40af !important; }
    div[data-testid="stFormSubmitButton"] button p { color: white !important; font-weight: 600; }

    /* --- Exemples --- */
    .examples-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin: 1.6rem 0 0.6rem 0;
    }
    div[class*="st-key-example_"] button {
        border-radius: 6px !important;
        border: 1px solid var(--border) !important;
        background: var(--card-bg) !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        color: var(--ink) !important;
        padding: 0.45rem 0.8rem !important;
    }
    div[class*="st-key-example_"] button:hover {
        border-color: var(--accent) !important;
        color: var(--accent) !important;
    }

    /* --- Carte de rapport --- */
    div[class*="st-key-report_card_"] {
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        padding: 0.3rem 0.3rem;
    }
    div[class*="st-key-report_card_"] h2 {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted) !important;
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.5rem;
        margin-bottom: 0.9rem !important;
    }
    div[class*="st-key-report_card_"] h3 { font-size: 1rem !important; color: var(--ink) !important; }
    div[class*="st-key-report_card_"] table { font-size: 0.88rem; }

    .query-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.15rem;
    }
    .query-text {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--ink);
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--border);
    }

    /* --- Sources --- */
    .sources-label {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        margin: 1.2rem 0 0.7rem 0;
    }
    div[class*="st-key-src_"] {
        border-radius: 6px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
        transition: border-color .12s ease;
    }
    div[class*="st-key-src_"]:hover { border-color: #cbd5e1 !important; }
    .src-row { display: flex; align-items: flex-start; gap: 0.65rem; }
    .src-badge {
        flex: none;
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 4px;
        background: var(--accent-solid);
        color: white;
        font-size: 0.72rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .src-title { font-weight: 600; font-size: 0.9rem; color: var(--ink); margin-bottom: 0.1rem; }
    .src-title a { text-decoration: none; color: inherit; }
    .src-title a:hover { color: var(--accent); }
    .src-domain { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 0.35rem; }
    .src-snippet { font-size: 0.82rem; color: var(--muted); line-height: 1.45; }

    .empty-state {
        padding: 2.4rem 1rem;
        text-align: center;
        color: var(--muted);
        border: 1px dashed var(--border);
        border-radius: 8px;
        font-size: 0.92rem;
    }

    [data-testid="stSidebar"] .eyebrow { margin-bottom: 0.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

EXAMPLES = [
    "Tendances 2026 du marché des VE en Europe",
    "Dernières fonctionnalités de Claude Opus 5",
    "Impact de l'IA générative sur le recrutement",
]

if "history" not in st.session_state:
    st.session_state.history = []
if "query_input" not in st.session_state:
    st.session_state.query_input = ""
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

st.markdown('<div class="eyebrow">Veille & synthèse</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Assistant de Recherche Web</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Interroge le web via Firecrawl, lit le contenu réel des meilleures pages '
    'et produit une synthèse sourcée — chaque affirmation renvoie à sa source d’origine.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="eyebrow">Configuration</div>', unsafe_allow_html=True)
    st.markdown("### Paramètres")
    limit = st.slider("Nombre de sources à consulter", min_value=3, max_value=8, value=SEARCH_LIMIT)
    st.caption("Plus de sources = synthèse plus complète, mais recherche plus longue.")

# Un clic sur un exemple doit remplir le champ avant que le widget text_input
# (key="query_input") ne soit instancié ci-dessous : Streamlit interdit de
# modifier session_state[key] après coup dans le même run.
if st.session_state.pending_query:
    st.session_state.query_input = st.session_state.pending_query

with st.form("search_form", clear_on_submit=False):
    query = st.text_input(
        "Sujet ou question de recherche :",
        key="query_input",
        placeholder="Ex : Quelles sont les tendances 2026 du marché des VE en Europe ?",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Lancer la recherche")

if not st.session_state.history:
    st.markdown('<div class="examples-label">Exemples</div>', unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for i, (col, ex) in enumerate(zip(cols, EXAMPLES)):
        with col:
            if st.button(ex, key=f"example_{i}", use_container_width=True):
                st.session_state.pending_query = ex
                st.rerun()

run_query = None
if submitted and query.strip():
    run_query = query.strip()
elif st.session_state.pending_query:
    run_query = st.session_state.pending_query
st.session_state.pending_query = None

if run_query:
    with st.spinner("Recherche et lecture des sources en cours..."):
        report, sources = research(run_query, limit=limit)
    st.session_state.history.insert(0, {"query": run_query, "report": report, "sources": sources})

if not st.session_state.history:
    st.markdown(
        '<div class="empty-state">Aucune recherche pour l’instant. '
        "Saisissez une question ci-dessus pour commencer.</div>",
        unsafe_allow_html=True,
    )

for idx, entry in enumerate(st.session_state.history):
    with st.container(border=True, key=f"report_card_{idx}"):
        st.markdown('<div class="query-label">Requête</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="query-text">{entry["query"]}</div>', unsafe_allow_html=True)
        st.markdown(entry["report"])

        if entry["sources"]:
            st.markdown(
                f'<div class="sources-label">{len(entry["sources"])} source(s) consultée(s)</div>',
                unsafe_allow_html=True,
            )
            src_cols = st.columns(2)
            for i, s in enumerate(entry["sources"]):
                domain = s.url.split("/")[2] if "/" in s.url else s.url
                snippet = s.content[:180] + ("…" if len(s.content) > 180 else "")
                with src_cols[i % 2]:
                    with st.container(border=True, key=f"src_{idx}_{i}"):
                        st.markdown(
                            '<div class="src-row">'
                            f'<div class="src-badge">{i + 1}</div>'
                            '<div>'
                            f'<div class="src-title"><a href="{s.url}" target="_blank">{s.title}</a></div>'
                            f'<div class="src-domain">{domain}</div>'
                            f'<div class="src-snippet">{snippet}</div>'
                            "</div>"
                            "</div>",
                            unsafe_allow_html=True,
                        )
    st.write("")
