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

markdown## Lancer les tests```bashpytest -q2) Utilisation (CLI)Exemple (adapter les options selon votre main.py) :bashpython main.py --query "wireless headphones"Résultats attendus :
affichage des principaux KPI dans les logs
génération d’un rapport HTML dans reports/ (ou dossier configuré)
3) Utilisation (API FastAPI)Lancer l’APIbashuvicorn app:app --host 0.0.0.0 --port 8000 --reloadSwagger UI :
http://127.0.0.1:8000/docs
Exemple d’appel (à adapter au endpoint)bashcurl -X POST "http://127.0.0.1:8000/analyze" \  -H "Content-Type: application/json" \  -d "{\"query\":\"wireless headphones\"}"3-bis) Docker (optionnel mais recommandé).dockerignoredockerignore__pycache__/*.pyc.venv/.env.git/pytest_cache/mypy_cache/dist/build/*.egg-info/reports/DockerfiledockerfileFROM python:3.11-slimWORKDIR /appENV PYTHONDONTWRITEBYTECODE=1ENV PYTHONUNBUFFERED=1COPY requirements.txt .RUN pip install --no-cache-dir -r requirements.txtCOPY . .EXPOSE 8000CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]Build & runbashdocker build -t market-agent .docker run -p 8000:8000 market-agentQuestions théoriques (étapes 4 à 7)4) Architecture de données et stockageSchéma de données (conceptuel) a) Stocker les résultats d’analyse

Table analysis_request

id (UUID), user_id, query, created_at, status
agent_config_version, trace_id
actual_cost_usd (traçabilité coûts LLM)



Table analysis_result

request_id (FK), summary, kpis (JSON), insights (JSON)
report_url (lien vers artefact HTML/PDF)
quality_score (score qualité automatisé)


Principe : métadonnées en DB, artefacts lourds (rapport HTML, JSON complet) en object storage. b) Maintenir l’historique des requêtes
analysis_request garde l’historique complet (statut, timestamps, erreurs, coûts)
ajout d’une idempotency_key pour éviter les doublons en cas de retry client
 c) Cacher les données collectées
Cache des pages/produits normalisés :

clé : scrape:{source}:{canonical_query_hash}
TTL variable selon volatilité (prix < description)


Stockage du “raw” (HTML/JSON) en objet, avec hash pour déduplication
 d) Gérer les configurations d’agents
Table agent_config versionnée :

modèle, paramètres (temperature), prompt, outils activés, timeouts/retries
version + is_active pour déployer/rollback proprement


Systèmes recommandés et pourquoi
PostgreSQL : “source of truth” (requêtes, statuts, configs, coûts, pointers)
Redis : cache hot + éventuellement rate limiting + résultats courts TTL
Object Storage (S3/MinIO) : artefacts lourds (rapports, raw scrape, JSON)
Queue (Celery+Redis/RabbitMQ ou SQS) : exécution asynchrone et scalabilité
Cette combinaison est robuste, économique et standard en production.5) Monitoring et observabilitéTracing (traçage d’exécution)
Générer un trace_id à l’entrée (API) et le propager à toutes les étapes
Un span par étape : scrape, normalize, sentiment, analysis, llm_summary, report
Métriques de performance
Latence end-to-end (p50/p95/p99) + latence par étape
Taux d’erreur par étape (scraping, LLM timeout, parsing)
Débit (analyses/min), saturation workers (CPU/RAM)
Profondeur et âge de la file (queue depth / queue age)
Cache hit rate (scraping + LLM)
Tokens in/out + coût par requête (pilotage financier)
Alerting
error_rate au-dessus d’un seuil sur une fenêtre glissante
p95 latency > seuil
queue_age > seuil (backlog)
dérive de coût (ex : coût/jour) ou explosion tokens
baisse brutale du cache hit rate (régression)
Mesure de la qualité des outputs
Validations déterministes : schéma JSON, sections obligatoires, garde-fous (prix non négatifs)
Scores qualité offline : LLM-as-judge sur échantillon + suivi dans le temps
Feedback utilisateur (thumbs up/down + catégorie d’erreur)
Métriques clés : success_rate, p95_latency, queue_age, cache_hit_rate, tokens/request, cost/request, judge_score_avg, schema_pass_rate.6) Scaling et optimisationGestion des pics (100+ analyses simultanées)
API synchrone uniquement pour “submit job” + “get status”
traitement asynchrone via file + pool de workers
autoscaling des workers sur queue_depth et queue_age
idempotency pour éviter duplication
Optimisation coûts LLM
Cache des réponses LLM (hash prompt + inputs + version config)
“model routing” : petit modèle pour extraction/formatage, modèle plus fort pour synthèse
prompt compact : envoyer KPI agrégés plutôt que données brutes
budgets par requête et “graceful degradation” (fallback déterministe)
Cache intelligent
2 niveaux : cache scraping + cache résultat final (si mêmes paramètres/config)
invalidation : TTL + changement version config + exigences de fraîcheur
Parallélisation
scraping multi-sources en parallèle
batch sentiment (par lots)
DAG simple : consolidation → synthèse → génération rapport
7) Amélioration continue et A/B testingÉvaluation automatique (LLM as Judge)
Dataset d’évaluation représentatif (catégories variées, cas “données pauvres”)
Critères : exactitude vs sources, utilité business, structure, non-hallucination
Exécution offline (coût maîtrisé), stockage des scores par version d’agent
Comparaison de stratégies de prompt
Versionner agent_config
A/B testing via feature flag (ex : 90/10 puis 50/50)
Mesures : qualité (judge + feedback), coût, latence, taux d’erreur
Feedback loop utilisateur
endpoint / UI simple : note + commentaire + tags
exploitation : amélioration prompts, règles, sources, et enrichissement dataset d’éval
Évolution des capacités
Stabilisation (SLO, observabilité, cache) → grounding/citations → quality gates en CI → guardrails + politiques de coût
Dans un contexte finance/entreprise : auditabilité (qui a lancé quoi), traçabilité coûts, rétention et masquage PII si applicable
