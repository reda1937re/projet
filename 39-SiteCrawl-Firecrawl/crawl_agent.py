import os
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions
from pydantic import BaseModel

from agno.agent import Agent
from agno.models.groq import Groq

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# crawl() scrape RÉELLEMENT chaque page visitée (contrairement à map) : c'est
# l'appel le plus coûteux en crédits Firecrawl et en tokens Groq, donc la
# limite par défaut reste volontairement basse.
CRAWL_LIMIT = 5
MAX_CHARS_PER_PAGE = 2500

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


class Page(BaseModel):
    title: str
    url: str
    content: str


digest_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Site Digest Writer",
    role="Expert en analyse et synthèse de sites web",
    instructions=dedent("""
    Vous recevez plusieurs pages numérotées (titre, URL, contenu) toutes issues du
    MÊME site web, obtenues par exploration automatique (crawl). Votre mission :
    produire une fiche de synthèse du site, basée UNIQUEMENT sur ces pages.

    Contenu attendu, en Markdown :

    ## Vue d'ensemble
    <de quoi parle ce site / cette section, en 2-3 phrases>

    ## Thèmes principaux
    <liste des sujets/sections identifiés, avec citation [n] de la ou des pages
    qui en parlent>

    ## Pages notables
    <2 à 5 pages qui semblent les plus importantes, avec une phrase sur chacune>

    Règles strictes :
    - N'inventez rien qui ne soit pas dans les pages fournies.
    - Citez systématiquement vos affirmations avec [1], [2]... renvoyant aux pages.
    - Si le contenu fourni est trop pauvre pour une vraie synthèse, dites-le
      clairement plutôt que de gonfler artificiellement la réponse.
    """),
    markdown=True,
)


def crawl_site(url: str, limit: int = CRAWL_LIMIT) -> list[Page]:
    """Explore un site à partir de `url` (en suivant les liens) et scrape chaque page visitée."""
    job = firecrawl.crawl(url, limit=limit, scrape_options=ScrapeOptions(formats=["markdown"]))

    pages = []
    for doc in job.data or []:
        markdown = (getattr(doc, "markdown", None) or "").strip()
        metadata = getattr(doc, "metadata", None)
        page_url = getattr(metadata, "url", None) if metadata else None
        title = (getattr(metadata, "title", None) if metadata else None) or page_url

        if not page_url or not markdown:
            continue
        pages.append(Page(title=title, url=page_url, content=markdown[:MAX_CHARS_PER_PAGE]))
    return pages


def digest(url: str, limit: int = CRAWL_LIMIT) -> tuple[str, list[Page]]:
    """Crawl le site puis demande au LLM une fiche de synthèse sourcée. Retourne (fiche, pages)."""
    pages = crawl_site(url, limit=limit)
    if not pages:
        return "Aucune page exploitable n'a été trouvée lors de l'exploration de ce site.", []

    pages_block = "\n\n".join(
        f"[{i}] {p.title} ({p.url})\n{p.content}" for i, p in enumerate(pages, 1)
    )
    prompt = f"Site exploré : {url}\n\nPages :\n\n{pages_block}"

    report = digest_agent.run(prompt)
    return report.content, pages
