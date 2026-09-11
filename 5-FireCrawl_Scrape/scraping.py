import os
from textwrap import dedent
from typing import Optional

import requests
from dotenv import load_dotenv
from firecrawl import Firecrawl
from langdetect import DetectorFactory, LangDetectException, detect
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.groq import Groq

DetectorFactory.seed = 0  # résultats de détection de langue déterministes

LANGUAGE_NAMES = {
    "fr": "French", "en": "English", "ar": "Arabic", "es": "Spanish", "de": "German",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "tr": "Turkish", "ru": "Russian",
    "zh-cn": "Chinese", "ja": "Japanese", "ko": "Korean",
}

# Charger les variables d'environnement
load_dotenv()

# Configuration API depuis les variables d'environnement
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Taille de chaque morceau de page envoyé à l'IA pour l'extraction : reste
# sous le quota gratuit Groq (8000 tokens/minute) même sur une grande page.
MAX_CHUNK_CHARS = 12000
# Certains sites renvoient des pages énormes (>140 000 caractères, filtres et
# contenus annexes inclus) : au-delà de ce nombre de morceaux, le temps de
# traitement et le risque de dépassement du quota Groq deviennent excessifs.
MAX_CHUNKS = 6

# Configuration FireCrawl
firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


# 📦 Schéma structuré : l'IA extrait directement des objets validés, quelle
# que soit la mise en page, la langue ou la CATÉGORIE du site (immobilier,
# véhicules, emploi, produits, services...) — fini le découpage par motifs de
# texte codés en dur comme "Ref :" ou "PARIS", qui ne marchait que sur un
# seul site immobilier en français.
class Listing(BaseModel):
    reference: Optional[str] = Field(None, description="Référence/ID de l'annonce si présent sur la page")
    title: Optional[str] = Field(None, description="Titre ou catégorie de l'annonce (ex: Maison, Toyota Corolla 2019, Développeur Python, iPhone 14)")
    price: Optional[str] = Field(None, description="Prix, salaire ou tarif affiché tel quel, avec sa devise d'origine")
    location: Optional[str] = Field(None, description="Localisation si pertinente (ville, adresse, région) ; vide si non applicable")
    description: str = Field("", description="Description de l'annonce, dans sa langue d'origine")


class ListingExtraction(BaseModel):
    listings: list[Listing] = Field(description="Toutes les annonces/offres distinctes trouvées dans le texte, quelle que soit leur catégorie")


extraction_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Listing Extractor",
    role="Expert en extraction de données d'annonces multilingue, toutes catégories",
    instructions=dedent("""
    Vous recevez le contenu brut (markdown) d'une page web listant des annonces ou offres —
    immobilier, véhicules, emploi, produits, services, ou toute autre catégorie de petites annonces —
    potentiellement dans n'importe quelle langue (français, anglais, arabe, etc.).

    Identifiez CHAQUE annonce distincte et extrayez, sans traduire ni reformuler :
    - référence/ID si présent
    - titre ou catégorie de l'annonce
    - prix, salaire ou tarif (avec sa devise d'origine)
    - localisation si pertinente pour ce type d'annonce
    - description

    Ignorez tout ce qui n'est pas une annonce individuelle (menus, filtres de recherche, publicités, pied de page).
    Si une information est absente ou non applicable à cette catégorie d'annonce, laissez le champ vide
    plutôt que d'inventer une valeur.
    """),
    output_schema=ListingExtraction,
)

