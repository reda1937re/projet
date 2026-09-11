import streamlit as st
from map_agent import map_site, MAP_LIMIT

st.set_page_config(page_title="Cartographie de Site", page_icon="◆", layout="wide")

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

    div[class*="st-key-cat_"] {
        border-radius: 8px !important; border: 1px solid var(--border) !important;
        background: var(--surface) !important; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .cat-title { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); margin-bottom: 0.6rem; }
    .cat-count { color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; }
    .link-row { display: block; padding: 0.35rem 0; border-bottom: 1px solid var(--border); font-size: 0.86rem; }
    .link-row:last-child { border-bottom: none; }
    .link-row a { color: var(--ink); text-decoration: none; }
    .link-row a:hover { color: var(--accent); }

    .summary-bar {
        display: flex; gap: 1.5rem; padding: 0.9rem 1.1rem; border: 1px solid var(--border);
        border-radius: 8px; background: var(--surface); margin-bottom: 1.4rem; font-size: 0.85rem; color: var(--muted);
    }
    .summary-bar b { color: var(--ink); }

    .empty-state { padding: 2.4rem 1rem; text-align: center; color: var(--muted); border: 1px dashed var(--border); border-radius: 8px; font-size: 0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Firecrawl · map()</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Cartographie de Site</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Découvre toutes les URLs d’un site (sans scraper leur contenu) '
    'et les regroupe automatiquement en catégories lisibles.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Paramètres")
    limit = st.slider("Nombre d'URLs max", min_value=10, max_value=100, value=MAP_LIMIT, step=10)
    search_filter = st.text_input("Filtrer par mot-clé (optionnel)", placeholder="Ex : pricing")
    st.caption("map() est l'appel Firecrawl le moins coûteux : il ne lit pas le contenu des pages.")

with st.form("map_form"):
    url = st.text_input(
        "URL du site :",
        placeholder="Ex : https://docs.firecrawl.dev",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Cartographier le site")

if "result" not in st.session_state:
    st.session_state.result = None

if submitted and url.strip():
    with st.spinner("Découverte des URLs en cours..."):
        links, categories = map_site(url.strip(), search=search_filter.strip() or None, limit=limit)
    st.session_state.result = {"url": url.strip(), "links": links, "categories": categories}

if not st.session_state.result:
    st.markdown(
        '<div class="empty-state">Aucune cartographie pour l’instant. '
        "Saisissez une URL de site ci-dessus pour commencer.</div>",
        unsafe_allow_html=True,
    )
else:
    res = st.session_state.result
    st.markdown(
        f'<div class="summary-bar">'
        f'<span><b>{len(res["links"])}</b> URLs découvertes</span>'
        f'<span><b>{len(res["categories"])}</b> catégories</span>'
        f'<span>Site : <b>{res["url"]}</b></span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if not res["categories"]:
        st.markdown(
            '<div class="empty-state">Aucune URL trouvée pour ce site.</div>',
            unsafe_allow_html=True,
        )
    else:
        cols = st.columns(2)
        for i, cat in enumerate(res["categories"]):
            with cols[i % 2]:
                with st.container(border=True, key=f"cat_{i}"):
                    st.markdown(
                        f'<div class="cat-title">{cat.name} '
                        f'<span class="cat-count">({len(cat.urls)})</span></div>',
                        unsafe_allow_html=True,
                    )
                    rows = "".join(
                        f'<div class="link-row"><a href="{u}" target="_blank">{u}</a></div>'
                        for u in cat.urls[:15]
                    )
                    if len(cat.urls) > 15:
                        rows += f'<div class="link-row">… et {len(cat.urls) - 15} de plus</div>'
                    st.markdown(rows, unsafe_allow_html=True)
