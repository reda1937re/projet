import os
from textwrap import dedent

from dotenv import load_dotenv
from firecrawl import Firecrawl
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.groq import Groq

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# map() ne scrape aucun contenu (juste la découverte des URLs) : c'est l'appel
# Firecrawl le moins coûteux, on peut se permettre une limite plus large que
# pour search()/crawl() sans exploser le budget de crédits.
MAP_LIMIT = 40

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


class Link(BaseModel):
    url: str
    title: str


class Category(BaseModel):
    name: str = Field(description="Nom de la catégorie (ex: Documentation, Blog, Produit, API...)")
    urls: list[str] = Field(description="URLs de cette catégorie, reprises exactement telles que fournies")


class SiteMapResult(BaseModel):
    categories: list[Category]


categorizer_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Site Map Categorizer",
    role="Expert en architecture de site web",
    instructions=dedent("""
    Vous recevez une liste d'URLs (avec leur titre) découvertes sur un site web via
    l'outil de cartographie Firecrawl (map). Votre mission : les regrouper en
    catégories logiques et lisibles (ex: Documentation, Blog, Produit, API Reference,
    Tarifs, À propos, Légal, Autre...).

    Règles strictes :
    - Ne reformulez JAMAIS une URL : reprenez-la exactement telle qu'elle apparaît
      dans la liste fournie.
    - N'inventez aucune URL qui ne serait pas dans la liste d'entrée.
    - Choisissez des noms de catégories clairs, adaptés au site observé (ne pas
      forcer des catégories génériques si elles ne correspondent à rien).
    - Une URL qui ne correspond à aucune catégorie claire va dans "Autre".
    - Triez les catégories par nombre d'URLs décroissant.
    """),
    output_schema=SiteMapResult,
)


def explore_site(url: str, search: str | None = None, limit: int = MAP_LIMIT) -> list[Link]:
    """Découvre les URLs d'un site via Firecrawl map (rapide, sans scraping de contenu)."""
    result = firecrawl.map(url, search=search, limit=limit)
    links = []
    for item in result.links or []:
        if not item.url:
            continue
        links.append(Link(url=item.url, title=item.title or item.url))
    return links


def categorize(links: list[Link]) -> list[Category]:
    """Demande au LLM de regrouper les liens découverts en catégories lisibles."""
    if not links:
        return []

    links_block = "\n".join(f"{l.url} | {l.title}" for l in links)
    prompt = f"URLs découvertes ({len(links)}) :\n\n{links_block}"

    result = categorizer_agent.run(prompt)
    if not isinstance(result.content, SiteMapResult):
        # Le modèle n'a pas renvoyé de JSON structuré valide : on retombe sur une
        # unique catégorie "Toutes les pages" plutôt que de faire planter l'UI.
        return [Category(name="Toutes les pages", urls=[l.url for l in links])]
    return result.content.categories


def map_site(url: str, search: str | None = None, limit: int = MAP_LIMIT) -> tuple[list[Link], list[Category]]:
    """Découvre puis catégorise les URLs d'un site. Retourne (liens bruts, catégories)."""
    links = explore_site(url, search=search, limit=limit)
    categories = categorize(links)
    return links, categories
