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
bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\activate
pip install -r requirements.txt

## 2) Run — CLI
bash
python main.py --query "wireless headphones"

## 3) Run — API

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
Swagger UI :
http://127.0.0.1:8000/docs

## 4) Example API usage
curl -X POST "http://127.0.0.1:8000/analyze" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"wireless headphones\"}"
## Notes / Limitations
Le scraping peut être bloqué selon les sites (robots, limitations). Le projet inclut un mock fallback pour garantir une démo stable.
Le sentiment est simulé/heuristique (basé sur ratings) pour privilégier l’orchestration et la robustesse.

## Next improvements
Vrai pipeline NLP sur reviews (aspect-based sentiment)
Cache (SQLite/Redis) + async scraping
Observabilité (logs structurés, traces)
CI (GitHub Actions) : lint + tests
## OutputsTest
pytest -q


## Outputs
HTML reports are generated in: reports/
Open the generated .html file in your browser.

##Théorie (Questions 4–7)
 Réponses Q4–Q7

# Build
docker build -t market-analysis-agent .

# Run
docker run --rm -p 8000:8000 -v "$(pwd)/reports:/app/reports" market-analysis-agent

