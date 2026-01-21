# Moov AI — Market Analysis Agent (E-commerce)

Agent Python pour analyser un marché e-commerce à partir d’une requête produit :
- collecte (scraping ou mock fallback),
- analyse (statistiques + tendances simulées),
- sentiment (basé sur ratings / règles),
- génération d’un rapport HTML (Chart.js),
- exposé en **CLI** et **API FastAPI**.

## Features
- **CLI** : exécuter une analyse en ligne de commande
- **REST API (FastAPI)** : endpoints pour lancer l’analyse
- **Robustesse** : fallback sur données mock si scraping indisponible
- **Rapport HTML** : graphiques + résumé déterministe
- **Tests** : tests unitaires sur les tools et l’orchestration

## Tech Stack
- Python 3.10+ (recommandé)
- FastAPI + Uvicorn
- Pytest
- Chart.js (dans le HTML report)

## Project Structure (high level)
- `main.py` : CLI
- `app.py` : API FastAPI
- `src/` : tools (WebScraper, SentimentAnalyzer, MarketAnalyzer, ReportGenerator)
- `tests/` : tests unitaires
- `reports/` (ou équivalent) : rapports HTML générés

## Setup (Local)
### 1) Create venv + install deps
```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\activate
pip install -r requirements.txt

## Run — CLI
```bash
python main.py --query "wireless headphones"

uvicorn app:app --reload

curl -X POST "http://127.0.0.1:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{"query":"wireless headphones"}'

## OutputsTest
pytest -q


## Outputs
HTML reports are generated in: reports/
Open the generated .html file in your browser.

##Théorie (Questions 4–7)
📄 Réponses Q4–Q7

### Les 3 choses à vérifier pour que ce soit “OK rendu”1) **Le PDF existe vraiment** dans ton repo : `docs/reponses_Q4-Q7.pdf` (sinon adapte le nom).  2) Ton endpoint est bien **`POST /analyze`** (sinon remplace dans le `curl`).  3) Le CLI accepte bien `--query` (sinon remplace par tes vrais arguments).Si tu veux, envoie-moi :- une capture ou le texte de la page `http://127.0.0.1:8000/docs` (liste des routes),- et le `python main.py --help`,et je te renvoie un README final **exact** (commandes et endpoints 100% corrects).
