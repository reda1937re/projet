"""Moteur partagé : génération + quantification d'incertitude (UQLM) + décision par agent IA.

Utilisé à la fois par le script CLI (allucination_detect.py) et par l'interface
Streamlit (app.py), pour éviter de dupliquer la définition de l'agent et la logique
de calcul entre les deux.
"""

import os

# sentence-transformers (utilisé par uqlm pour le scorer cosinus) importe
# transformers, qui essaie par défaut de charger TensorFlow en plus de PyTorch.
# Sur cette machine, la version de TensorFlow installée est incompatible avec
# la version de protobuf présente, ce qui fait planter l'import. On n'a besoin
# que du backend PyTorch : on doit désactiver TF AVANT tout import d'uqlm.
os.environ.setdefault("USE_TF", "0")

import pandas as pd
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.python import PythonTools
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from uqlm import BlackBoxUQ
from uqlm.utils import load_example_dataset, math_postprocessor

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

INSTRUCTION_MATH = "Lorsque vous résolvez ce problème mathématique, ne retournez que la réponse sans texte supplémentaire.\n"

# Les scorers sont passés explicitement à BlackBoxUQ (voir analyser_questions) pour
# contourner un bug de la version installée d'uqlm : quand scorers=None, l'attribut
# interne self.scorer_names reste None au lieu d'utiliser la liste par défaut, ce qui
# fait planter le calcul des scores.
DEFAULT_SCORERS = ["semantic_negentropy", "noncontradiction", "exact_match", "cosine_sim"]

agent_hallucination = Agent(
    name="AgentDetectionHallucination",
    role="Analyser les réponses incertaines et proposer une action appropriée.",
    model=Groq(id="openai/gpt-oss-120b", api_key=GROQ_API_KEY),
    tools=[PythonTools()],
    markdown=False,
    description="""
Vous êtes un agent spécialisé dans l'analyse des réponses générées par un modèle de langage.
Votre rôle est de détecter les réponses avec un risque élevé d'hallucination basé uniquement sur le score d'incertitude fourni par une méthode de quantification d'incertitude (UQ).
Vous n'avez pas accès à la vérité terrain et devez vous fier exclusivement au niveau d'incertitude pour décider s'il faut ACCEPTER, REFORMULER, ou REFUSER la réponse.
Vous opérez selon une logique basée sur des seuils et êtes censé fournir des sorties normalisées et cohérentes dans un format de décision clair.
""",
    instructions="""
🎯 Objectif:
Vous êtes un expert agent dans la détection d'hallucinations potentielles dans les réponses générées par un modèle de langage pour des questions mathématiques simples du jeu de données SVAMP.

📝 Entrée (fournie dans le prompt en texte brut):
1. La **question** mathématique posée (ex. "Tom a 3 pommes et achète 2 de plus...")
2. La **réponse** générée par le modèle (ex. "La réponse est 5.")
3. Le **score d'incertitude** associé (ex. 0.47), un flottant entre 0 et 1 fourni par la bibliothèque BlackBoxUQ.

🎯 Tâche:
Basé **uniquement** sur la valeur d'incertitude, déterminer l'action la plus appropriée selon ces règles:
🟢 Si incertitude < 0.2 → **ACCEPTER**
🟠 Si 0.2 ≤ incertitude ≤ 0.5 → **REFORMULER**
🔴 Si incertitude > 0.5 → **REFUSER**

📋 Format de Réponse (strictement requis):
Toujours répondre sur **une seule ligne**, commençant par l'action (**ACCEPTER**, **REFORMULER**, ou **REFUSER**) en **MAJUSCULES**, suivi d'une **justification concise en une phrase claire**.
⚠️ Ne pas inclure de texte supplémentaire ou de sauts de ligne.

🔴 Exemple:
REFORMULER L'incertitude est modérée (0.43), reformuler la réponse est recommandé.
""",
)


def calculer_incertitude(row):
    """Calculer le score d'incertitude à partir des métriques BlackBoxUQ.

    Une entropie_semantique plus faible = incertitude plus élevée.
    """
    incertitude_semantique = 1 - row.get("semantic_negentropy", 0)
    incertitude_correspondance_exacte = 1 - row.get("exact_match", 0)
    incertitude_cosinus = 1 - row.get("cosine_sim", 0)
    incertitude_contradiction = 1 - row.get("noncontradiction", 0)

    incertitude_primaire = incertitude_semantique
    incertitude_combinee = (incertitude_semantique + incertitude_correspondance_exacte + incertitude_cosinus) / 3

    return incertitude_primaire, {
        "semantique": incertitude_semantique,
        "correspondance_exacte": incertitude_correspondance_exacte,
        "cosinus": incertitude_cosinus,
        "contradiction": incertitude_contradiction,
        "combinee": incertitude_combinee,
    }


def load_svamp_questions(n: int = 5) -> list[str]:
    svamp = load_example_dataset("svamp", n=n)
    return list(svamp["question"])


async def analyser_questions(questions: list[str], progress_callback=None) -> pd.DataFrame:
    """Génère une réponse à chaque question, calcule l'incertitude, puis fait
    trancher un agent IA (ACCEPTER / REFORMULER / REFUSER) pour chacune.

    progress_callback(etape, i, total), si fourni, est appelé pour suivre la progression
    ("generation" une fois, puis "decision" pour chaque question analysée par l'agent).
    """
    if progress_callback:
        progress_callback("generation", 0, len(questions))

    prompts = [INSTRUCTION_MATH + q for q in questions]
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
    bbuq = BlackBoxUQ(llm=llm, scorers=DEFAULT_SCORERS)
    results = await bbuq.generate_and_score(prompts)
    df = results.to_df()

    # bbuq.to_df() ne contient pas la question d'origine (seulement le prompt
    # complet avec l'instruction ajoutée) : on la rajoute explicitement, sinon
    # l'agent de décision ne reçoit jamais la vraie question (bug du script d'origine).
    df["question"] = questions

    if "response" in df.columns:
        df["sortie_traitee"] = df["response"].apply(math_postprocessor)
    elif "generation" in df.columns:
        df["sortie_traitee"] = df["generation"].apply(math_postprocessor)
    else:
        df["sortie_traitee"] = None

    donnees_incertitude = []
    for _, row in df.iterrows():
        incertitude, detail = calculer_incertitude(row)
        donnees_incertitude.append({"incertitude": incertitude, **detail})
    df = pd.concat([df, pd.DataFrame(donnees_incertitude)], axis=1)

    decisions = []
    for i, row in df.iterrows():
        if progress_callback:
            progress_callback("decision", i + 1, len(df))

        response = row.get("response") or row.get("generation", "")
        incertitude = row.get("incertitude", 1.0)
        contexte_prompt = f"""
Question : {row["question"]}
Réponse : {response}
Incertitude : {incertitude:.3f}
""".strip()

        try:
            reponse_agent = agent_hallucination.run(contexte_prompt)
            decision = reponse_agent.content if hasattr(reponse_agent, "content") else str(reponse_agent)
        except Exception as e:
            decision = f"ERREUR: {e}"

        decisions.append(decision)

    df["decision_agent"] = decisions
    return df
