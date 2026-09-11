# app.py
"""
Interface Streamlit pour l'application de scraping d'annonces (immobilier,
véhicules, emploi, produits, services... toute catégorie)
"""

import csv
import io

import streamlit as st
from scraping import detect_language_code, get_ai_summary, save_to_airtable, scrape_and_parse

LANGUAGE_FLAGS = {
    "fr": "🇫🇷", "en": "🇬🇧", "ar": "🇸🇦", "es": "🇪🇸", "de": "🇩🇪",
    "it": "🇮🇹", "pt": "🇵🇹", "nl": "🇳🇱", "tr": "🇹🇷", "ru": "🇷🇺",
    "zh-cn": "🇨🇳", "ja": "🇯🇵", "ko": "🇰🇷",
}

# Interface utilisateur
st.set_page_config(page_title="Scraper d'Annonces IA", page_icon="🔍", layout="wide")
st.title("🔍 Scraper d'Annonces avec Analyse IA")
st.caption(
    "Extrait les annonces de n'importe quel site et de n'importe quelle catégorie "
    "(immobilier, véhicules, emploi, produits, services...), dans n'importe quelle langue, "
    "et les analyse via un agent IA (résumé, atouts, risques)."
)

# Session state
if "records" not in st.session_state:
    st.session_state.records = []
if "summaries" not in st.session_state:
    st.session_state.summaries = {}
if "scraped_url" not in st.session_state:
    st.session_state.scraped_url = None

# ------------------------------------------------------------------ Sidebar
with st.sidebar:
    st.header("🔗 Source")
    url = st.text_input(
        "URL à scraper",
        value="https://www.century21.fr/annonces/achat-maison/v-bordeaux/",
        help="Fonctionne sur n'importe quel site d'annonces (immobilier, véhicules, emploi, produits...), dans n'importe quelle langue.",
    )
    launch = st.button("🚀 Lancer l'extraction", use_container_width=True)

    if st.session_state.records:
        st.divider()
        st.header("📦 Résultats")
        st.caption(f"Source actuelle : {st.session_state.scraped_url}")

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["ref", "title", "price", "location", "description", "summary"]
        )
        writer.writeheader()
        for r in st.session_state.records:
            writer.writerow({**r, "summary": st.session_state.summaries.get(r["ref"], "")})
        st.download_button(
            "⬇️ Exporter en CSV",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="annonces_immobilieres.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if st.button("🗑️ Réinitialiser", use_container_width=True):
            st.session_state.records = []
            st.session_state.summaries = {}
            st.session_state.scraped_url = None
            st.rerun()

# ------------------------------------------------------------------ Scraper & analyser
if launch and url:
    progress_bar = st.progress(0.0, text="🔄 Récupération de la page...")

    def _on_progress(step, total):
        progress_bar.progress(step / total, text=f"🤖 Analyse du contenu ({step}/{total})...")

    try:
        st.session_state.records = scrape_and_parse(url, progress_callback=_on_progress)
        st.session_state.summaries = {}
        st.session_state.scraped_url = url
        progress_bar.empty()

        if st.session_state.records:
            st.success(f"✅ {len(st.session_state.records)} annonce(s) trouvée(s) !")
        else:
            st.warning("⚠️ Aucune annonce trouvée sur cette page.")
            st.info(
                "💡 Vérifie que l'URL pointe bien vers une liste d'annonces "
                "(et pas une page d'accueil ou une fiche individuelle)."
            )
    except Exception as e:
        progress_bar.empty()
        st.error(f"❌ Erreur : {e}")

# ------------------------------------------------------------------ Résultats
if not st.session_state.records:
    st.info("👈 Colle une URL de page d'annonces dans la barre latérale, puis clique sur **🚀 Lancer l'extraction**.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("📋 Annonces trouvées", len(st.session_state.records))
col2.metric("🤖 Résumés IA générés", len(st.session_state.summaries))
col3.metric(
    "📈 Progression",
    f"{len(st.session_state.summaries)}/{len(st.session_state.records)}",
)

search = st.text_input("🔍 Filtrer (prix, lieu, description...)", placeholder="ex: garage, Austin, 300000...")

to_analyze = [r for r in st.session_state.records if r["ref"] not in st.session_state.summaries]
if to_analyze and st.button(f"🤖 Analyser les {len(to_analyze)} annonce(s) restante(s) avec l'IA"):
    batch_progress = st.progress(0.0)
    for i, record in enumerate(to_analyze, 1):
        batch_progress.progress(i / len(to_analyze), text=f"Analyse {i}/{len(to_analyze)}...")
        st.session_state.summaries[record["ref"]] = get_ai_summary(record)
    batch_progress.empty()
    st.rerun()

st.divider()

records = st.session_state.records
if search:
    needle = search.lower()
    records = [
        r
        for r in records
        if needle in r["price"].lower()
        or needle in r["location"].lower()
        or needle in r["description"].lower()
        or needle in (r.get("title") or "").lower()
    ]
    st.caption(f"{len(records)} annonce(s) correspondant à « {search} »")

for i, record in enumerate(records, 1):
    title_suffix = f" — {record['title']}" if record.get("title") else ""
    lang_code = detect_language_code(record.get("description", ""))
    flag = LANGUAGE_FLAGS.get(lang_code, "🌐") if lang_code else ""

    with st.expander(f"{flag} Annonce {i} - {record['ref']}{title_suffix}"):
        has_location = record["location"] not in ("", "Non précisée")
        if has_location:
            badge_col1, badge_col2 = st.columns(2)
            badge_col1.markdown(f"### 💰 {record['price']}")
            badge_col2.markdown(f"### 📍 {record['location']}")
        else:
            st.markdown(f"### 💰 {record['price']}")
        st.markdown(f"**📝 Description :** {record['description']}")

        st.divider()

        # Résumé IA généré à la demande (et non pour toutes les annonces à
        # chaque rechargement : le contenu d'un expander s'exécute même
        # fermé, donc sans ce bouton explicite, 17 annonces = 17 appels IA
        # immédiats, même pour celles jamais consultées).
        if record["ref"] in st.session_state.summaries:
            st.markdown("### 🤖 Résumé IA")
            st.markdown(st.session_state.summaries[record["ref"]])
        elif st.button("🤖 Analyser cette annonce avec l'IA", key=f"analyze_{record['ref']}"):
            with st.spinner("🤖 Génération de l'analyse..."):
                st.session_state.summaries[record["ref"]] = get_ai_summary(record)
            st.rerun()

        # Envoi à Airtable (une fois l'analyse IA disponible)
        if record["ref"] in st.session_state.summaries and st.button(
            f"📊 Enregistrer annonce {i} dans Airtable", key=f"airtable_{record['ref']}"
        ):
            record_with_summary = {
                **record,
                "summary": st.session_state.summaries[record["ref"]],
            }

            success, message = save_to_airtable(record_with_summary)

            if success:
                st.success("✅ Enregistré dans Airtable")
            else:
                st.error(f"❌ {message}")
