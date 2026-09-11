import os
import re
from typing import Optional

import faiss
import numpy as np
import pymupdf
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from agno.agent import Agent
from agno.models.groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Modèle multilingue : couvre le français, l'arabe, l'anglais et ~50 autres langues,
# contrairement à "all-MiniLM-L6-v2" (anglais uniquement) utilisé avant.
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MIN_CHUNK_LEN = 40
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


def load_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def extract_text_from_pdf(file) -> str:
    # PyMuPDF est ~20x plus rapide que pypdf pour extraire le texte d'un PDF.
    data = file.read() if hasattr(file, "read") else file
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n\n".join(page.get_text() for page in doc)


def chunk_text(text: str, source: str) -> list[dict]:
    """Découpe en blocs de taille régulière avec chevauchement.

    L'extraction PDF insère un retour à la ligne après chaque ligne visuelle
    (pas après chaque paragraphe) : découper sur les "\n" produisait des
    centaines de micro-fragments à encoder un par un, ce qui rendait l'ajout
    d'un article très lent. On aplatit d'abord le texte, puis on tranche par
    fenêtre glissante alignée sur les mots.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunks = []
    start = 0
    n = len(normalized)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        if end < n:
            boundary = normalized.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        piece = normalized[start:end].strip()
        if len(piece) >= MIN_CHUNK_LEN:
            chunks.append({"content": piece, "source": source})
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


class KnowledgeBase:
    """Base de connaissances multilingue en mémoire, ré-indexable à la volée."""

    def __init__(self, embedder: SentenceTransformer):
        self.embedder = embedder
        self.chunks: list[dict] = []
        self.index: Optional[faiss.IndexFlatL2] = None

    def add_document(self, text: str, source: str) -> int:
        new_chunks = chunk_text(text, source)
        if not new_chunks:
            return 0
        # On n'encode que les nouveaux passages et on les ajoute à l'index
        # existant, au lieu de ré-encoder toute la base à chaque ajout.
        embeddings = self.embedder.encode(
            [c["content"] for c in new_chunks], convert_to_numpy=True, show_progress_bar=False
        )
        if self.index is None:
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)
        self.chunks.extend(new_chunks)
        return len(new_chunks)

    def remove_source(self, source: str) -> None:
        self.chunks = [c for c in self.chunks if c["source"] != source]
        self._rebuild_index()

    def clear(self) -> None:
        self.chunks = []
        self.index = None

    def _rebuild_index(self) -> None:
        if not self.chunks:
            self.index = None
            return
        texts = [c["content"] for c in self.chunks]
        embeddings = self.embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)

    def search(self, query: str, num_documents: int = 4) -> list[dict]:
        if not query or not query.strip() or self.index is None or not self.chunks:
            return []
        num_docs = min(num_documents, len(self.chunks))
        query_vec = self.embedder.encode([query], convert_to_numpy=True)
        _, indices = self.index.search(np.array(query_vec), num_docs)
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.chunks):
                c = self.chunks[idx]
                results.append({"content": c["content"], "meta_data": {"source": c["source"]}})
        return results


def build_agent(knowledge_base: KnowledgeBase) -> Agent:
    def retriever(agent, query, num_documents=4, **kwargs):
        if num_documents is None:
            num_documents = 4
        return knowledge_base.search(query, num_documents)

    return Agent(
        model=Groq(id="openai/gpt-oss-120b", api_key=GROQ_API_KEY),
        knowledge=None,
        search_knowledge=True,
        knowledge_retriever=retriever,
        instructions=[
            "Tu es un assistant qui répond aux questions en te basant uniquement sur les articles fournis dans la base de connaissances.",
            "Réponds toujours dans la même langue que la question posée (français, arabe ou anglais).",
            "Si l'information n'est pas présente dans les articles fournis, dis-le clairement au lieu d'inventer une réponse.",
        ],
    )
