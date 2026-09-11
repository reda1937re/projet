import os
from textwrap import dedent

from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.groq import Groq
from agno.db.sqlite import SqliteDb

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# FAQ d'exemple : à remplacer par les vraies infos de l'entreprise (horaires,
# livraison, retours, tarifs...). L'agent ne doit répondre qu'à partir de ce
# qui est écrit ici pour tout ce qui concerne des faits sur l'entreprise —
# jamais inventer une politique ou un tarif.
COMPANY_NAME = "Acme Corp"
FAQ = dedent("""
    - Horaires du support : du lundi au vendredi, 9h-18h (heure de Paris).
    - Livraison : sous 3 à 5 jours ouvrés en France métropolitaine.
    - Retours : possibles sous 14 jours, produit non utilisé, remboursement sous 5 jours après réception.
    - Paiement : carte bancaire et PayPal acceptés. Pas de paiement à la livraison.
    - Contact humain : support@acme-corp.example ou ce numéro WhatsApp aux heures d'ouverture.
""")

# La mémoire de conversation est persistée en SQLite, une session par
# utilisateur (numéro WhatsApp) : sans ça, l'agent oublierait tout entre deux
# messages du même client, ce qui est inutilisable pour du support.
db = SqliteDb(db_file="support_sessions.db", session_table="whatsapp_support_sessions")

support_agent = Agent(
    model=Groq(api_key=GROQ_API_KEY, id="openai/gpt-oss-120b"),
    name="Customer Support Agent",
    role=f"Agent de support client WhatsApp pour {COMPANY_NAME}",
    instructions=dedent(f"""
    Vous êtes l'assistant support client de {COMPANY_NAME}, sur WhatsApp.

    Informations officielles de l'entreprise (seule source fiable pour ces sujets) :
    {FAQ}

    Règles strictes :
    - Répondez de façon professionnelle, chaleureuse et concise (messages WhatsApp courts,
      pas de longs pavés).
    - Pour toute question sur les horaires, livraisons, retours, paiements : basez-vous
      UNIQUEMENT sur les informations ci-dessus. N'inventez jamais un tarif, un délai ou
      une politique qui n'y figure pas.
    - Si vous ne savez pas répondre (question hors de ces informations, réclamation
      complexe, litige) : dites-le clairement, rassurez le client, et proposez de le
      mettre en relation avec un humain via support@acme-corp.example.
    - Souvenez-vous du contexte de la conversation en cours avec ce client (vous y avez
      accès automatiquement) pour ne pas lui faire répéter des informations déjà données.
    - Répondez dans la langue utilisée par le client.
    - Un emoji occasionnel est bienvenu, mais n'en abusez pas.
    """),
    db=db,
    add_history_to_context=True,
    # Limite le nombre d'échanges précédents rechargés à chaque message : une
    # conversation WhatsApp peut s'étaler sur des jours, pas besoin de tout
    # l'historique pour répondre à la question du moment.
    num_history_runs=10,
    markdown=False,
)


def get_response(message: str, session_id: str) -> str:
    """Génère la réponse de l'agent pour `message`, dans le contexte de la
    conversation `session_id` (le numéro WhatsApp de l'expéditeur).
    """
    response = support_agent.run(message, session_id=session_id)
    return response.content


if __name__ == "__main__":
    print(get_response("Bonjour, vous livrez en combien de temps ?", session_id="test_local"))
