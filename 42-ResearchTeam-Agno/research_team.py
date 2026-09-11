import os
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

from agno.agent import Agent
from agno.team.team import Team
from agno.models.groq import Groq

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Le 120B est plus capable mais son quota Groq gratuit (8000 tokens/minute) est
# vite dépassé dès qu'on cumule recherche + vérification + rédaction dans une
# même minute ; le 20B a un quota nettement plus élevé (voir 20-Agno-Team pour
# le même constat). Tous les membres l'utilisent pour rester fiables ensemble.
MODEL_ID = "openai/gpt-oss-20b"


def groq_model(model_id: str = MODEL_ID) -> Groq:
    """Groq configuré avec un léger retry : un test réel avec 3 membres + un
    Vérificateur séparé a déclenché 96 dépassements de quota Groq (8000
    tokens/minute, tier gratuit) sur une seule exécution — chaque agent relaie
    tout le contenu précédent au suivant, donc le coût cumulé explose vite. Un
    retry court aide sur les dépassements ponctuels, mais la vraie solution a
    été de réduire l'équipe à 2 membres (voir plus bas).
    """
    return Groq(
        id=model_id,
        api_key=GROQ_API_KEY,
        retries=2,
        delay_between_retries=2,
        exponential_backoff=True,
    )

# Équipe à 2 membres (pas 3) et contenu volontairement compact : sur le tier
# gratuit Groq, chaque agent supplémentaire dans la chaîne "paie" à nouveau
# tout le contenu des étapes précédentes, ce qui fait exploser le total de
# tokens/minute bien plus vite qu'on ne l'imaginerait en ne regardant que la
# taille des sources elles-mêmes.
SEARCH_LIMIT = 3
MAX_CHARS_PER_SOURCE = 900

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


def firecrawl_search(query: str) -> str:
    """Recherche sur le web via Firecrawl et renvoie le contenu (markdown) des
    meilleurs résultats, numérotés [1], [2]... pour permettre des citations.
    Utilisez cet outil pour trouver de l'information factuelle et à jour sur
    n'importe quel sujet. Vous pouvez l'appeler plusieurs fois avec des requêtes
    différentes si le sujet a plusieurs facettes.
    """
    result = firecrawl.search(query, limit=SEARCH_LIMIT, scrape_options=ScrapeOptions(formats=["markdown"]))

    blocks = []
    for i, item in enumerate(result.web or [], 1):
        markdown = (getattr(item, "markdown", None) or "").strip()
        metadata = getattr(item, "metadata", None)
        url = getattr(metadata, "url", None) if metadata else None
        title = (getattr(metadata, "title", None) if metadata else None) or url
        if not url or not markdown:
            continue
        blocks.append(f"[{i}] {title} ({url})\n{markdown[:MAX_CHARS_PER_SOURCE]}")

    return "\n\n".join(blocks) if blocks else "Aucun résultat exploitable trouvé pour cette recherche."


# --- Agent 1 : Chercheur -----------------------------------------------------
# Seul membre à avoir un outil : contrairement à l'agent 37 (recherche
# précalculée en Python avant l'appel LLM), c'est ici le LLM lui-même qui
# décide quand et combien de fois chercher.
searcher_agent = Agent(
    model=groq_model(),
    name="Chercheur",
    role="Spécialiste de la recherche web",
    instructions=dedent("""
    Vous êtes chargé de rassembler de l'information factuelle et à jour sur le
    sujet demandé. Utilisez l'outil `firecrawl_search` au moins une fois — plusieurs
    fois si le sujet a plusieurs facettes ou angles distincts.

    Présentez votre résultat comme une liste de sources numérotées [1], [2]...
    avec, pour chacune : titre, URL, et les faits pertinents qu'elle contient.

    Ne résumez pas et ne tirez aucune conclusion : votre rôle est de RASSEMBLER
    la matière première brute, pas de la rédiger. Conservez la numérotation et
    les URLs exactes fournies par l'outil.
    """),
    tools=[firecrawl_search],
    # Les résultats bruts de firecrawl_search (plusieurs pages scrapées) peuvent
    # être volumineux : on les compresse pour rester sous la limite Groq
    # (8000 tokens/minute, tier gratuit).
    compress_tool_results=True,
    markdown=True,
)

