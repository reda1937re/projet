"""Moteur partagé : pipeline multi-agents (Recherche -> Analyse -> Évaluation)
coordonné par un agno.team.Team, plus l'auto-évaluation Phoenix (llm_classify).

Utilisé à la fois par le script CLI (evaluation_agent.py) et par l'interface
Streamlit (app.py), pour éviter de dupliquer la définition des agents et la
logique d'exécution entre les deux.
"""

import os
import sys

# La console Windows utilise par défaut l'encodage cp1252, qui ne supporte pas
# certains caractères Unicode que les logs internes d'Agno ou les réponses du
# modèle peuvent contenir (ex. espace fine insécable " ") — ça faisait
# planter le script en plein milieu de l'exécution.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
import pandas as pd
from textwrap import dedent
from agno.agent import Agent
from agno.team import Team
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from arize.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation.agno import AgnoInstrumentor
from phoenix.evals import OpenAIModel, llm_classify

load_dotenv()

# -------- Configuration OpenTelemetry --------
# register() exige des identifiants non vides (ValueError sinon) : le tracing Arize
# est donc optionnel ici et ne s'active que si ARIZE_SPACE_ID/ARIZE_API_KEY sont définis,
# pour que le pipeline multi-agents reste utilisable sans compte Arize.
ARIZE_SPACE_ID = os.getenv("ARIZE_SPACE_ID")
ARIZE_API_KEY = os.getenv("ARIZE_API_KEY")
ARIZE_TRACING_ACTIF = bool(ARIZE_SPACE_ID and ARIZE_API_KEY)

if ARIZE_TRACING_ACTIF:
    tracer_provider = register(
        space_id=ARIZE_SPACE_ID,
        api_key=ARIZE_API_KEY,
        project_name="agent-politique-agricole",
    )
    AgnoInstrumentor().instrument(tracer_provider=tracer_provider)
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# Le script original utilisait OpenAI (gpt-4o) ; remplacé par Groq (compatible
# avec l'API OpenAI) pour réutiliser la clé GROQ_API_KEY déjà disponible.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_ID = "openai/gpt-oss-120b"

# -------- Agent 1: Recherche --------
AgentRecherche = Agent(
    name="AgentRecherche",
    model=Groq(id=GROQ_MODEL_ID, api_key=GROQ_API_KEY),
    tools=[DuckDuckGoTools()],
    description=dedent("""
        Vous êtes un assistant de recherche politique spécialisé dans la collecte de données récentes et crédibles sur :
        - Les politiques agricoles du Royaume-Uni, les programmes de subventions, les schémas de développement rural et les réglementations environnementales
        - Votre objectif est de récupérer des informations exploitables et des rapports vérifiés à partir de :

        • Publications DEFRA et NFU
        • Organismes de recherche scientifique et groupes de réflexion politique
        • Journaux commerciaux et journaux réputés du Royaume-Uni
        • Plateformes gouvernementales officielles (.gov.uk)
    """),
    instructions=dedent("""
        1. Découverte des Sources 🔍
           □ Rechercher les documents, rapports et articles les plus récents liés à la législation agricole britannique.
           □ Prioriser les données de DEFRA, études académiques, NFU et sources politiques de confiance.

        2. Filtrage des Informations ✅
           □ Éliminer le contenu dupliqué ou obsolète.
           □ Se concentrer sur les changements politiques les plus récents et régionalement pertinents.

        3. Extraction du Contexte Brut 📋
           □ Extraire les faits clés, mises à jour politiques et contexte pertinent en texte brut.
           □ Ne pas effectuer d'analyse - se concentrer uniquement sur la récupération d'informations.

        ⚠️ Limite-toi à 4-5 recherches ciblées maximum, puis rédige la synthèse avec ce que tu as trouvé.
        Ne cherche pas l'exhaustivité : mieux vaut une synthèse utile rapidement qu'une recherche infinie.
    """),
    expected_output=dedent("""
        # {Résumé de la Politique Agricole du Royaume-Uni 📄 Contexte Brut} 📋

        ## Données Collectées
        - **Source 1:** {...}
        - **Source 2:** {...}
        - **Source 3:** {...}

        ## Politiques et Programmes Pertinents
        - Politique A: {...}
        - Politique B: {...}
        - Schéma C: {...}

        ## Notes Environnementales et Économiques
        - Mises à jour des initiatives climatiques: {...}
        - Tendances des revenus agricoles: {...}

        ---
        Compilé par l'Agent de Recherche • Dernière Vérification: {heure_actuelle}
    """),
    markdown=True,
    debug_mode=True,
    # Les résultats bruts de web_search (plusieurs recherches x 10 résultats JSON
    # complets) font rapidement gonfler le contexte au-delà de la limite Groq
    # (8000 tokens/minute en tier gratuit) : on les compresse avant qu'ils ne
    # s'accumulent dans la conversation.
    compress_tool_results=True,
    # Sans limite, l'agent peut enchaîner des recherches web quasi indéfiniment sur
    # un sujet aussi vaste (observé : 20+ min sans jamais conclure). On plafonne le
    # nombre d'appels d'outils pour garantir un temps d'exécution raisonnable.
    tool_call_limit=6,
)

