import streamlit as st
from export_pdf import build_pdf
from pdf_analyzer import extract_pdf_content, analyze_question

# 🖥️ Interface utilisateur
st.set_page_config(page_title="Analyse PDF IA", page_icon="🔍", layout="wide")
st.title("🔍 Analyse Intelligente de PDF")
st.caption("Entrez l'URL d'un PDF public pour extraire et interroger son contenu.")

DEFAULT_URL = "https://www.pwc.com/gx/en/issues/analytics/assets/pwc-ai-analysis-sizing-the-prize-report.pdf"

if "pdf_url_cached" not in st.session_state:
    st.session_state.pdf_url_cached = None
    st.session_state.pdf_text = None
    st.session_state.messages = []

col_url, col_btn = st.columns([5, 1])
with col_url:
    pdf_url = st.text_input("🔗 URL du PDF :", value=DEFAULT_URL)
with col_btn:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    force_refresh = st.button("🔄 Réanalyser", use_container_width=True)

# ⚡ On ne relance Firecrawl que si l'URL a changé (ou sur demande explicite) :
# sans ce garde-fou, la moindre question posée relançait une extraction complète
# et consommait des crédits Firecrawl à chaque interaction.
if pdf_url and (pdf_url != st.session_state.pdf_url_cached or force_refresh):
    with st.spinner("⏳ Extraction du contenu en cours..."):
        extracted_text, error = extract_pdf_content(pdf_url)
    st.session_state.pdf_url_cached = pdf_url
    if error:
        st.error(f"❌ {error}")
        st.session_state.pdf_text = None
    else:
        st.session_state.pdf_text = extracted_text
        st.session_state.messages = []
        st.success("✅ Contenu extrait avec succès.")
elif pdf_url == st.session_state.pdf_url_cached and st.session_state.pdf_text is None:
    st.error("❌ La dernière extraction a échoué. Modifie l'URL ou clique sur 🔄 Réanalyser.")

# 📋 Affichage + interrogation
if st.session_state.pdf_text:
    with st.expander("📋 Voir le contenu extrait (nettoyé)"):
        st.text_area("Contenu PDF", st.session_state.pdf_text, height=400)

    st.subheader("❓ Posez vos questions au sujet du PDF")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.messages:
        st.download_button(
            "⬇️ Exporter la conversation en PDF",
            data=build_pdf(st.session_state.pdf_url_cached, st.session_state.messages),
            file_name="analyse_pdf_conversation.pdf",
            mime="application/pdf",
        )

    question = st.chat_input("Ex: Quel est l'impact économique de l'IA ?")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("🤔 Analyse de la question par l'agent..."):
                answer, error = analyze_question(
                    question, st.session_state.pdf_text, history=st.session_state.messages[:-1]
                )
                if error:
                    answer = f"❌ {error}"
            st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()