# --- Agent 2 : Rédacteur / Vérificateur --------------------------------------
# La vérification est fusionnée dans les instructions du Rédacteur plutôt que
# confiée à un 3e agent séparé : un membre de plus dans la chaîne signifiait un
# aller-retour complet de plus via le leader, avec tout le contenu déjà
# accumulé à repayer en tokens — c'est ce qui faisait exploser le quota Groq.
writer_agent = Agent(
    model=groq_model(),
    name="Rédacteur",
    role="Rédacteur de rapports de synthèse sourcés, avec vérification croisée des faits",
    instructions=dedent("""
    Vous recevez les sources numérotées rassemblées par le Chercheur. Rédigez le
    rapport final destiné à l'utilisateur, en Markdown, en deux temps :

    1. Vérifiez d'abord mentalement si les sources se corroborent ou se
       contredisent entre elles, et si certaines affirmations ne reposent que
       sur une seule source faible.
    2. Rédigez ensuite le rapport avec cette structure :

    ## Synthèse
    <réponse structurée au sujet demandé, avec citations [1] [2]...>

    ## Points à nuancer
    <affirmations contradictoires entre sources, ou faiblement soutenues —
    omettez cette section s'il n'y en a aucune>

    ## Sources
    [1] <titre> — <url>
    [2] <titre> — <url>
    ...

    N'inventez rien qui ne soit pas dans les sources fournies par le Chercheur.
    """),
    markdown=True,
)

research_team = Team(
    members=[searcher_agent, writer_agent],
    # Le leader orchestre 2 échanges successifs (délégation à chaque membre) : on
    # utilise le modèle 20B, au quota Groq plus élevé que le 120B, pour éviter de
    # dépasser la limite de 8000 tokens/minute du tier gratuit sur ce cumul.
    model=groq_model(),
    mode="coordinate",
    # Force la délégation aux 2 membres dans l'ordre : le rapport final a besoin
    # des 2 apports, on ne laisse pas le leader décider de sauter une étape.
    delegate_to_all_members=True,
    instructions=dedent("""
    Vous coordonnez une équipe de 2 agents pour produire un rapport de recherche
    web fiable et sourcé sur le sujet demandé par l'utilisateur.

    Ordre de travail impératif :
    1. Déléguez d'abord au Chercheur : il doit rassembler des sources via son
       outil de recherche web.
    2. Déléguez ensuite au Rédacteur, en lui transmettant EXACTEMENT les
       sources rassemblées par le Chercheur (numérotation et URLs incluses) :
       il vérifie leur cohérence et rédige le rapport final.

    Renvoyez en sortie finale UNIQUEMENT le rapport produit par le Rédacteur
    (ne le résumez pas, ne le raccourcissez pas, ne le reformulez pas).
    """),
    markdown=True,
)


def run_research(query: str) -> tuple[Optional[str], Optional[str]]:
    """Lance l'équipe sur `query`. Retourne (rapport, erreur) : l'un des deux est
    toujours None.

    Nécessaire car un échec d'appel Groq (ex: quota TPM dépassé) ne lève pas
    toujours d'exception ici : Agno peut renvoyer le message d'erreur brut de
    l'API (JSON commençant par '{"error"') directement comme `result.content`,
    ce qui l'afficherait tel quel dans l'UI sans ce garde-fou.
    """
    try:
        result = research_team.run(query)
    except Exception as e:
        return None, f"Erreur pendant l'exécution de l'équipe : {e}"

    content = result.content
    if not isinstance(content, str) or not content.strip():
        return None, "L'équipe n'a pas produit de rapport exploitable, réessayez."
    if content.strip().startswith('{"error"'):
        return None, "Le fournisseur du modèle a temporairement refusé la requête (quota atteint). Réessayez dans quelques instants."
    return content, None