# -------- Agent 2: Analyse --------
AgentAnalyse = Agent(
    name="AgentAnalyse",
    model=Groq(id=GROQ_MODEL_ID, api_key=GROQ_API_KEY),
    description=dedent("""
        Vous êtes un analyste senior de politique agricole qui synthétise des évaluations structurées
        basées sur des documents politiques et des données d'intervenants. Vous fournissez des perspectives
        complètes, factuelles et régionalement conscientes couvrant :

        • Implications politiques sur l'agriculture et la biodiversité
        • Évaluations d'impact économique
        • Recommandations stratégiques pour le gouvernement et les parties prenantes
    """),
    instructions=dedent("""
        1. Révision Politique 📋
           □ Analyser les données brutes et identifier les principaux moteurs politiques.
           □ Relier les conclusions à la productivité agricole, au bien-être des exploitations et à la durabilité.

        2. Évaluation des Résultats 📊
           □ Quantifier l'impact sur les communautés rurales et les chaînes d'approvisionnement alimentaire.
           □ Intégrer les tendances environnementales, commerciales et économiques.

        3. Recommandations 💡
           □ Proposer des plans d'action multi-échelles (immédiat, moyen terme, long terme).
           □ Structurer les suggestions selon le type d'exploitation, la géographie et la zone prioritaire.

        4. Format et Clarté ✓
           □ Utiliser un formatage Markdown clair avec des en-têtes structurés.
           □ Assurer un flux logique de l'observation à la recommandation.
    """),
    expected_output=dedent("""
        # {Analyse de Politique Agricole du Royaume-Uni} 🌾

        ## Résumé Exécutif
        {Aperçu concis du paysage agricole actuel et des défis clés}

        | Région | Types d'Exploitations | Enjeux Clés | Schémas de Soutien |
        |--------|-------------|-------------|----------------|
        | Angleterre| ...        | ...         | ...            |
        | Pays de Galles | ...   | ...         | ...            |
        | ...    | ...         | ...         | ...            |

        ## Conclusions Clés
        - **Impact Environnemental:** {...}
        - **Viabilité Économique:** {...}
        - **Développement Rural:** {...}

        ## Analyse de Marché
        {Tendances actuelles de l'agriculture britannique et implications commerciales internationales}

        ## Recommandations
        1. **Actions Immédiates:** {...}
        2. **Stratégie à Moyen Terme:** {...}
        3. **Vision à Long Terme:** {...}

        ## Sources de Données
        {Liste numérotée des références avec dates et pertinence}

        ---
        Préparé par l'Analyste de Politique Agricole • Publié : {date_actuelle} • Dernière Mise à Jour : {heure_actuelle}
    """),
    markdown=True,
)

