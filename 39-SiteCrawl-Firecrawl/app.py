import streamlit as st
from crawl_agent import digest, CRAWL_LIMIT

st.set_page_config(page_title="Exploration de Site", page_icon="◆", layout="wide")

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

    .sources-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 1.2rem 0 0.7rem 0; }
    div[class*="st-key-pg_"] { border-radius: 6px !important; border: 1px solid var(--border) !important; background: var(--surface) !important; }
    .src-row { display: flex; align-items: flex-start; gap: 0.65rem; }
    .src-badge {
        flex: none; width: 1.5rem; height: 1.5rem; border-radius: 4px; background: var(--accent-solid); color: white;
        font-size: 0.72rem; font-weight: 600; display: flex; align-items: center; justify-content: center;
    }
    .src-title { font-weight: 600; font-size: 0.9rem; color: var(--ink); margin-bottom: 0.1rem; }
    .src-title a { text-decoration: none; color: inherit; }
    .src-title a:hover { color: var(--accent); }
    .src-domain { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }

    .empty-state { padding: 2.4rem 1rem; text-align: center; color: var(--muted); border: 1px dashed var(--border); border-radius: 8px; font-size: 0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Firecrawl · crawl()</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Exploration de Site</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Explore un site en suivant ses liens, lit le contenu de plusieurs pages '
    'et en produit une fiche de synthèse sourcée.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Paramètres")
    limit = st.slider("Nombre de pages à explorer", min_value=2, max_value=10, value=CRAWL_LIMIT)
    st.caption("crawl() scrape réellement chaque page : gardez une limite basse pour économiser des crédits.")

with st.form("crawl_form"):
    url = st.text_input(
        "URL de départ :",
        placeholder="Ex : https://docs.firecrawl.dev/introduction",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Explorer le site")

if "result" not in st.session_state:
    st.session_state.result = None

if submitted and url.strip():
    with st.spinner("Exploration du site et lecture des pages en cours..."):
        report, pages = digest(url.strip(), limit=limit)
    st.session_state.result = {"url": url.strip(), "report": report, "pages": pages}

if not st.session_state.result:
    st.markdown(
        '<div class="empty-state">Aucune exploration pour l’instant. '
        "Saisissez une URL de départ ci-dessus pour commencer.</div>",
        unsafe_allow_html=True,
    )
else:
    res = st.session_state.result
    with st.container(border=True, key="report_card"):
        st.markdown('<div class="query-label">Site exploré</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="query-text">{res["url"]}</div>', unsafe_allow_html=True)
        st.markdown(res["report"])

        if res["pages"]:
            st.markdown(f'<div class="sources-label">{len(res["pages"])} page(s) explorée(s)</div>', unsafe_allow_html=True)
            for i, p in enumerate(res["pages"]):
                domain = p.url.split("/")[2] if "/" in p.url else p.url
                with st.container(border=True, key=f"pg_{i}"):
                    st.markdown(
                        '<div class="src-row">'
                        f'<div class="src-badge">{i + 1}</div>'
                        '<div>'
                        f'<div class="src-title"><a href="{p.url}" target="_blank">{p.title}</a></div>'
                        f'<div class="src-domain">{domain}</div>'
                        "</div>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
