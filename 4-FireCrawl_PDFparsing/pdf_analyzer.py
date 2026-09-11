import re
import os
from firecrawl import FirecrawlApp
from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent
from dotenv import load_dotenv


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

# gpt-oss-120b supporte une fenêtre de contexte large (~131k tokens), mais le
# compte gratuit Groq est plafonné à 8000 tokens/minute (TPM) en on-demand :
# on reste nettement en dessous pour ne pas se faire rejeter par ce quota.
MAX_CONTEXT_CHARS = 20000

# 🔑 Initialisation de Firecrawl
firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

# 🤖 Définition de l'agent IA
pdf_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="PDF Analysis Agent",
    role="Expert en analyse de documents PDF",
    instructions=dedent("""
    Vous êtes un expert en analyse de documents PDF. Votre rôle est :
    1. Répondre aux questions précises sur le document
    2. Identifier les thèmes clés et structure logique

    Règles strictes :
    - Pour les Q/R : citer les pages/paragraphes pertinents si possible
    - Toujours vérifier la cohérence interne du document
    - Maintenir un ton professionnel et neutre
    - Répondre toujours dans la même langue que la question posée (français, arabe ou anglais)

    Format de réponse :
    🎯 Réponse concise
    💡 Contexte : [explication ou justification]
    📄 Source : [citation ou référence précise]
    """),
    markdown=True
)

def extract_pdf_content(pdf_url):
    try:
        # 🔍 Extraction via Firecrawl (essai des deux méthodes possibles)
        try:
            # Méthode v2 (nouvelle version)
            result = firecrawl.scrape(url=pdf_url, formats=['markdown'])
        except AttributeError:
            try:
                # Méthode v1 (ancienne version)
                result = firecrawl.scrape_url(url=pdf_url)
            except AttributeError:
                raise Exception("Méthode Firecrawl non trouvée. Vérifiez votre version de firecrawl-py")
        
        # 🔧 Accès au markdown dans result
        markdown_text = None
        
        # Pour la v2 de l'API
        if hasattr(result, 'markdown'):
            markdown_text = result.markdown
        # Pour la v1 de l'API ou structure différente
        elif hasattr(result, "data") and isinstance(result.data, list) and len(result.data) > 0:
            markdown_text = getattr(result.data[0], "markdown", None)
        # Autre structure possible
        elif isinstance(result, dict) and 'markdown' in result:
            markdown_text = result['markdown']
        
        if not markdown_text:
            return None, "Aucune donnée extraite. Vérifiez que le PDF n'est pas protégé."
        
        # 🧹 Nettoyage markdown
        cleaned = re.sub(r'!\[.*?\]\(.*?\)', '', markdown_text)  # supprime les images
        cleaned = re.sub(r'#+.*', '', cleaned, flags=re.MULTILINE)  # supprime les titres
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # lignes vides multiples
        extracted_text = cleaned.strip()
        
        if not extracted_text:
            return None, "Le contenu extrait est vide après nettoyage."
        
        return extracted_text, None
        
    except Exception as e:
        return None, f"Erreur lors de l'extraction: {e}"

def analyze_question(question, pdf_content, history=None, max_retries=2):
    history_block = ""
    if history:
        recent = history[-6:]  # les 3 derniers échanges suffisent pour le contexte
        turns = [f"{'Utilisateur' if h['role'] == 'user' else 'Assistant'} : {h['content']}" for h in recent]
        history_block = "\n\nHistorique récent de la conversation :\n" + "\n".join(turns)

    content_limit = MAX_CONTEXT_CHARS
    last_error = None
    for _ in range(max_retries + 1):
        prompt = f"{question}{history_block}\n\nContenu PDF extrait :\n{pdf_content[:content_limit]}"
        try:
            answer = pdf_agent.run(prompt)
            return answer.content, None
        except Exception as e:
            last_error = e
            # Deux causes différentes gérées ici : un appel d'outil mal formé
            # (transitoire, un nouvel essai identique suffit) ou un dépassement
            # du quota de tokens/minute (on réduit alors le contexte envoyé).
            if "rate_limit" in str(e).lower() or "tokens" in str(e).lower():
                content_limit = content_limit // 2
    return None, f"Erreur lors de l'analyse (après {max_retries + 1} tentatives) : {last_error}"