# -------- Agent 3: Évaluation --------
AgentEvaluateur = Agent(
    name="AgentEvaluateur",
    model=Groq(id=GROQ_MODEL_ID, api_key=GROQ_API_KEY),
    description=dedent("""
        Vous êtes un auditeur d'impact politique évaluant si un rapport de politique agricole britannique
        répond de manière significative aux besoins des "communautés agricoles". Vous évaluez si l'analyse
        est impactante basée sur :

        • Pertinence et couverture des défis agricoles actuels
        • Profondeur des perspectives sur les résultats économiques et environnementaux
        • Qualité et réalisme des recommandations politiques proposées
    """),
    instructions=dedent("""
        1. Tâche d'Évaluation 🎯
           □ Évaluer l'utilité globale du rapport politique.
           □ Comparer le contenu aux préoccupations agricoles du monde réel.

        2. Décision d'Étiquetage 🏷️
           □ Utiliser uniquement "impactant" ou "non impactant" comme étiquette finale.
           □ Être strict : n'attribuer "impactant" que si l'analyse est approfondie et axée sur la communauté.

        3. Explication du Raisonnement 🧠
           □ Après l'étiquetage, rédiger une explication étape par étape.
           □ Souligner ce qui rend le rapport fort ou faible d'un point de vue d'impact politique.

        ⚠️ La sortie doit commencer par un seul mot : impactant ou non impactant. Aucun autre caractère sur la première ligne.
    """),
    expected_output=dedent("""
        impactant

        L'analyse démontre profondeur et pertinence. Elle couvre la biodiversité, l'économie rurale et les risques de chaîne d'approvisionnement.
        La structure s'aligne avec les formats politiques et inclut des recommandations basées sur des données.
        Les différences régionales et les impacts socioéconomiques sont correctement abordés.

        ---
        Évalué par l'Auditeur d'Impact Politique • Vérifié : {date_actuelle}
    """),
    markdown=True,
)

# -------- Agent 4: Gestionnaire --------
# Le script original passait AgentRecherche/AgentAnalyse/AgentEvaluateur directement
# dans tools=[...] d'un Agent (pattern "agent-comme-outil"). Ce pattern n'existe plus
# dans la version installée d'agno (2.8.7) : un Agent ne délègue plus automatiquement
# à d'autres Agents passés en tools, il se contentait d'halluciner un faux plan en
# texte sans jamais les appeler. Le remplacement officiel pour orchestrer plusieurs
# agents est agno.team.Team, qui délègue réellement à ses "members".
AgentGestionnaire = Team(
    name="AgentGestionnaire",
    # Le leader du Team doit relire/synthétiser en un seul appel les rapports complets
    # de AgentRecherche + AgentAnalyse (souvent >8000 tokens à eux deux), ce qui dépasse
    # la limite Groq du modèle 120B (8000 tokens/minute en tier gratuit). Le modèle 20B,
    # plus léger, dispose d'un quota TPM plus élevé sur ce même tier et suffit pour ce
    # rôle de routage/synthèse (les agents spécialisés gardent le modèle 120B).
    model=Groq(id="openai/gpt-oss-20b", api_key=GROQ_API_KEY),
    members=[AgentRecherche, AgentAnalyse, AgentEvaluateur],
    description="Un agent orchestrateur coordonnant le flux d'évaluation complet de la politique agricole britannique.",
    instructions=dedent("""
        Étapes :
        1. Appeler AgentRecherche pour rassembler le contexte pertinent de la politique agricole britannique.
        2. Transmettre le contexte brut à AgentAnalyse pour produire une analyse structurée.
        3. Demander à AgentEvaluateur d'évaluer l'impact du rapport politique.

        Ne pas générer de texte vous-même. Router chaque tâche vers l'agent correct.
    """),
    expected_output="Rapport politique complet suivi d'une étiquette d'évaluation d'impact formelle et d'une explication.",
    markdown=True,
    debug_mode=True,
    # Idem : le Team accumule les sorties complètes de AgentRecherche + AgentAnalyse
    # pour synthétiser le rapport final, ce qui a fait dépasser la limite Groq
    # (8774 tokens demandés pour 8000 autorisés/minute) lors d'un premier test.
    compress_tool_results=True,
)

