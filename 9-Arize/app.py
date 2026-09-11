import streamlit as st

from policy_pipeline import (
    ARIZE_TRACING_ACTIF,
    GROQ_API_KEY,
    run_auto_evaluation,
    run_multi_agent_pipeline,
)

st.set_page_config(page_title="Politique Agricole - Multi-Agents", page_icon="🌾", layout="wide")
st.title("🌾 Analyse Multi-Agents de Politique Agricole")
st.caption(
    "Un Gestionnaire délègue à 3 agents spécialisés — Recherche (web), Analyse, Évaluation d'impact — "
    "puis un second modèle (Phoenix) juge indépendamment si le rapport final est impactant."
)

if not GROQ_API_KEY:
    st.error("GROQ_API_KEY est introuvable. Ajoute-le dans le fichier .env à la racine du projet.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Paramètres")
    if ARIZE_TRACING_ACTIF:
        st.success("Tracing Arize actif")
    else:
        st.info("Tracing Arize désactivé (ARIZE_SPACE_ID / ARIZE_API_KEY absents). Le pipeline fonctionne quand même.")

    st.caption(
        "⚠️ Ce pipeline enchaîne plusieurs appels Groq (recherche web incluse) et peut prendre "
        "**3 à 8 minutes**, selon la charge du quota gratuit Groq (8000 tokens/minute)."
    )

DEFAULT_QUESTION = (
    "Analyser l'état actuel et les implications futures des politiques agricoles "
    "britanniques et leur impact sur les communautés agricoles"
)

saisie_utilisateur = st.text_area("Sujet à analyser", value=DEFAULT_QUESTION, height=100)
lancer = st.button("🚀 Lancer l'analyse multi-agents", use_container_width=True)

if "resultat" not in st.session_state:
    st.session_state.resultat = None

if lancer:
    if not saisie_utilisateur.strip():
        st.warning("⚠️ Décris un sujet à analyser avant de lancer le pipeline.")
    else:
        progress_placeholder = st.empty()
        progress_placeholder.info("🚀 Démarrage du pipeline...")
        try:
            contenu_final = run_multi_agent_pipeline(
                saisie_utilisateur,
                progress_callback=lambda label: progress_placeholder.info(label),
            )
            progress_placeholder.info("🧪 Auto-évaluation du rapport (Phoenix)...")
            df_eval = run_auto_evaluation(saisie_utilisateur, contenu_final)
            progress_placeholder.empty()
            st.session_state.resultat = {
                "saisie": saisie_utilisateur,
                "contenu_final": contenu_final,
                "label": df_eval["label"].iloc[0],
                "explanation": df_eval["explanation"].iloc[0],
                "df": df_eval,
            }
        except Exception as e:
            progress_placeholder.empty()
            st.error(f"❌ Erreur pendant le pipeline : {e}")

resultat = st.session_state.resultat
if resultat is None:
    st.info("👆 Décris un sujet puis clique sur **🚀 Lancer l'analyse multi-agents**.")
    st.stop()

st.divider()

label = resultat["label"]
if label == "impactful":
    st.success(f"🟢 Évaluation automatique : **{label}**")
else:
    st.warning(f"🟠 Évaluation automatique : **{label}**")
st.markdown(f"**Justification :** {resultat['explanation']}")

st.download_button(
    "⬇️ Exporter les résultats en CSV",
    data=resultat["df"].to_csv(index=False).encode("utf-8-sig"),
    file_name="evaluation_analyse_politique.csv",
    mime="text/csv",
)

st.divider()
st.markdown("### 📄 Rapport final")
st.markdown(resultat["contenu_final"])
