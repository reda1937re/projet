import asyncio

import pandas as pd

from uq_pipeline import analyser_questions, load_svamp_questions


async def main():
    # 📊 1. Charger le jeu de données SVAMP
    questions = load_svamp_questions(n=5)
    print("------------------------📊 Questions------------------------")
    for idx, q in enumerate(questions, 1):
        print(f"{idx}. {q}")
    print("-----------------------------------------------------------")

    # 🔍 2. Génération + scoring d'incertitude + décision de l'agent
    def _progress(etape, i, total):
        if etape == "generation":
            print("\n🤖 Génération des réponses et calcul de l'incertitude...")
        elif etape == "decision":
            print(f"🧠 Analyse par l'agent {i}/{total}...")

    df = await analyser_questions(questions, progress_callback=_progress)

    print("\n✅ Colonnes disponibles :", df.columns.tolist())
    print("\n📊 Scores d'incertitude calculés:")
    print(df[["response", "incertitude", "semantique", "correspondance_exacte", "cosinus", "combinee"]].head())

    for i, row in df.iterrows():
        print(f"🧠 Q{i + 1} → Incertitude: {row['incertitude']:.3f} → {row['decision_agent']}")

    # 💾 3. Sauvegarder dans un fichier CSV
    df.to_csv("resultats_math_uq_corrige.csv", index=False)
    print("\n📁 Résultats sauvegardés dans resultats_math_uq_corrige.csv")

    # 📊 4. Résumé des décisions
    print("\n📊 Résumé des décisions:")
    decisions = [result.split()[0] for result in df["decision_agent"] if result.split()]
    print(pd.Series(decisions).value_counts())


if __name__ == "__main__":
    asyncio.run(main())
