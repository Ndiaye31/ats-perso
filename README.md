# mon-ATS

ATS (Applicant Tracking System) personnel qui automatise l'ensemble du pipeline de candidature : scraping d'offres, scoring IA, génération de lettres de motivation, et envoi automatisé des candidatures.

## Architecture technique

| Couche | Stack |
|--------|-------|
| **Backend** | Python / FastAPI + SQLAlchemy + PostgreSQL (Alembic pour les migrations) |
| **Frontend** | TypeScript / React + Vite + TailwindCSS |
| **IA** | API Anthropic Claude (scoring d'offres + génération de lettres de motivation) |
| **Automatisation** | Playwright (auto-apply sur les portails) + Gmail API (envoi email OAuth2) |
| **Infra** | Docker Compose (Postgres 16 + API) |

## Modules fonctionnels

1. **Scrapers** (`app/scrapers/`) — Extraction d'offres depuis emploi-territorial.fr et emploi.fhf.fr, configurable via `config/scrapers.yml` (sélecteurs CSS, pagination, throttling)
2. **Scoring IA** (`app/scoring.py`, `app/ai/`) — Évaluation automatique de la pertinence des offres par rapport au profil candidat (`config/profil.yml`)
3. **Génération de LM** (`app/ai/generate_lm.py`, `app/automation/lm_generator.py`) — Lettres de motivation personnalisées via Claude, stockées dans `config/lettres/`
4. **Auto-apply** (`app/automation/`) — Candidature automatisée via Playwright (portails emploi-territorial, FHF) avec retry borné, screenshots sur échec, rapports JSON par batch
5. **Email** (`app/email_sender.py`) — Envoi de candidatures par email via Gmail OAuth2 (fallback quand le portail n'est pas supporté)
6. **Frontend cockpit** (`frontend/`) — Dashboard React avec KPIs, tableau des offres, pipeline kanban des candidatures, modales de détail et d'application
7. **Scheduler** (`app/scheduler.py`) — Jobs planifiés (scrape, rescore, batch candidatures)
8. **Observabilité** — Logs structurés JSON, health check enrichi (`/health`), alertes sur erreurs critiques

## Démarrage rapide

```bash
# Copier et remplir la configuration
cp .env.example .env

# Lancer l'infra
docker compose up -d

# Ou sans Docker :
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Configuration

- **`config/profil.yml`** — Profil candidat (compétences, expériences, postes cibles, préférences)
- **`config/scrapers.yml`** — Sources de scraping (URLs, sélecteurs CSS, pagination, throttling)
- **`.env`** — Variables d'environnement (DB, clés API, SMTP, chemins CV/diplôme)

Le profil candidat et les sources de scraping sont entièrement pilotés par des fichiers YAML, sans toucher au code.

## Validation

```bash
# Tests backend
python -m unittest discover tests

# Pipeline bout-en-bout
python scripts/validate_pipeline.py --base-url http://127.0.0.1:8000
```

## Avancement (Roadmap)

- **Sprints 1–3** : 100% (robustesse métier, sécurité/config, observabilité)
- **Sprint 4** : 25% (responsive UI, tests frontend/intégration)
- **Sprint 5** : 0% (documentation/runbook)
- **Total estimé : ~75%**

Voir `ROADMAP_IMPLEMENTATION.md` pour le détail.
