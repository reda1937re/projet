import os
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv
from firecrawl import Firecrawl

from agno.agent import Agent
from agno.models.groq import Groq

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# scrape() ne lit qu'UNE page : on peut se permettre de garder beaucoup plus de
# contenu que pour search()/crawl() (qui cumulent plusieurs pages dans le même
# prompt) tout en restant sous la limite Groq (8000 tokens/minute, tier gratuit).
MAX_CONTENT_CHARS = 12000

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

page_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Page Analyzer",
    role="Expert en analyse de contenu web",
    instructions=dedent("""
    Vous recevez le contenu markdown d'UNE page web, et soit une question précise,
    soit une demande de résumé général.

    - Si une question est posée : répondez-y en vous basant UNIQUEMENT sur le
      contenu fourni. Si la page ne contient pas la réponse, dites-le clairement
      plutôt que d'inventer.
    - Si aucune question n'est posée : produisez un résumé structuré en Markdown
      avec les points clés de la page.
    - Répondez dans la langue de la question (ou du contenu si pas de question).
    """),
    markdown=True,
)


def scrape_page(url: str) -> Optional[str]:
    """Scrape une page via Firecrawl et retourne son contenu markdown (None si échec)."""
    result = firecrawl.scrape(url, formats=["markdown"])
    markdown = getattr(result, "markdown", None)
    if not markdown or not markdown.strip():
        return None
    return markdown.strip()


def analyze_page(url: str, question: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Scrape `url` puis répond à `question` (ou résume la page si absente).

    Retourne (réponse, erreur) : l'un des deux est toujours None.
    """
    content = scrape_page(url)
    if content is None:
        return None, "Impossible d'extraire le contenu de cette page (site bloqué, JS-only, ou page vide)."

    truncated = content[:MAX_CONTENT_CHARS]
    if question and question.strip():
        prompt = f"Question : {question.strip()}\n\nContenu de la page ({url}) :\n\n{truncated}"
    else:
        prompt = f"Résume cette page ({url}) :\n\n{truncated}"

    answer = page_agent.run(prompt)
    return answer.content, None
