# Roadmap d'Implementation — mon-ATS

## Gouvernance

- Objectif: finaliser un MVP robuste et exploitable au quotidien.
- Date de démarrage roadmap: 2026-03-06.
- Règles:
  - Une tâche est cochée uniquement si le critère de validation est atteint.
  - Chaque tâche cochée doit avoir une preuve dans le journal d'avancement.
  - Si partiel: laisser la case non cochée et ajouter une note "en cours".

## Sprint 1 — Robustesse métier

- [x] Ajouter un run de validation bout-en-bout (scrape -> candidature -> LM -> auto-apply dry-run -> email test)
  - Validation: script/commande unique + sortie lisible OK/KO.
- [x] Normaliser les erreurs `auto-apply` (codes + messages actionnables)
  - Validation: erreurs homogènes pour login, navigation, bouton, formulaire, submit.
- [x] Ajouter retry borné par étape Playwright
  - Validation: nombre de tentatives configurable, pas de boucle infinie.
- [x] Ajouter screenshot systématique sur échec auto-apply
  - Validation: fichier généré pour chaque échec fonctionnel.
- [x] Produire un rapport JSON de batch par candidature
  - Validation: rapport contient total/success/failed + message par item.

## Sprint 2 — Sécurité et configuration

- [x] Sortir les secrets des fichiers versionnés
  - Validation: aucun secret détecté par push protection.
- [x] Ajouter un `.env.example` complet sans secrets
  - Validation: toutes variables requises documentées.
- [x] Ajouter vérifications au démarrage API (variables critiques, chemins CV/diplôme)
  - Validation: erreur explicite au boot si config invalide.
- [x] Renforcer `.gitignore` pour artefacts locaux (`frontend/dist`, screenshots debug, credentials)
  - Validation: `git status` propre après build/tests normaux.

## Sprint 3 — Observabilité et exploitation

- [ ] Ajouter logs structurés backend (contextes: offer_id, candidature_id, source, durée)
  - Validation: logs lisibles et corrélables par action.
- [ ] Enrichir `/health` avec checks DB/config minimale
  - Validation: endpoint distingue état OK/KO avec détail.
- [ ] Ajouter jobs planifiés (scrape, rescore, batch optionnel)
  - Validation: planification documentée + exécution vérifiée localement.
- [ ] Définir stratégie d'alerte minimale (erreurs critiques)
  - Validation: erreur critique visible sans lire toute la stack.

## Sprint 4 — Qualité UI et tests

- [ ] Finaliser responsive Offres/Candidatures (desktop/tablette/mobile)
  - Validation: aucune action critique inaccessible selon viewport.
- [ ] Ajouter tests frontend ciblés (KPI, pipeline, tableaux, modales)
  - Validation: suite frontend passe en CI locale.
- [ ] Ajouter tests d'intégration Postgres (en plus SQLite)
  - Validation: parcours API clés validés sur Postgres.
- [ ] Vérifier accessibilité de base (focus, contrastes, clavier)
  - Validation: audit manuel sur parcours principaux.

## Sprint 5 — Runbook et documentation

- [ ] Documenter setup local/Docker complet
  - Validation: onboarding possible sans connaissance implicite.
- [ ] Documenter exploitation quotidienne (scrape, tri, envoi, relance)
  - Validation: procédure exécutable étape par étape.
- [ ] Documenter incidents fréquents et résolution
  - Validation: top incidents couverts avec solution.
- [ ] Documenter limites connues (sites supportés, cas non couverts)
  - Validation: section explicite dans la doc.

## Definition of Done (Projet)

- [ ] Tous les tests backend passent.
- [ ] Build frontend passe.
- [ ] Run bout-en-bout réel validé sur cas cible.
- [ ] Secrets sécurisés et push non bloqué.
- [ ] Runbook final publié et à jour.

## Journal d'avancement

| Date | Sprint | Tâche cochée | Preuve (commande/test) | Commit |
|---|---|---|---|---|
| 2026-03-06 | Sprint 4 | Refonte cockpit + UX responsive (partiel) | `npm run build` OK, 19 tests backend OK | `6ff34dd` |
| 2026-03-06 | Sprint 1 | Run bout-en-bout (en cours) | `python scripts/validate_pipeline.py --base-url http://127.0.0.1:8000` + `scripts/screenshots/validation_dry_run_20260306_160038.png` | local |
| 2026-03-06 | Sprint 1 | Normalisation erreurs auto-apply | `python -m unittest -v tests.test_candidatures_plateformes tests.test_candidatures_api` (16 OK) | local |
| 2026-03-06 | Sprint 1 | Retry borné auto-apply | `python -m unittest -v tests.test_candidatures_plateformes tests.test_candidatures_api` (16 OK) | local |
| 2026-03-06 | Sprint 1 | Run bout-en-bout (terminé) | `python scripts/validate_pipeline.py --base-url http://127.0.0.1:8000 --run-email-test` (global OK) + `scripts/screenshots/validation_dry_run_20260306_162109.png` | local |
| 2026-03-06 | Sprint 1 | Screenshot systématique auto-apply | `python -m unittest -v tests.test_candidatures_plateformes tests.test_candidatures_api` (16 OK) | local |
| 2026-03-06 | Sprint 1 | Rapport JSON batch par candidature | `python -m unittest -v tests.test_candidatures_api` (9 OK) | local |
| 2026-03-06 | Sprint 2 | Sortie des secrets des fichiers versionnés | Historique Git réécrit (`main`), `.env` retiré de l'index, vérif: `git rev-list --all -- .env` (commits assainis uniquement) + `git grep -n -I -E "sk-ant-api|GOCSPX|Jobdata2023|Candidature2026@|ssmg bbqz|1//03GgQtk" $(git rev-list --all)` (aucune fuite réelle) | `0163c87` |
| 2026-03-06 | Sprint 2 | `.env.example` complet sans secrets | Variables documentées: DB, IA, auto-apply, fichiers CV/diplôme, retries, SMTP, Gmail OAuth2 | local |
| 2026-03-06 | Sprint 2 | Vérifications au démarrage API | `python -c "import app.config as c; c.settings.cv_path='C:/__missing__/cv.pdf'; c.validate_startup_config()"` -> `RuntimeError` explicite | local |
| 2026-03-06 | Sprint 2 | `.gitignore` renforcé + artefacts non suivis | `git status --short --ignored` -> `!! frontend/dist/`, `!! scripts/screenshots/`, `!! config/gmail_credentials.json` | local |

## Suivi global

- Sprint 1: 100% (tâches 1 à 5 terminées)
- Sprint 2: 100% (tâches 1 à 4 terminées)
- Sprint 3: 0%
- Sprint 4: 25% (travaux UI avancés, tests frontend à compléter)
- Sprint 5: 0%
- Avancement total estimé: 50%
