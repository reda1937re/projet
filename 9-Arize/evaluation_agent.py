"""Script CLI : lance le pipeline multi-agents (Recherche -> Analyse -> Évaluation)
puis l'auto-évaluation Phoenix, et affiche/sauvegarde les résultats.

Toute la logique (agents, Team, appels API) vit dans policy_pipeline.py, partagée
avec l'interface Streamlit (app.py).
"""

from policy_pipeline import (
    ARIZE_TRACING_ACTIF,
    run_auto_evaluation,
    run_multi_agent_pipeline,
)

if ARIZE_TRACING_ACTIF:
    print("Tracing Arize actif.")
else:
    print("ARIZE_SPACE_ID / ARIZE_API_KEY absents : tracing Arize desactive, le pipeline continue sans observabilite.")

saisie_utilisateur = "Analyser l'état actuel et les implications futures des politiques agricoles britanniques et leur impact sur les communautés agricoles"

print("Génération d'analyse politique multi-agents...")
print("=" * 80)

contenu_final = run_multi_agent_pipeline(saisie_utilisateur, progress_callback=lambda label: print(f"-> {label}"))
print("\n===== SORTIE FINALE =====")
print(contenu_final)

# -------- Évaluation automatique --------
df_eval_router = run_auto_evaluation(saisie_utilisateur, contenu_final)

print("\n===== RÉSULTATS D'ÉVALUATION =====")
print(df_eval_router[["label", "explanation"]])
print("Résultats sauvegardés dans 'evaluation_analyse_politique.csv'")
df_eval_router.to_csv("evaluation_analyse_politique.csv", index=False)
