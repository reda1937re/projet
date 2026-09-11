import os

# sentence-transformers (utilisé pour les embeddings locaux) importe transformers,
# qui essaie par défaut de charger TensorFlow en plus de PyTorch. La version de
# TensorFlow installée sur cette machine est incompatible avec la version de
# protobuf présente : on désactive TF avant tout import de la lib.
os.environ.setdefault("USE_TF", "0")

from textwrap import dedent
from agno.agent import Agent
from mistralai.client import Mistral
from agno.models.groq import Groq
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.tools.reasoning import ReasoningTools
from ddgs import DDGS
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from dotenv import load_dotenv
load_dotenv()

# Dossier du script : les chemins sont résolus par rapport à lui, pas au
# répertoire courant, pour que le script fonctionne peu importe d'où il est lancé.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKDOWN_DIR = os.path.join(SCRIPT_DIR, "Markdown")
DOCUMENT_DIR = os.path.join(SCRIPT_DIR, "Document")
LANCEDB_URI = os.path.join(SCRIPT_DIR, "tmp", "lancedb")

mistral_key = os.getenv("MISTRAL_API_KEY")
# Le script original utilisait OpenAI (chat + embeddings) ; remplacé par Groq
# pour le chat (clé GROQ_API_KEY déjà disponible) et par l'embedder Mistral
# pour les embeddings (Groq n'a pas d'API d'embeddings).
groq_key = os.getenv("GROQ_API_KEY")

if mistral_key:
    client = Mistral(api_key=mistral_key)
else:
    print("ERREUR: MISTRAL_API_KEY requis pour OCR")
    exit()

if not groq_key:
    print("ERREUR: GROQ_API_KEY requis")
    exit()

## OCR Function améliorée ###
def ocr_pdf(pdf_path, output_name=None):
    """Convertit un PDF en Markdown via OCR Mistral"""
    if not os.path.exists(pdf_path):
        print(f"ERREUR: PDF non trouvé - {pdf_path}")
        return False
    
    print(f"Traitement OCR de {pdf_path}...")
    
    try:
        # Upload du PDF
        uploaded_pdf = client.files.upload(
            file={
                "file_name": os.path.basename(pdf_path),
                "content": open(pdf_path, "rb"),
            },
            purpose="ocr"
        )

        # Obtenir URL signée
        signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)

        # Traitement OCR
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": signed_url.url,
            },
            include_image_base64=True
        )

        # Générer nom de sortie
        if output_name is None:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_name = f"{base_name}.md"

        # Sauvegarder en Markdown
        os.makedirs(MARKDOWN_DIR, exist_ok=True)
        output_path = os.path.join(MARKDOWN_DIR, output_name)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join([page.markdown for page in ocr_response.pages]))
        
        print(f"SUCCESS: {output_path} créé ({len(ocr_response.pages)} pages)")
        return True
        
    except Exception as e:
        print(f"ERREUR OCR {pdf_path}: {e}")
        return False
class DDGSTools:
    def __init__(self):
        self.ddgs = DDGS()
    
    def search(self, query, max_results=5):
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            return results
        except Exception as e:
            print(f"Erreur recherche: {e}")
            return []

# Dans votre agent
ddgs_tool = DDGSTools()

## Traitement de tous vos PDFs ###
def process_all_pdfs():
    """Traite tous les PDFs du dossier Document/"""
    document_folder = DOCUMENT_DIR
    
    if not os.path.exists(document_folder):
        print(f"ERREUR: Dossier {document_folder} non trouvé")
        return
    
    # Lister tous les PDFs
    pdf_files = [f for f in os.listdir(document_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print("Aucun PDF trouvé dans Document/")
        return
    
    print(f"PDFs trouvés: {pdf_files}")
    
    success_count = 0
    for pdf_file in pdf_files:
        pdf_path = os.path.join(document_folder, pdf_file)
        if ocr_pdf(pdf_path):
            success_count += 1
    
    print(f"\nTraitement terminé: {success_count}/{len(pdf_files)} PDFs convertis")
    
    # Lister les Markdown créés
    if os.path.exists(MARKDOWN_DIR):
        md_files = [f for f in os.listdir(MARKDOWN_DIR) if f.endswith('.md')]
        print(f"Fichiers Markdown créés: {md_files}")

## Configuration base de connaissances ###
# MarkdownKnowledgeBase(path=..., vector_db=...) a été remplacé par la classe
# unifiée Knowledge : le contenu se charge via add_content(path=...) plutôt
# qu'un argument du constructeur + .load(recreate=...).
knowledge_base = Knowledge(
    vector_db=LanceDb(
        table_name="freight_documents",
        uri=LANCEDB_URI,
        search_type=SearchType.hybrid,
        # L'API d'embeddings gratuite de Mistral est trop vite rate-limitée pour
        # indexer plusieurs documents d'un coup ; embedder local à la place.
        embedder=SentenceTransformerEmbedder(),
    ),
    # La valeur par défaut (10 documents) fait dépasser la limite Groq (8000
    # tokens/minute en tier gratuit) en un seul appel.
    max_results=3,
)
if os.path.exists(MARKDOWN_DIR) and any(f.endswith(".md") for f in os.listdir(MARKDOWN_DIR)):
    knowledge_base.add_content(path=MARKDOWN_DIR)

freight_agent = Agent(
    name="Freight Agent",
    # Le contexte (base de connaissances + ReasoningTools) dépasse régulièrement la
    # limite Groq du modèle 120B (8000 tokens/minute) ; le modèle 20B a un quota plus
    # élevé sur le tier gratuit.
    model=Groq(id="openai/gpt-oss-20b", api_key=groq_key),
    instructions=dedent("""
    You are a Freight Cost Estimator Agent that helps small import/export businesses estimate and compare shipping costs and timelines across major carriers.

    You have access to:
    - A knowledge base built from 2024 rate guides and surcharge tables for UPS, FedEx, and DHL (converted from PDF via OCR)
    - DDGS search for live data and missing information

    When analyzing shipping requests, search your knowledge base FIRST for official rates, then supplement with web search if needed.
    
    Always provide detailed cost breakdowns, delivery estimates, and clear recommendations based on the specific product dimensions and requirements.
    """),
    tools=[ReasoningTools(add_instructions=True), ddgs_tool],
    knowledge=knowledge_base,
    search_knowledge=True,
    compress_tool_results=True,
)

def load_knowledge_base():
    """Le contenu est déjà chargé à la construction de knowledge_base via add_content()."""
    if not (os.path.exists(MARKDOWN_DIR) and any(f.endswith('.md') for f in os.listdir(MARKDOWN_DIR))):
        print("Aucun fichier Markdown trouvé - utilisation de DDGS uniquement")

def full_response(message):
    print('--------Freight Agent Triggered--------')
    try:
        response = freight_agent.run(message)
        return response.content
    except Exception as e:
        print(f"Erreur: {e}")
        return f"Erreur lors du traitement: {str(e)}"

if __name__ == '__main__':
    print("=== FREIGHT AGENT OCR SETUP ===")
    
    # Étape 1: Traiter les PDFs (décommentez pour exécuter)
    #process_all_pdfs()
    #exit()  # Arrête après traitement OCR
    
    # Étape 2: Charger la base de connaissances
    load_knowledge_base()
    
    # Test
    test_message = """
    User Question: Ship from Chicago, IL to Miami, FL
    Product Specifications: Machine parts, Weight: 300 lbs, Dimensions: 36"x24"x18", Industrial equipment
    """
    
    print("\nTest agent...")
    result = full_response(test_message)
    print(f"\nRésultat:\n{result}")