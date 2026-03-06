# Jobs planifiés (Sprint 3)

## Variables

- `SCHEDULER_ENABLED`: active/désactive la boucle planifiée.
- `SCHEDULER_SCRAPE_INTERVAL_S`: intervalle job scrape.
- `SCHEDULER_RESCORE_INTERVAL_S`: intervalle job rescore.
- `SCHEDULER_BATCH_ENABLED`: active le job batch optionnel.
- `SCHEDULER_BATCH_INTERVAL_S`: intervalle job batch optionnel.
- `SCHEDULER_BATCH_LIMIT`: nombre max de candidatures batch.

## Jobs

- `scrape`: exécute `/offres/scrape` côté service.
- `rescore`: exécute `/offres/score` côté service.
- `optional_batch`: génère les LM en batch pour des candidatures `brouillon` en mode `plateforme` (si activé).

## Vérification locale

- Tests: `python -m unittest -v tests.test_scheduler`
- Exécution one-shot: `python scripts/run_scheduled_jobs_once.py`