MEMBER_LABELS = {
    "agentrecherche": "🔎 Recherche en cours (web) — AgentRecherche...",
    "agentanalyse": "📊 Analyse structurée en cours — AgentAnalyse...",
    "agentevaluateur": "⚖️ Évaluation d'impact en cours — AgentEvaluateur...",
}


def run_multi_agent_pipeline(saisie_utilisateur: str, progress_callback=None) -> str:
    """Exécute le pipeline Recherche -> Analyse -> Évaluation via le Team, en
    streamant les événements pour suivre la progression réelle (quel agent est
    en train de tourner), et retourne le contenu final synthétisé.

    progress_callback(label: str), si fourni, est appelé à chaque fois qu'un
    nouveau membre du Team est délégué.
    """
    final_content = None
    for event in AgentGestionnaire.run(saisie_utilisateur, stream=True, stream_events=True):
        tool = getattr(event, "tool", None)
        if tool is not None and tool.tool_name == "delegate_task_to_member" and progress_callback:
            member_id = (tool.tool_args or {}).get("member_id", "")
            progress_callback(MEMBER_LABELS.get(member_id, f"🤖 {member_id} en cours..."))

        # "TeamRunCompleted" (avec le préfixe Team) n'est émis que par le Team
        # lui-même, jamais par les membres délégués (qui émettent "RunCompleted"
        # sans préfixe) : ça suffit à isoler la réponse finale synthétisée.
        if getattr(event, "event", None) == "TeamRunCompleted" and getattr(event, "content", None):
            final_content = event.content

    return final_content or "(Aucune réponse générée.)"


MODELE_EVAL_ROUTER = """
Vous êtes un bot d'aide IA qui vérifie l'impact de l'analyse de politique agricole britannique sur les communautés agricoles. Votre tâche est d'évaluer si l'analyse fournie est impactante.

Voici les données :
[DÉBUT DONNÉES]
************
[Input]: Ci-dessous se trouve l'entrée qui contient la saisie utilisateur et l'historique de conversation.
{input}

[Sortie Réelle]: Ci-dessous se trouve la sortie réelle générée par l'agent.
{actual_output}

[Sortie Attendue]: Ci-dessous se trouve le format de sortie attendu qui devrait contenir une analyse des politiques agricoles britanniques et leur impact sur les communautés agricoles.
{expected_output}
************
[FIN DONNÉES]

Déterminer si l'analyse est impactante ou non impactante basé sur l'entrée, la sortie réelle et le format attendu.
"""


def run_auto_evaluation(saisie_utilisateur: str, contenu_final: str) -> pd.DataFrame:
    """Fait juger le rapport final par un second modèle (Phoenix llm_classify),
    indépendamment de AgentEvaluateur, et retourne le DataFrame de résultat
    (colonnes 'label' et 'explanation' notamment).
    """
    donnees_reponse = {
        "input": [saisie_utilisateur],
        "actual_output": [contenu_final],
        "expected_output": [AgentAnalyse.expected_output],
    }
    df_reponse = pd.DataFrame(donnees_reponse)

    def format_template(row):
        return MODELE_EVAL_ROUTER.format(
            input=row["input"],
            actual_output=row["actual_output"],
            expected_output=row["expected_output"],
        )

    df_reponse["formatted_prompt"] = df_reponse.apply(format_template, axis=1)

    return llm_classify(
        dataframe=df_reponse,
        template=MODELE_EVAL_ROUTER,
        model=OpenAIModel(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=GROQ_MODEL_ID,
        ),
        rails=["not impactful", "impactful"],
        provide_explanation=True,
        concurrency=1,
    )
