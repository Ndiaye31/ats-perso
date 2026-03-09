# Commandes utiles

## Docker

```bash
# Démarrer les services
docker compose up -d

# Arrêter les services
docker compose down

# Voir les logs du backend
docker logs -f ats-perso-api-1

# Redémarrer le backend (après modif code)
docker restart ats-perso-api-1
```

## Alembic (migrations BDD)

```bash
# Appliquer toutes les migrations
docker exec ats-perso-api-1 alembic upgrade head

# Voir la migration actuelle
docker exec ats-perso-api-1 alembic current

# Revenir une migration en arrière
docker exec ats-perso-api-1 alembic downgrade -1
```

## Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Lancer en dev
npm run dev

# Build production
npm run build

# Vérifier les types
npx tsc --noEmit
```

## Scraping

```bash
# Scraper toutes les sources
curl -X POST http://localhost:8000/offres/scrape

# Scraper une source spécifique
curl -X POST http://localhost:8000/offres/scrape/emploi-territorial.fr
curl -X POST http://localhost:8000/offres/scrape/emploi.fhf.fr
```

## Git

```bash
# Pousser sur ta branche
git add -A && git commit -m "message" && git push origin mactar

# Merger dans main
git checkout main && git merge mactar && git push origin main
```

## Base de données (accès direct)

```bash
# Ouvrir un shell psql
docker exec -it ats-perso-db-1 psql -U postgres -d ats

# Quelques requêtes utiles

# Nombre d'offres par source
SELECT s.name, COUNT(*) FROM offers o JOIN sources s ON o.source_id = s.id GROUP BY s.name;

# Candidatures par statut
SELECT statut, COUNT(*) FROM candidatures GROUP BY statut;

# Offres sans moyen de candidature (ne devrait plus y en avoir)
SELECT COUNT(*) FROM offers WHERE contact_email IS NULL AND candidature_url IS NULL;
```
