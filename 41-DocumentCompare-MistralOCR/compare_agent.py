import os
from textwrap import dedent
from typing import Literal

from dotenv import load_dotenv
from mistralai.client import Mistral
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.mistral import MistralChat

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# mistral-large-latest a un contexte large, mais on garde une limite raisonnable
# par document pour que la comparaison reste rapide et abordable même sur de
# gros contrats.
MAX_CHARS_PER_DOC = 15000

mistral_client = Mistral(api_key=MISTRAL_API_KEY)


class Change(BaseModel):
    type: Literal["Ajout", "Suppression", "Modification"] = Field(
        description="Nature du changement entre le document A et le document B"
    )
    clause: str = Field(description="Section ou clause concernée (titre court)")
    detail: str = Field(description="Explication précise de ce qui a changé, en citant le contenu avant/après si pertinent")


class ComparisonResult(BaseModel):
    summary: str = Field(description="Résumé en 2-3 phrases de l'ampleur et de la nature globale des changements")
    changes: list[Change] = Field(description="Liste de tous les changements identifiés entre les deux documents")


comparison_agent = Agent(
    model=MistralChat(api_key=MISTRAL_API_KEY, id="mistral-large-latest"),
    name="Document Comparator",
    role="Expert en analyse comparative de documents (contrats, textes légaux, versions successives)",
    instructions=dedent("""
    Vous recevez le contenu de deux versions d'un même document (Document A = version
    précédente, Document B = version actuelle), tous deux extraits par OCR.

    Votre mission : identifier PRÉCISÉMENT ce qui a changé entre les deux versions.

    Règles strictes :
    - Ne signalez que des changements de FOND (clauses, montants, dates, obligations,
      conditions...). Ignorez les différences purement cosmétiques (mise en page,
      espacement, artefacts d'OCR sans impact sur le sens).
    - Pour chaque changement, précisez son type : "Ajout" (nouveau dans B, absent de A),
      "Suppression" (présent dans A, absent de B), ou "Modification" (présent dans les
      deux mais différent).
    - Soyez précis et factuel : citez ce qui a changé, pas une impression vague.
    - Si les deux documents sont identiques sur le fond, renvoyez une liste de
      changements vide et dites-le clairement dans le résumé.
    - Ne signalez jamais un changement que vous ne pouvez pas justifier avec le texte
      fourni.
    """),
    output_schema=ComparisonResult,
)


def ocr_pdf(file_path: str) -> str:
    """Extrait le contenu markdown d'un PDF via l'OCR Mistral."""
    uploaded = mistral_client.files.upload(
        file={"file_name": os.path.basename(file_path), "content": open(file_path, "rb")},
        purpose="ocr",
    )
    signed_url = mistral_client.files.get_signed_url(file_id=uploaded.id)
    ocr_response = mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": signed_url.url},
        include_image_base64=False,
    )
    return "\n".join(page.markdown for page in ocr_response.pages)


def compare_documents(text_a: str, text_b: str) -> ComparisonResult:
    """Compare deux textes de documents et retourne les changements structurés."""
    prompt = (
        f"Document A (version précédente) :\n\n{text_a[:MAX_CHARS_PER_DOC]}\n\n"
        f"---\n\n"
        f"Document B (version actuelle) :\n\n{text_b[:MAX_CHARS_PER_DOC]}"
    )
    result = comparison_agent.run(prompt)
    if not isinstance(result.content, ComparisonResult):
        return ComparisonResult(
            summary="La comparaison n'a pas pu être structurée correctement, réessayez.",
            changes=[],
        )
    return result.content


def compare_pdfs(path_a: str, path_b: str) -> tuple[ComparisonResult, str, str]:
    """OCR les deux PDFs puis les compare. Retourne (résultat, texte_a, texte_b)."""
    text_a = ocr_pdf(path_a)
    text_b = ocr_pdf(path_b)
    result = compare_documents(text_a, text_b)
    return result, text_a, text_b