# Agent IA
listing_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Listing Analyzer",
    role="Expert en analyse d'annonces, toutes catégories",
    instructions=dedent("""
    Vous êtes un expert en analyse d'annonces et de petites annonces (immobilier, véhicules, emploi,
    produits, services, ou toute autre catégorie).

    Votre mission pour chaque annonce est :
    - Générer un résumé clair et concis, adapté à sa catégorie.
    - Identifier les atouts principaux (prix, caractéristiques, localisation si pertinente, etc.).
    - Identifier les risques ou signaux d'alerte potentiels (prix anormal, manque d'information,
      incohérences internes, formulation suspecte typique des arnaques).

    ⚠️ Règles strictes :
    - Adaptez votre analyse à la catégorie réelle de l'annonce (ne pas parler de "quartier" pour une
      offre d'emploi, ni de "salaire" pour un bien immobilier, etc.).
    - Répondez toujours dans la langue du champ "description" de l'annonce (détectez-la automatiquement),
      même si la description est courte : ignorez la langue des libellés du prompt lui-même.
    - Si un élément de localisation mentionné dans la description n'est PAS cohérent avec le champ
      "location", signalez-le explicitement.
    - Ne jamais faire d'affirmation sans confirmation croisée avec les données fournies.
    - Si une information importante et attendue pour cette catégorie est absente, mentionnez-le dans les risques.

    📝 Format de sortie obligatoire en Markdown clair (adaptez les libellés à la langue de l'annonce) :
    **Résumé** : ...

    ✅ **Atouts** :

    ⚠️ **Risques / Incohérences** :

    ⚡ Répondez uniquement en markdown bien formaté. Ne sortez jamais de ce format.
    """),
    markdown=True,
)


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def extract_listings(content: str, progress_callback=None) -> list[dict]:
    """Extrait les annonces d'un texte/markdown via l'IA, en plusieurs passes si la page est longue.

    progress_callback(chunk_index, total_chunks), si fourni, est appelé avant chaque passe
    pour permettre à l'interface d'afficher une progression.
    """
    records = []
    seen = set()

    all_chunks = _chunks(content, MAX_CHUNK_CHARS)[:MAX_CHUNKS]
    total = len(all_chunks)

    for i, chunk in enumerate(all_chunks, 1):
        if progress_callback:
            progress_callback(i, total)
        if not chunk.strip():
            continue
        try:
            result = extraction_agent.run(chunk)
            data = result.content
        except Exception as e:
            print(f"Debug - échec d'extraction sur un morceau de page : {e}")
            continue

        if not isinstance(data, ListingExtraction):
            # Le modèle n'a parfois pas renvoyé de JSON structuré valide pour ce
            # morceau (contenu inhabituel) : on l'ignore plutôt que de planter.
            print(f"Debug - réponse non structurée sur le morceau {i}, ignoré : {str(data)[:200]}")
            continue

        for item in data.listings:
            key = (item.reference or "", item.price or "", (item.description or "")[:80])
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "ref": item.reference or f"annonce-{len(records) + 1}",
                    "title": item.title or "",
                    "price": item.price or "Non précisé",
                    "location": item.location or "Non précisée",
                    "description": item.description or "",
                }
            )

    return records


def scrape_and_parse(url, progress_callback=None):
    """Scrape une URL et retourne les annonces extraites par l'IA (n'importe quel site, n'importe quelle langue)."""
    try:
        scrape_result = firecrawl.scrape(url, formats=["markdown"])

        markdown_content = None
        if hasattr(scrape_result, "markdown"):
            markdown_content = scrape_result.markdown
        elif isinstance(scrape_result, dict) and "markdown" in scrape_result:
            markdown_content = scrape_result["markdown"]

        if not markdown_content:
            raise ValueError("Impossible d'extraire le contenu de la page (aucun markdown retourné).")

        print(f"Debug - contenu récupéré : {len(markdown_content)} caractères")
        return extract_listings(markdown_content, progress_callback=progress_callback)

    except Exception as e:
        print(f"Erreur dans scrape_and_parse: {e}")
        raise


def detect_language_code(text: str) -> Optional[str]:
    """Détecte le code langue (ex: 'fr', 'en', 'ar') ; None si le texte est trop court/ambigu."""
    if not text or len(text.strip()) < 8:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def _detect_language_name(text: str) -> Optional[str]:
    code = detect_language_code(text)
    return LANGUAGE_NAMES.get(code, code) if code else None


def get_ai_summary(record):
    """Génère le résumé IA pour une annonce, dans la langue de l'annonce."""
    description = record.get("description", "") or ""
    # Une description très courte (ex: "4 beds 2 baths 1,527 sq. ft.") est trop
    # ambiguë pour que le modèle infère fiablement la langue tout seul : on la
    # détecte donc explicitement plutôt que de lui laisser deviner.
    detected = _detect_language_name(description) or _detect_language_name(f"{record.get('title', '')} {description}")
    lang_instruction = f'Respond entirely in {detected}.' if detected else "Respond in the same language as the description below."

    # Les libellés ci-dessous sont volontairement en anglais et neutres : des
    # labels français faisaient parfois basculer la réponse en français même
    # pour une annonce anglophone dont la description était courte.
    prompt = f"""Listing / classified ad ({lang_instruction}):

reference: {record.get('ref')}
title: {record.get('title')}
price: {record.get('price')}
location: {record.get('location')}
description: {description}
"""

    summary = listing_agent.run(prompt)
    return summary.content


def save_to_airtable(record):
    """Sauvegarde un enregistrement dans Airtable."""
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID):
        return False, "Airtable non configuré : ajoute AIRTABLE_API_KEY, AIRTABLE_BASE_ID et AIRTABLE_TABLE_ID au fichier .env."

    enriched_record = {
        "ref": str(record.get("ref", "")),
        "price": str(record.get("price", "")),
        "location": str(record.get("location", "")),
        "description": str(record.get("description", "")),
        "summary": str(record.get("summary", "")),
    }

    response = requests.post(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}",
        headers={
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"fields": enriched_record},
    )

    return response.status_code == 200, response.text
