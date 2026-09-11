import asyncio
import sys

# Sur Windows, la console du serveur Streamlit utilise par défaut l'encodage
# cp1252, qui ne supporte pas les emojis que la bibliothèque Agno affiche dans
# ses logs internes (tool calls, etc.) — ça faisait planter agent.run().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st

from uq_pipeline import GROQ_API_KEY, analyser_questions, load_svamp_questions

st.set_page_config(page_title="Détecteur d'Hallucinations IA", page_icon="🧠", layout="wide")
st.title("🧠 Détecteur d'Hallucinations (Quantification d'Incertitude)")
st.caption(
    "Génère plusieurs réponses par question pour mesurer leur incertitude (UQLM), puis un agent IA "
    "décide s'il faut ACCEPTER, REFORMULER ou REFUSER la réponse — sans jamais connaître la bonne réponse."
)

if not GROQ_API_KEY:
    st.error("GROQ_API_KEY est introuvable. Ajoute-le dans le fichier .env à la racine du projet.")
    st.stop()

DECISION_STYLE = {
    "ACCEPTER": ("success", "🟢"),
    "REFORMULER": ("warning", "🟠"),
    "REFUSER": ("error", "🔴"),
}

if "results_df" not in st.session_state:
    st.session_state.results_df = None

with st.sidebar:
    st.header("⚙️ Paramètres")
    source = st.radio("Source des questions", ["Exemples SVAMP (maths)", "Mes propres questions"])

    if source == "Exemples SVAMP (maths)":
        n_questions = st.slider("Nombre de questions", 1, 10, 3)
        custom_questions = None
    else:
        st.caption("Une question par ligne.")
        custom_text = st.text_area(
            "Questions",
            height=150,
            placeholder="Combien font 12 + 7 ?\nQuelle est la capitale de la France ?",
        )
        custom_questions = [q.strip() for q in custom_text.splitlines() if q.strip()]

    st.caption(
        "⚠️ Chaque question déclenche ~6 appels au modèle (5 échantillons + 1 décision) : "
        "reste raisonnable, le quota gratuit Groq est limité par jour."
    )
    launch = st.button("🚀 Lancer l'analyse", use_container_width=True)

if launch:
    if source == "Exemples SVAMP (maths)":
        questions = load_svamp_questions(n=n_questions)
    else:
        questions = custom_questions or []

    if not questions:
        st.warning("⚠️ Ajoute au moins une question avant de lancer l'analyse.")
    else:
        progress_bar = st.progress(0.0, text="🔄 Génération des réponses et calcul de l'incertitude...")

        def _on_progress(etape, i, total):
            if etape == "generation":
                progress_bar.progress(0.15, text="🔄 Génération des réponses et calcul de l'incertitude...")
            elif etape == "decision":
                progress_bar.progress(0.15 + 0.85 * (i / total), text=f"🧠 Décision de l'agent ({i}/{total})...")

        try:
            df = asyncio.run(analyser_questions(questions, progress_callback=_on_progress))
            st.session_state.results_df = df
            progress_bar.empty()
        except Exception as e:
            progress_bar.empty()
            st.error(f"❌ Erreur pendant l'analyse : {e}")

df = st.session_state.results_df
if df is None:
    st.info("👈 Choisis une source de questions dans la barre latérale, puis clique sur **🚀 Lancer l'analyse**.")
    st.stop()

# ------------------------------------------------------------------ Résumé
decisions = [d.split()[0] if d.split() else "?" for d in df["decision_agent"]]
counts = {k: decisions.count(k) for k in ("ACCEPTER", "REFORMULER", "REFUSER")}

col1, col2, col3, col4 = st.columns(4)
col1.metric("📋 Questions analysées", len(df))
col2.metric("🟢 Acceptées", counts["ACCEPTER"])
col3.metric("🟠 À reformuler", counts["REFORMULER"])
col4.metric("🔴 Refusées", counts["REFUSER"])

st.download_button(
    "⬇️ Exporter les résultats en CSV",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultats_hallucination_uq.csv",
    mime="text/csv",
)

st.divider()

# ------------------------------------------------------------------ Détail par question
for i, row in df.iterrows():
    decision_word = row["decision_agent"].split()[0] if row["decision_agent"].split() else "?"
    style, emoji = DECISION_STYLE.get(decision_word, ("info", "❔"))

    with st.expander(f"{emoji} Q{i + 1} — {row['question'][:80]}{'...' if len(row['question']) > 80 else ''}"):
        st.markdown(f"**❓ Question :** {row['question']}")
        st.markdown(f"**💬 Réponse du modèle :** {row.get('response', row.get('generation', ''))}")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Incertitude", f"{row['incertitude']:.2f}")
        m2.metric("Sémantique", f"{row['semantique']:.2f}")
        m3.metric("Corresp. exacte", f"{row['correspondance_exacte']:.2f}")
        m4.metric("Cosinus", f"{row['cosinus']:.2f}")
        m5.metric("Combinée", f"{row['combinee']:.2f}")

        getattr(st, style)(f"**{row['decision_agent']}**")

        with st.popover("👀 Voir les réponses échantillonnées"):
            sampled = row.get("sampled_responses")
            if sampled:
                for j, s in enumerate(sampled, 1):
                    st.markdown(f"{j}. {s}")
            else:
                st.caption("Aucun échantillon disponible.")
