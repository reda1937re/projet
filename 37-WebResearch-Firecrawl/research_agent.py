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

# Nombre de pages récupérées par recherche et taille max de contenu gardée par
# page : au-delà, le contenu cumulé envoyé au modèle dépasse la limite Groq
# (8000 tokens/minute en tier gratuit).
SEARCH_LIMIT = 5
MAX_CHARS_PER_SOURCE = 3000

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


class Source(BaseModel):
    title: str
    url: str
    content: str


synthesis_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Web Research Synthesizer",
    role="Expert en recherche web et synthèse d'information",
    instructions=dedent("""
    Vous recevez une question de recherche et une liste de sources web numérotées
    (titre, URL, extrait de contenu réellement scrapé sur la page).

    Votre mission :
    - Répondre à la question en synthétisant UNIQUEMENT les informations présentes
      dans les sources fournies. N'inventez rien et n'utilisez aucune connaissance
      externe non confirmée par une source.
    - Chaque affirmation importante doit être suivie d'une citation numérotée
      [1], [2], etc. renvoyant à la source correspondante.
    - Si plusieurs sources se contredisent, signalez-le explicitement plutôt que
      de trancher arbitrairement.
    - Si les sources fournies ne suffisent pas à répondre correctement, dites-le
      clairement au lieu de combler les trous par une supposition.
    - Répondez dans la langue de la question posée.

    Format de sortie obligatoire en Markdown :

    ## Synthèse
    <réponse structurée avec citations [1] [2] ...>

    ## Sources
    [1] <titre> — <url>
    [2] <titre> — <url>
    ...
    """),
    markdown=True,
)


def _extract_source(item) -> Optional[Source]:
    """Convertit un résultat Firecrawl (Document avec markdown scrapé) en Source exploitable."""
    markdown = (getattr(item, "markdown", None) or "").strip()
    metadata = getattr(item, "metadata", None)
    url = getattr(metadata, "url", None) if metadata else getattr(item, "url", None)
    title = (getattr(metadata, "title", None) if metadata else None) or getattr(item, "title", None) or url

    if not url or not markdown:
        # Certaines pages échouent silencieusement au scraping (JS-only, bloquées,
        # timeout) : on les ignore plutôt que de faire planter toute la recherche.
        return None

    return Source(title=title, url=url, content=markdown[:MAX_CHARS_PER_SOURCE])


def search_web(query: str, limit: int = SEARCH_LIMIT) -> list[Source]:
    """Recherche sur le web via Firecrawl et récupère le contenu markdown de chaque résultat."""
    result = firecrawl.search(
        query,
        limit=limit,
        scrape_options=ScrapeOptions(formats=["markdown"]),
    )

    sources = []
    for item in result.web or []:
        source = _extract_source(item)
        if source:
            sources.append(source)
    return sources


def research(query: str, limit: int = SEARCH_LIMIT) -> tuple[str, list[Source]]:
    """Recherche le web sur `query` et retourne (rapport de synthèse sourcé, sources utilisées)."""
    sources = search_web(query, limit=limit)
    if not sources:
        return "Aucune source exploitable n'a été trouvée pour cette recherche.", []

    sources_block = "\n\n".join(
        f"[{i}] {s.title} ({s.url})\n{s.content}" for i, s in enumerate(sources, 1)
    )
    prompt = f"Question de recherche : {query}\n\nSources :\n\n{sources_block}"

    report = synthesis_agent.run(prompt)
    return report.content, sources
