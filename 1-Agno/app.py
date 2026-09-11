import streamlit as st

from export_chat import build_docx, build_pdf
from rag_engine import GROQ_API_KEY, KnowledgeBase, build_agent, extract_text_from_pdf, load_embedder

st.set_page_config(page_title="Assistant Articles Multilingue", page_icon="📚")

st.markdown(
    """
    <style>
    .stChatMessage p, .stMarkdown p { direction: auto; unicode-bidi: plaintext; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Chargement du modèle d'embeddings...")
def get_embedder():
    return load_embedder()


def get_knowledge_base() -> KnowledgeBase:
    if "kb" not in st.session_state:
        st.session_state.kb = KnowledgeBase(get_embedder())
    return st.session_state.kb


def get_agent(kb: KnowledgeBase):
    if "agent" not in st.session_state or st.session_state.get("agent_kb") is not kb:
        st.session_state.agent = build_agent(kb)
        st.session_state.agent_kb = kb
    return st.session_state.agent


def main():
    st.title("📚 Assistant Articles — FR / EN / عربي")
    st.caption(
        "Ajoute un ou plusieurs articles (texte collé ou fichier PDF/TXT), "
        "puis pose tes questions dans la langue de ton choix."
    )

    if not GROQ_API_KEY:
        st.error("GROQ_API_KEY est introuvable. Ajoute-le dans le fichier .env à la racine du projet.")
        st.stop()

    kb = get_knowledge_base()

    if "sources" not in st.session_state:
        st.session_state.sources = []
    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.header("📄 Articles")

        pasted_text = st.text_area("Coller un article (n'importe quelle langue)", height=150)
        pasted_title = st.text_input("Titre de l'article collé", placeholder="ex: Article économie")
        if st.button("Ajouter le texte collé", use_container_width=True):
            if pasted_text.strip():
                title = pasted_title.strip() or f"Article collé #{len(st.session_state.sources) + 1}"
                with st.spinner("Indexation de l'article..."):
                    added = kb.add_document(pasted_text, title)
                if added:
                    st.session_state.sources.append(title)
                    st.success(f"{added} passages ajoutés depuis « {title} ».")
                else:
                    st.warning("Le texte collé est trop court pour être indexé.")
            else:
                st.warning("Colle d'abord un texte.")

        uploaded_files = st.file_uploader(
            "Ou importer des fichiers (PDF / TXT)", type=["pdf", "txt"], accept_multiple_files=True
        )
        if uploaded_files and st.button("Ajouter les fichiers", use_container_width=True):
            for f in uploaded_files:
                if f.name in st.session_state.sources:
                    continue
                with st.spinner(f"Indexation de « {f.name} »..."):
                    if f.name.lower().endswith(".pdf"):
                        text = extract_text_from_pdf(f)
                    else:
                        text = f.read().decode("utf-8", errors="ignore")
                    added = kb.add_document(text, f.name)
                if added:
                    st.session_state.sources.append(f.name)
                    st.success(f"{added} passages ajoutés depuis « {f.name} ».")

        if st.session_state.sources:
            st.divider()
            st.subheader("Articles indexés")
            for src in list(st.session_state.sources):
                col1, col2 = st.columns([4, 1])
                col1.write(f"• {src}")
                if col2.button("🗑️", key=f"del-{src}"):
                    kb.remove_source(src)
                    st.session_state.sources.remove(src)
                    st.rerun()

            if st.button("Tout effacer", use_container_width=True):
                kb.clear()
                st.session_state.sources = []
                st.session_state.messages = []
                st.rerun()

        if st.session_state.messages:
            st.divider()
            st.subheader("💾 Exporter la conversation")
            st.download_button(
                "⬇️ Télécharger en PDF",
                data=build_pdf(st.session_state.messages, st.session_state.sources),
                file_name="conversation.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.download_button(
                "⬇️ Télécharger en Word",
                data=build_docx(st.session_state.messages, st.session_state.sources),
                file_name="conversation.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    if not st.session_state.sources:
        st.info("👈 Ajoute au moins un article dans la barre latérale pour commencer à poser des questions.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Pose ta question en français, arabe ou anglais...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        agent = get_agent(kb)
        with st.chat_message("assistant"):
            with st.spinner("Recherche dans les articles..."):
                answer = None
                last_error = None
                # Groq/Llama produit parfois un appel d'outil mal formé (erreur
                # "tool_use_failed") : c'est intermittent, un simple nouvel essai
                # suffit presque toujours.
                for attempt in range(3):
                    try:
                        response = agent.run(question)
                        answer = response.content
                        break
                    except Exception as e:
                        last_error = e
                if answer is None:
                    answer = (
                        "Désolé, le modèle a rencontré une erreur technique en essayant de répondre "
                        f"(même après plusieurs tentatives). Réessaie ta question. Détail : {last_error}"
                    )
            st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


if __name__ == "__main__":
    main()
