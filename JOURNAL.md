# Journal de développement — mon-ATS

Suivi chronologique de tout ce qui a été construit, pourquoi, et comment.

---

## Contexte du projet

Un ATS (Applicant Tracking System) personnel pour suivre des candidatures à des offres d'emploi publiques.
L'objectif final : scraper des sites comme emploi-territorial.fr, générer des lettres de motivation via l'IA (Claude API), et envoyer les candidatures par mail.

**Stack choisie :** Python 3.11+ / FastAPI / PostgreSQL / SQLAlchemy 2.0 / Alembic

---

## Étape 1 — Architecture de base

### Ce qui a été créé

```
mon-ats/
├── app/
│   ├── main.py          # Point d'entrée FastAPI
│   ├── config.py        # Chargement des variables d'environnement
│   ├── database.py      # Connexion à la base de données
│   ├── models/          # Tables de la base de données
│   ├── schemas/         # Formats de réponse de l'API
│   └── routers/         # Endpoints HTTP
├── alembic/             # Migrations de base de données
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

### Explication fichier par fichier

**`app/config.py`**
Charge la variable `DATABASE_URL` depuis le fichier `.env` grâce à `pydantic-settings`.
Cela évite d'écrire les identifiants de connexion directement dans le code.

**`app/database.py`**
Crée le moteur SQLAlchemy, la session de base de données, et la classe `Base` dont héritent tous les modèles.
La fonction `get_db()` est un générateur utilisé par FastAPI pour ouvrir/fermer proprement la session à chaque requête.

**`app/models/offer.py`** — Table `offers`
Représente une offre d'emploi. Colonnes :
- `id` : identifiant unique (UUID généré en Python)
- `title`, `company`, `location`, `url` : informations de base
- `description` : texte complet de l'offre
- `status` : état de la candidature (`new`, `applied`, `interview`, `rejected`)
- `applied_at` : date à laquelle on a postulé
- `source_id` : référence vers la source (LinkedIn, emploi-territorial…)
- `created_at`, `updated_at` : horodatages automatiques

**`app/models/source.py`** — Table `sources`
Représente le site d'où vient l'offre (LinkedIn, Indeed, emploi-territorial.fr…).
Chaque offre est reliée à une source via `source_id`.
Cela permet de savoir sur quel site on a trouvé chaque offre et de faire des statistiques par source.

**`app/routers/health.py`** — `GET /health`
Endpoint minimal qui retourne `{"status": "ok"}`.
Utile pour vérifier que le serveur tourne (monitoring, Docker healthcheck).

**`app/routers/offers.py`** — `GET /offers`
Retourne la liste de toutes les offres en base, triées de la plus récente à la plus ancienne.

**`alembic/versions/0001_initial.py`**
Première migration : crée les tables `sources` et `offers` dans la base de données.
Alembic garde un historique des migrations pour pouvoir monter (`upgrade`) ou revenir en arrière (`downgrade`).

### Choix techniques importants

- **SQLAlchemy 2.0** : syntaxe moderne avec `Mapped` et `mapped_column` (plus lisible, mieux typée)
- **UUID côté Python** : les identifiants sont générés par `uuid.uuid4()` avant insertion, pas par PostgreSQL. Cela permet de connaître l'ID avant même d'écrire en base.
- **Alembic** : `sqlalchemy.url` n'est jamais écrit dans `alembic.ini`. Il est injecté au démarrage depuis `.env` via `app/config.py`. Aucun mot de passe dans les fichiers versionnés.

---

## Étape 2 — Déduplication des offres

### Problème
Sans mécanisme de déduplication, scraper deux fois le même site insère les mêmes offres en double.

### Solution : `content_hash`

**`app/utils.py`** — fonction `compute_content_hash(title, company, url)`
Calcule un hash SHA-256 à partir du titre, de l'entreprise et de l'URL de l'offre (normalisés en minuscules).
Deux offres identiques produiront toujours le même hash.

```python
raw = f"{title.lower().strip()}|{company.lower().strip()}|{url or ''}"
return hashlib.sha256(raw.encode()).hexdigest()
```

**`app/models/offer.py`** — colonne `content_hash` ajoutée
Colonne VARCHAR avec contrainte UNIQUE et un index. Si on essaie d'insérer une offre avec un hash déjà présent, on la saute au lieu de planter.

**`alembic/versions/0002_add_content_hash.py`**
Migration qui ajoute la colonne `content_hash` et son index unique sur la table `offers` existante.

---

## Étape 3 — Données de test

**`scripts/seed.py`**
Script autonome (hors FastAPI) qui insère 5 offres fictives en base pour tester l'API sans avoir à scraper un vrai site.

Ce que fait le script :
1. Crée (ou réutilise) une source "LinkedIn"
2. Pour chaque offre fictive, calcule son `content_hash`
3. Si le hash est déjà en base → affiche "doublon ignoré" et passe à la suivante
4. Sinon → insère l'offre

```bash
python scripts/seed.py
# Résultat :
#   + Développeur Backend Python @ Doctolib
#   + Ingénieur FastAPI / PostgreSQL @ Leboncoin
#   ...
# 5 offres insérées, 0 doublons ignorés.

python scripts/seed.py  # 2e fois
# 0 offres insérées, 5 doublons ignorés.
```

---

## Étape 4 — Modèle Candidature

### Pourquoi une table séparée ?

Une **offre** est une annonce trouvée sur un site.
Une **candidature** est l'action d'y répondre : rédiger une lettre, envoyer un mail, suivre les retours.

Une offre peut exister sans candidature (on l'a vue mais pas encore postulé).
Une candidature est toujours liée à une offre.

**`app/models/candidature.py`** — Table `candidatures`
Colonnes :
- `id` : UUID
- `offer_id` : FK vers `offers.id` (CASCADE : si l'offre est supprimée, la candidature aussi)
- `statut` : état (`brouillon`, `envoyée`, `relancée`, `refusée`, `acceptée`)
- `lm_texte` : texte de la lettre de motivation (généré par l'IA plus tard)
- `date_envoi` : date d'envoi effective
- `email_contact` : adresse mail du recruteur
- `created_at`, `updated_at` : horodatages automatiques

**`alembic/versions/0003_add_candidature.py`**
Migration qui crée la table `candidatures`.

---

## Étape 5 — Scraper emploi-territorial.fr

**`app/scrapers/emploi_territorial.py`**
Scraper basé sur `requests` + `BeautifulSoup`.

Fonctionnement :
1. Appelle `https://www.emploi-territorial.fr/offres-emploi` page par page (max 2 pages par défaut)
2. Pour chaque page, parse le HTML et cherche les cartes d'offres
3. Extrait titre, employeur, localisation, URL
4. Retourne une liste de `RawOffer` (dataclass simple)

Le scraper est tolérant aux erreurs : si une page échoue (timeout, structure HTML changée), il log un avertissement et continue.

**`app/routers/scrape.py`** — `POST /offres/scrape`
Endpoint qui orchestre le scraping et l'insertion :
1. Crée ou récupère la source "emploi-territorial.fr"
2. Appelle `fetch_offers()`
3. Pour chaque offre brute, calcule le hash et vérifie si elle existe déjà
4. Insère uniquement les nouvelles offres
5. Retourne un résumé `{"inserted": X, "skipped": Y, "total_scraped": Z}`

```bash
curl -X POST http://127.0.0.1:8000/offres/scrape
# {"inserted": 12, "skipped": 0, "total_scraped": 12}

# Deuxième appel :
# {"inserted": 0, "skipped": 12, "total_scraped": 12}
```

---

## Étape 6 — Profil utilisateur

**`config/profil.yml`**
Fichier YAML qui centralise toutes les informations personnelles :
- Identité (nom, email, téléphone)
- Compétences
- Expériences professionnelles
- Formation
- Chemin vers le CV de base
- Préférences de recherche (types de contrat, localisation, salaire minimum)

Ce fichier servira de contexte pour la génération de lettres de motivation par l'IA (étape future).

**`app/profil.py`**
Charge le fichier YAML une seule fois au démarrage et expose un dict `profil` importable partout dans l'application.

```python
from app.profil import profil
print(profil["nom"])          # "Jean Dupont"
print(profil["competences"])  # ["gestion de projet", "Excel", ...]
```

---

## État actuel de la base de données

### Table `sources`
| Colonne | Type | Rôle |
|---|---|---|
| `id` | UUID | Clé primaire |
| `name` | VARCHAR UNIQUE | Nom du site (ex: "LinkedIn") |
| `url` | VARCHAR | URL du site |
| `created_at` | TIMESTAMP | Date de création |

### Table `offers`
| Colonne | Type | Rôle |
|---|---|---|
| `id` | UUID | Clé primaire |
| `title` | VARCHAR | Titre du poste |
| `company` | VARCHAR | Nom de l'employeur |
| `location` | VARCHAR | Localisation |
| `url` | VARCHAR | Lien vers l'offre |
| `description` | TEXT | Texte complet |
| `status` | VARCHAR | État (`new`, `applied`…) |
| `applied_at` | DATE | Date de candidature |
| `content_hash` | VARCHAR UNIQUE | Hash pour déduplication |
| `source_id` | UUID FK | Référence vers `sources` |
| `created_at` | TIMESTAMP | Date de création |
| `updated_at` | TIMESTAMP | Dernière modification |

### Table `candidatures`
| Colonne | Type | Rôle |
|---|---|---|
| `id` | UUID | Clé primaire |
| `offer_id` | UUID FK | Référence vers `offers` |
| `statut` | VARCHAR | État de la candidature |
| `lm_texte` | TEXT | Lettre de motivation |
| `date_envoi` | DATE | Date d'envoi |
| `email_contact` | VARCHAR | Email recruteur |
| `created_at` | TIMESTAMP | Date de création |
| `updated_at` | TIMESTAMP | Dernière modification |

---

## Endpoints disponibles

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/health` | Vérifie que le serveur tourne |
| `GET` | `/offers` | Liste toutes les offres |
| `POST` | `/offres/scrape` | Lance le scraping emploi-territorial.fr |

Documentation interactive : **http://127.0.0.1:8000/docs**

---

## Commandes utiles

```bash
# Démarrer le serveur
uvicorn app.main:app --reload

# Appliquer les migrations
python -m alembic upgrade head

# Insérer les données de test
python scripts/seed.py

# Lancer le scraper
curl -X POST http://127.0.0.1:8000/offres/scrape
```

---

## Prochaines étapes prévues

- [ ] Vrais scrapers additionnels (Welcome to the Jungle, Indeed…)
- [ ] Génération de lettre de motivation via Claude API (`app/ai/`)
- [ ] Envoi de candidatures par mail (`app/email/`)
- [ ] Frontend React (dashboard, suivi candidatures)

---

## Session du 03/03/2026 — Mise en prod Docker + Scrapers + Interface

### 1. Clonage du dépôt et migration vers Docker

Le projet existait avec une base de données locale (PostgreSQL sur `localhost:5433`).
Migration vers Docker : modification du `.env` pour pointer vers le service Docker.

```
# Avant
DATABASE_URL=postgresql+psycopg://ats_user:Ndiaye123@localhost:5433/ats_db

# Après
DATABASE_URL=postgresql+psycopg://ats_user:ats_pass@db:5432/ats_db
```

`db` est le nom du service dans `docker-compose.yml`. À l'intérieur du réseau Docker, les conteneurs se joignent par nom de service, pas par `localhost`.

Commandes utilisées :
```bash
docker-compose up --build
docker-compose exec api python -m alembic upgrade head
```

---

### 2. Correction du scraper générique

**Problème :** Le fichier `config/scrapers.yml` contenait des sélecteurs CSS génériques (suppositions) qui ne correspondaient pas au vrai HTML des sites. Résultat : 0 offres scrapées.

**Analyse des sites par inspection HTTP :**

| Site | Structure HTML |
|---|---|
| emploi-territorial.fr | Table HTML (`<tr>`), pagination via `?search-fam-metier=A7` |
| emploi.fhf.fr | `article.card.card-offer`, pagination 0-indexée (`?page=0`) |
| place-emploi-public.fr | Erreur TLS — inaccessible |
| fonction-publique.gouv.fr | Redirige vers choisirleservicepublic.gouv.fr (JS-rendu) |

**Sélecteurs corrigés dans `config/scrapers.yml` :**

*emploi-territorial.fr* — filière Informatique & SI uniquement (`search-fam-metier=A7`) :
- Carte : `tr`
- Titre : `a[href^='/offre/o']`
- Employeur : `a[href*='search-col=']`
- Localisation : `td:nth-child(3)`

*emploi.fhf.fr* — postes administratifs uniquement (`type=ADM`) :
- Carte : `article.card.card-offer`
- Titre : `h3.card-title`
- Employeur : `.field--name-field-establishment`
- Lien : `a.btn.btn-link`
- Pagination : commence à 0 (`page_start: 0`)

**Ajout dans `ScraperConfig`** de deux nouveaux champs :
- `page_param` : nom du paramètre de pagination (défaut `"page"`)
- `page_start` : numéro de la première page (défaut `1`, FHF commence à `0`)

---

### 3. Correction de l'insertion en base — `ON CONFLICT DO NOTHING`

**Problème :** L'insertion en masse (bulk insert SQLAlchemy) plantait avec `UniqueViolation` dès qu'un doublon existait, annulant toute la transaction.

**Solution :** Remplacement du check Python par un `INSERT ... ON CONFLICT DO NOTHING` PostgreSQL natif dans `app/routers/scrape.py` :

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(Offer.__table__).values(...).on_conflict_do_nothing(
    index_elements=["content_hash"]
)
result = db.execute(stmt)
inserted += 1 if result.rowcount else 0
```

Avantages : atomique, gère les race conditions, pas de N+1 queries.

---

### 4. Amélioration du scoring

**Problème :** Le scoring donnait 40 points à des offres comme "Agent polyvalent des écoles" parce que le matching cherchait des sous-chaînes. Exemple : `"de" in "agent polyvalent des écoles"` → `True`, donc le poste "Analyste de données" matchait.

**Correction dans `app/scoring.py` :**
- Ajout de `_sig_words()` : extrait les mots significatifs (≥ 4 caractères, hors mots courants comme "de", "du", "les"…)
- Ajout de `_word_in_text()` : matching par mot entier via regex `\b` (word boundary)
- Résultat : seules les offres avec un vrai mot-clé métier dans le titre obtiennent un score élevé

```python
def _sig_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zéèêàùîôâûç]+", text.lower())
            if len(w) >= 4 and w not in _STOP]

def _word_in_text(word: str, text: str) -> bool:
    return bool(re.search(r"\b" + re.escape(word) + r"\b", text))
```

---

### 5. Interface React — nouvelles colonnes et modal Fiche

**Colonne "Source"** : affiche le nom du site d'où vient l'offre (`emploi-territorial.fr`, `emploi.fhf.fr`).
- Ajout de `source_name` dans `OfferRead` (Pydantic) via `model_validator(mode="wrap")`
- `joinedload(Offer.source)` dans le router pour éviter les requêtes N+1
- Ajout de `source_name` dans `types.ts` et dans la colonne du tableau

**Colonne "Fiche"** : bouton pour consulter la description ou accéder à l'offre.
- Icône bleue : description disponible → ouvre la modal
- Icône grise : pas de description mais URL disponible → ouvre la modal avec lien
- Nouveau composant `FicheModal.tsx` : affiche titre, description scrollable, email de contact, bouton "Voir l'offre"

**Champ `description`** ajouté dans `OfferRead` et `types.ts`.

---

### 6. Fetch des pages de détail (`fetch_detail: true`)

Activé pour récupérer la description complète de chaque offre.
- emploi-territorial.fr : sélecteur `#MainContent`
- emploi.fhf.fr : sélecteur `main`

**Problème de performance :** Sans optimisation, chaque scraping visitait toutes les pages de détail, même pour des offres déjà en base.

**Solution — skip des offres connues :**

Dans `app/routers/scrape.py` : chargement des hashes existants avant scraping.
```python
def _load_known_hashes(db: Session) -> set[str]:
    rows = db.query(Offer.content_hash).filter(Offer.content_hash.isnot(None)).all()
    return {h for (h,) in rows}
```

Dans `app/scrapers/base.py` : le hash est calculé dès la liste (avant de visiter le détail). Si le hash est dans `known_hashes`, la page de détail est ignorée.

```python
h = compute_content_hash(title, company, location)
if h not in known_hashes:
    detail = self._fetch_detail(url)  # visite seulement si nouvelle offre
```

Résultat : le 1er scraping est lent (visite chaque détail), les suivants sont rapides (seules les nouvelles offres déclenchent des requêtes HTTP).

---

### État des endpoints après cette session

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/health` | Vérifie que le serveur tourne |
| `GET` | `/offers` | Liste les offres (filtre `min_score`) |
| `POST` | `/offres/scrape` | Scrape tous les sites configurés |
| `POST` | `/offres/scrape/{source}` | Scrape un site spécifique |
| `POST` | `/offres/score` | Recalcule le score de toutes les offres |
| `GET` | `/candidatures` | Liste les candidatures |
| `POST` | `/candidatures` | Crée une candidature |
| `PATCH` | `/candidatures/{id}` | Met à jour une candidature |

### Prochaines étapes identifiées (session 03/03/2026)

- [ ] Intégration API France Travail (OAuth2) pour place-emploi-public.fr et choisirleservicepublic.gouv.fr
- [ ] Génération de lettre de motivation via Claude API
- [ ] Envoi automatique des candidatures par email

---

## Session du 04/03/2026 — Génération LM, Candidatures, Interface & Scraping

### 1. Génération de lettre de motivation via Claude API

**Fichiers :** `app/ai/generate_lm.py`, `app/routers/candidatures.py`

Le backend `generate_lm()` existait déjà. Problème initial : crédits Anthropic épuisés sur l'ancienne clé → résolu en mettant à jour `ANTHROPIC_API_KEY` dans `.env` et en redémarrant le conteneur avec `docker-compose up -d --force-recreate api` (le simple `restart` ne recharge pas le `.env`).

Modèle utilisé : `claude-haiku-4-5-20251001`. Le prompt injecte le profil complet (résumé, compétences, expériences, formation) et génère une lettre de 300-400 mots adaptée au poste et à l'employeur.

**Endpoint :** `POST /candidatures/{id}/generate-lm` → sauvegarde la LM en base et la retourne.

---

### 2. Correction de la duplication des candidatures

**Problème :** Chaque ouverture de la modal "Postuler" + action (générer LM, annuler…) créait une nouvelle candidature, résultant en plusieurs entrées pour la même offre.

**Corrections :**

*Backend — `POST /candidatures` idempotent :*
```python
existing = db.execute(
    select(Candidature)
    .where(Candidature.offer_id == body.offer_id)
    .where(Candidature.statut != "annulée")
).scalar_one_or_none()
if existing:
    return existing  # retourne l'existante au lieu de créer un doublon
```

*Nouveau endpoint :* `GET /candidatures/offer/{offer_id}` — retourne la candidature active pour une offre donnée.

*Frontend — `ApplyModal.tsx` :* `useEffect` au montage qui charge la candidature existante et pré-remplit l'email et la LM.

---

### 3. Suppression de candidatures

**Backend :** `DELETE /candidatures/{id}` (204 No Content).

**Frontend :** Bouton "Supprimer" avec confirmation dans `CandidaturesTable.tsx`, en plus du bouton "Annuler" existant.

---

### 4. Prévisualisation email dans la modal

**Composant `ApplyModal.tsx`** — ajout de deux onglets :
- **Rédaction** : éditeur textarea + bouton "Générer avec Claude"
- **Prévisualisation** : affiche l'email complet tel qu'il sera envoyé
  - `À :` adresse recruteur
  - `Objet :` `Candidature — {titre du poste}`
  - Corps : LM formatée

---

### 5. Indicateur de candidature sur les offres

Dans `OffersTable.tsx` : chargement des candidatures au montage, badge coloré sous le bouton "Postuler" :
- 🟡 **Brouillon** — candidature en cours non envoyée
- 🟢 **Envoyée** — candidature déjà envoyée

---

### 6. Détection du mode de candidature (email / plateforme / portail tiers)

**Nouveau champ `candidature_url`** dans le modèle `Offer` (migration `0008`).

**Scraper `_fetch_detail` mis à jour :**
- Parcourt les blocs `.offre-item` de la section "Contact et modalités de candidature" sur emploi-territorial.fr
- Extrait le "Lien de candidature" (URL vers portail tiers) et l'email (mailto ou texte brut via regex)
- Retry automatique × 3 avec backoff (3s, 6s, 9s) en cas d'erreur réseau

**Délai augmenté :** 2.5s entre requêtes pour éviter le blocage IP par emploi-territorial.fr.

**Logique de détection `_detect_mode` (backend) :**
1. `contact_email` → `"email"`
2. `candidature_url` (domaine externe) → `"portail_tiers"`
3. `url` → `"plateforme"`
4. sinon → `"inconnu"`

**Frontend `ApplyModal.tsx` :**
- Badge orange 🔗 pour portail tiers avec nom de domaine affiché
- Bouton "Aller sur le portail tiers" orange

---

### 7. Filtres dans le tableau des offres

Ajout d'un filtre **Mode** dans `OffersTable.tsx` :
- ✉ Email / 🌐 Plateforme / 🔗 Portail tiers / — Inconnu
- Combinable avec le filtre Source existant

---

### Résultats scraping après corrections (04/03/2026)

105 offres insérées (60 emploi-territorial.fr + 45 emploi.fhf.fr) :
- **72/80** avec description complète
- **13** avec email de contact direct
- **19** avec lien portail tiers (Flatchr, Beetween, Seine-Maritime, etc.)

---

### État des endpoints (04/03/2026)

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/health` | Vérifie que le serveur tourne |
| `GET` | `/offers` | Liste les offres (filtres score, statut, lieu, source) |
| `POST` | `/offres/scrape` | Scrape tous les sites configurés |
| `POST` | `/offres/scrape/{source}` | Scrape un site spécifique |
| `POST` | `/offres/score` | Recalcule le score de toutes les offres |
| `GET` | `/candidatures` | Liste les candidatures |
| `GET` | `/candidatures/offer/{offer_id}` | Candidature active pour une offre |
| `POST` | `/candidatures` | Crée une candidature (idempotent) |
| `PATCH` | `/candidatures/{id}` | Met à jour une candidature |
| `DELETE` | `/candidatures/{id}` | Supprime une candidature |
| `POST` | `/candidatures/{id}/generate-lm` | Génère la LM via Claude API |

---

### Prochaines étapes identifiées (04/03/2026)

- [ ] Envoi automatique des candidatures par email (SMTP — Gmail ou autre)
- [ ] Intégration API France Travail (OAuth2) pour place-emploi-public.fr / choisirleservicepublic.gouv.fr
- [ ] Scrapers additionnels (Welcome to the Jungle, Indeed…)
- [ ] Améliorer le scoring en exploitant la description complète (pas seulement le titre)
- [ ] Tableau de bord / statistiques (offres par source, par mode, par score)

---

## Session du 05/03/2026 — Automatisation Playwright (emploi-territorial.fr & emploi.fhf.fr)

### Objectif

Automatiser l'envoi de candidatures directement depuis l'ATS via un navigateur headless (Playwright), sans interaction manuelle.

---

### 1. Architecture mise en place

```
app/
  automation/
    __init__.py
    base.py                  # Classe abstraite BaseApplicator
    emploi_territorial.py    # Applicator emploi-territorial.fr
    emploi_fhf.py            # Applicator emploi.fhf.fr
    lm_generator.py          # Génération LM Word (.docx) → PDF via LibreOffice
scripts/
  explore_form.py            # Script diagnostic standalone
  screenshots/               # Tous les screenshots Playwright
```

---

### 2. Dépendances ajoutées

**`requirements.txt`**
```
playwright>=1.48.0
python-docx>=1.1.0
```

**`Dockerfile`**
```dockerfile
RUN playwright install chromium --with-deps
RUN apt-get install -y --no-install-recommends libreoffice-writer
```

**`docker-compose.yml`** — volume pour le CV :
```yaml
volumes:
  - C:/Users/macta/Documents:/documents:ro
```

---

### 3. Configuration (`app/config.py` + `.env`)

Nouveaux champs :
```python
emploi_territorial_login: str = ""
emploi_territorial_password: str = ""
emploi_fhf_login: str = ""
emploi_fhf_password: str = ""
cv_path: str = ""       # /documents/CV A.M. NDIAYE.pdf
diplome_path: str = ""  # /app/config/diplomes_amadou_mactar.pdf
```

Le dossier `config/` est monté via `.:/app` — les fichiers PDF (CV, diplôme) sont donc accessibles directement dans le container à `/app/config/`.

---

### 4. Génération de la lettre de motivation en PDF (`app/automation/lm_generator.py`)

Pipeline complet :
1. `generate_lm_docx()` — crée un `.docx` formaté (python-docx) :
   - En-tête expéditeur (nom, email, téléphone)
   - Date alignée à droite
   - Bloc destinataire + objet
   - Corps de la lettre (paragraphes séparés, sans formule d'appel dupliquée)
   - Formule de politesse + signature
2. `convert_docx_to_pdf()` — convertit via `libreoffice --headless --convert-to pdf`
3. `generate_lm_pdf()` — orchestre les deux étapes

---

### 5. Applicator emploi-territorial.fr (`app/automation/emploi_territorial.py`)

| Étape | Sélecteur / Méthode |
|---|---|
| Login URL | `/demandeur/login` |
| Champ login | `input[name='identCand']` |
| Champ mot de passe | `input[name='password']` |
| Bouton connexion | `button:has-text('me connecter')` |
| Vérification | URL ne contient plus `/login` |
| Bouton candidature | `a.btn-candidature-top` ou `a:has-text('Déposer ma candidature')` |
| Formulaire fichier[0] | CV (`/documents/CV A.M. NDIAYE.pdf`) |
| Formulaire fichier[1] | LM générée en PDF |
| Formulaire fichier[2] | Diplôme (`/app/config/diplomes_amadou_mactar.pdf`) |
| Soumission | `button:has-text('Postuler à cet')` |

---

### 6. Applicator emploi.fhf.fr (`app/automation/emploi_fhf.py`)

FHF utilise un formulaire de login **masqué par défaut**. Il faut cliquer sur "Connexion" dans la navbar pour le révéler, sinon le champ `input[name='name']` ciblé est la barre de recherche.

| Étape | Sélecteur / Méthode |
|---|---|
| Login URL | `/login` |
| Révéler le formulaire | `a:has-text('Connexion')` |
| Champ login | `#edit-name--2` (ID spécifique, évite la barre de recherche) |
| Champ mot de passe | `#edit-pass` |
| Bouton connexion | `#edit-submit--2` |
| Bouton candidature | `a:has-text('Je candidate!')` (AJAX → ouvre une modal) |
| Soumission | `button:has-text('Je confirme')` dans la modal |
| Upload fichiers | Aucun (FHF récupère le CV du profil) |

---

### 7. Endpoint `/auto-apply` (`app/routers/candidatures.py`)

```
POST /candidatures/{id}/auto-apply?dry_run=false
```

Comportement :
- `dry_run=true` → screenshot du formulaire sans soumettre (diagnostic)
- `dry_run=false` → soumission réelle, statut → `"envoyée"`, `date_envoi` → aujourd'hui
- Bloque si `offer.candidature_url` est renseigné (portail tiers = pas de formulaire sur le site)
- Détecte le site automatiquement depuis `offer.url`

**Nommage des screenshots** : `{société}_{YYYYMMDD}_{type}.png`
- `_dry_run.png` — dry-run réussi
- `_bouton_introuvable.png` — diagnostic bouton non trouvé
- `_erreur_formulaire.png` — diagnostic erreur remplissage

---

### 8. Frontend — boutons "Test" et "Postuler automatiquement"

**`frontend/src/api.ts`**
```typescript
export function autoApply(candidatureId: string, dryRun = false)
```

**`frontend/src/components/ApplyModal.tsx`**
- Bouton **"Test"** (dry-run) : screenshot sans soumettre, résultat en toast
- Bouton **"Postuler automatiquement"** : candidature réelle
- Visibles **uniquement** si `offer.url` contient `emploi-territorial.fr` ou `fhf.fr` **ET** sans `candidature_url` (pas portail tiers)

---

### 9. Problèmes rencontrés et solutions

| Problème | Cause | Solution |
|---|---|---|
| Login 404 sur emploi-territorial | URL `/login` invalide | URL correcte : `/demandeur/login` |
| Sélecteur login introuvable | Champ supposé `input[name='email']` inexistant | Vrai champ : `input[name='identCand']` (découvert via Playwright live dans Docker) |
| Login FHF impossible | Formulaire caché derrière un bouton nav | Cliquer `a:has-text('Connexion')` avant de remplir |
| Conflit champ login FHF | `input[name='name']` = barre de recherche (1er élément) | Cibler `#edit-name--2` (ID du champ login) |
| CV non trouvé | Nom de fichier avec espaces mal configuré dans `.env` | `CV_PATH=/documents/CV A.M. NDIAYE.pdf` |
| Bouton non trouvé (portail tiers) | L'offre redirige vers agglo-larochelle.fr, pas de formulaire local | Bloquer si `offer.candidature_url` est renseigné + message explicite |
| Filtre mode trop strict | FHF détecté comme `portail_tiers` ou `email` → bloqué | Supprimer le filtre strict sur `mode_candidature`, garder uniquement la détection site |
| Diplôme absent | Champ obligatoire dans le formulaire emploi-territorial | Ajout `diplome_path` dans config, upload dans `fill_form` au 3e champ fichier |

---

### 10. Validation dry-run

- **emploi-territorial.fr** : dry-run réussi (`success: true`), screenshot du formulaire avec champs CV + LM + diplôme visibles
- **emploi.fhf.fr** : dry-run réussi (`success: true`), modal de confirmation "Je candidate!" visible

---

### État des endpoints (05/03/2026)

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/candidatures/{id}/auto-apply?dry_run=true` | Dry-run : screenshot sans soumettre |
| `POST` | `/candidatures/{id}/auto-apply` | Candidature automatique réelle |
| `POST` | `/candidatures/{id}/generate-lm` | Génère la LM via Claude API |

---

### Prochaines étapes identifiées (05/03/2026)

- [ ] Tester en production sur une offre emploi-territorial en mode `plateforme` active (sans `candidature_url`)
- [ ] Vérifier la checkbox RGPD (si elle bloque la soumission)
- [ ] Autres sites à automatiser si besoin
- [ ] Pipeline complet : scrape → score → generate-lm → auto-apply

---

## Session du 05/03/2026 — Optimisations perf, fiabilité candidatures et batch auto-apply (22:14:22)

### 1. Performance backend/frontend

- Ajout d'endpoints allégés/paginés:
  - `GET /offers/table` (filtres + pagination)
  - `GET /offers/{id}` (détail offre)
  - `GET /candidatures/status-map` (statuts minimalistes)
- Ajout d'index DB via migration `0009_add_perf_indexes.py` pour accélérer tri/filtrage.
- Scraping optimisé:
  - `requests.Session` réutilisée
  - insertion SQL batch (`ON CONFLICT DO NOTHING`)
  - mesures de timing (`fetch_seconds`, `insert_seconds`, `total_seconds`)
- Frontend optimisé:
  - table offres en pagination serveur (100/page)
  - chargement fiche à la demande
  - annulation des requêtes en vol (`AbortController`) + gestion erreurs.

### 2. Qualité du matching offres/profil

- Durcissement scoring:
  - blacklist stricte des métiers hors cible dans `profil.yml`
  - ratio minimal de correspondance titre (`title_match_ratio_min: 0.6`)
  - détails de scoring enrichis (`rejected_by_blacklist`, `blacklist_hits`, `title_match_ratio`).

### 3. Génération LM

- Prompt LM remplacé par une version professionnelle multi-secteur, plus stricte sur:
  - structure (3 paragraphes),
  - style et ponctuation,
  - absence d'invention,
  - formule finale:
    - `Je reste disponible pour toute information complémentaire.`
    - `Veuillez agréer, Madame, Monsieur, l'expression de mes sincères salutations.`

### 4. Candidatures auto et batch simultané

- Nouveaux endpoints batch:
  - `POST /candidatures/bulk-generate-lm`
  - `POST /candidatures/bulk-auto-apply`
  - `POST /candidatures/bulk-generate-lm-and-auto-apply`
- Traitement simultané contrôlé (`max_concurrency`, borné).
- Ajout bouton frontend batch: `LM + Auto-postuler`.
- Correction métier importante:
  - `auto-apply` bloqué explicitement pour `mode_candidature == "email"`.
  - UI masque le bouton auto pour les candidatures mode email.

### 5. Tests ajoutés et validation

- Tests unitaires email: `tests/test_email_sender.py`.
- Tests unitaires plateformes (modes/garde-fous): `tests/test_candidatures_plateformes.py`.
- Tests d'intégration API candidatures + batch: `tests/test_candidatures_api.py`.
- Exécution validée:
  - `python -m unittest -v tests.test_email_sender tests.test_candidatures_plateformes tests.test_candidatures_api`
  - **19 tests OK**
  - `npm run build` frontend OK.

## Session du 06/03/2026 — CV correct + refonte cockpit frontend + correctifs UX

### 1. Configuration envoi email (CV)

- Correction du CV utilisé pour l'envoi des candidatures email:
  - `.env` mis à jour vers `CV_PATH=/app/config/cv_amadou_mactar_ndiaye.pdf`
- Redémarrage du service API Docker pour recharger la config.

### 2. Refonte UI "cockpit"

- Nouveau layout applicatif:
  - header modernisé
  - zone KPI en haut de page
  - contenu principal en 2 colonnes (table + pipeline)
- Ajout composant KPI:
  - `frontend/src/components/KpiStrip.tsx`
- Ajout composant pipeline candidatures:
  - `frontend/src/components/PipelineBoard.tsx`
- Thème visuel global unifié:
  - tokens CSS + typographie + fond dans `frontend/src/index.css`

### 3. Passe UX (lisibilité + cohérence)

- Harmonisation des badges et CTA:
  - `StatusBadge` (couleurs/contrastes, style pill)
  - `ScoreBadge` (échelle explicite `x/100`)
  - `ScrapeButton` aligné sur la palette cockpit
- Refonte `CandidaturesTable`:
  - vraie vue mobile en cartes
  - table desktop restylée
  - badges mode candidature unifiés

### 4. Correctifs layout et colonnes offres

- Correction débordement colonne pipeline:
  - grille `minmax(0,1fr)` + `min-w-0` sur la colonne principale
  - `PipelineBoard` en `w-full`
- Correction colonnes "Offres" non visibles:
  - scroll horizontal explicite sur desktop intermédiaire
  - largeur min de table
  - colonnes secondaires responsives (`Date limite`, `Source`, `Fiche`) selon breakpoints

### 5. Validation

- Build frontend validé à chaque étape:
  - `npm run build` ✅

---

## Session du 06/03/2026 — Sprint 3 (Observabilité et exploitation)

### 1. Logs structurés backend

- Ajout d'une brique de log JSON corrélable:
  - `app/logging_utils.py` avec `log_event(...)`
- Instrumentation des actions critiques:
  - scraping (`app/routers/scrape.py`)
  - candidatures (création, génération LM, envoi email, auto-apply) (`app/routers/candidatures.py`)
- Contextes portés dans les logs:
  - `offer_id`, `candidature_id`, `source`, `duration_ms`, `event`

### 2. Endpoint `/health` enrichi

- `app/routers/health.py` étendu avec checks détaillés:
  - check DB (`SELECT 1`)
  - check config minimale (variables critiques + chemins CV/diplôme)
- Réponse:
  - HTTP 200 si OK global
  - HTTP 503 si KO avec détail par check

### 3. Jobs planifiés

- Scheduler backend intégré:
  - `app/scheduler.py`
  - démarrage/arrêt au lifecycle API dans `app/main.py`
- Jobs:
  - scrape périodique
  - rescore périodique
  - batch LM optionnel (activable par env)
- Config ajoutée:
  - `SCHEDULER_ENABLED`, `SCHEDULER_SCRAPE_INTERVAL_S`, `SCHEDULER_RESCORE_INTERVAL_S`
  - `SCHEDULER_BATCH_ENABLED`, `SCHEDULER_BATCH_INTERVAL_S`, `SCHEDULER_BATCH_LIMIT`
- Exécution locale:
  - script `scripts/run_scheduled_jobs_once.py --simulate`
- Documentation:
  - `docs/SCHEDULER.md`

### 4. Stratégie d'alerte minimale (erreurs critiques)

- Ajout d'une alerte critique centralisée:
  - `emit_critical_alert(...)` dans `app/logging_utils.py`
- Handlers globaux FastAPI dans `app/main.py`:
  - HTTP 5xx -> log `CRITICAL` + `alert_code=HTTP_5XX` + `incident_id`
  - exception non gérée -> log `CRITICAL` + `alert_code=UNHANDLED_EXCEPTION` + `incident_id`
- Objectif atteint:
  - une erreur critique est immédiatement visible sans lire toute la stack

### Validation globale Sprint 3

- Tests:
  - `python -m unittest -v tests.test_alerting tests.test_scheduler tests.test_health_api tests.test_candidatures_plateformes tests.test_candidatures_api tests.test_email_sender`
  - **25 tests OK**
- Vérification Docker production-like:
  - `docker compose up -d` OK
  - `GET /health` OK
  - `POST /offres/scrape` OK
  - `POST /offres/score` OK

Sprint 3 est terminé à 100%.

---

## 2026-03-06 — Fix auto-apply FHF (bouton submit invisible)

### Problème

L'auto-apply Playwright pour les offres `emploi.fhf.fr` échouait systématiquement à l'étape `submit` avec un timeout de 30 secondes (`AUTOAPPLY_SUBMIT_FAILED`).

### Diagnostic

Le site FHF utilise Drupal qui génère **deux éléments** "Envoyer ma candidature" :
- `<input type="submit">` — **caché** (hidden, utilisé en interne par Drupal AJAX)
- `<button type="button">` — **visible** (le vrai bouton cliquable)

Le sélecteur `input[value*='Envoyer']` dans `EmploiFHFApplicator.submit()` matchait l'input invisible en premier → Playwright attendait qu'il devienne visible → timeout → échec.

### Correction

**Fichier :** `app/automation/emploi_fhf.py` — méthode `submit()`

Ancien sélecteur :
```python
"button:has-text('Envoyer ma candidature'), "
"input[value*='Envoyer'], "
"button:has-text('Envoyer')"
```

Nouveau sélecteur (`:visible` pour cibler uniquement le bouton visible) :
```python
"button:has-text('Envoyer ma candidature'):visible, "
"button:has-text('Envoyer'):visible"
```

### Validation

- Dry-run OK : screenshot confirme textarea rempli + bouton visible
- Envoi réel OK : candidature "RESPONSABLE PRODUCTION ALIMENTAIRE" envoyée avec succès sur emploi.fhf.fr

---

## 2026-03-06 — Détection mode email, fallback auto-apply, actions portail tiers

### 1. Détection de mode : email redevient prioritaire

**Problème :** Le commit `5b1cdd7` forçait `plateforme` pour toutes les URLs emploi-territorial/FHF, même quand l'offre n'avait pas de bouton "Déposer ma candidature" et ne proposait qu'un email. Résultat : le mode `email` n'apparaissait plus du tout pour ces offres.

**Correction :** Retour à la logique email-first dans `_detect_mode()` (backend) et `detectMode()` (frontend) :
1. `candidature_url` → `portail_tiers`
2. `contact_email` → `email`
3. `url` → `plateforme`
4. sinon → `inconnu`

24 candidatures existantes corrigées de `plateforme` → `email` en base.

### 2. Fallback email automatique dans auto-apply

**Problème :** Certaines offres emploi-territorial n'ont pas de bouton "Déposer ma candidature" sur leur page. L'auto-apply Playwright échouait à `find_apply_button` sans proposer d'alternative.

**Correction :** Dans `_auto_apply_with_db()` (`app/routers/candidatures.py`), quand `find_apply_button` échoue :
- Si un email de contact existe → envoi automatique par email (CV + LM en pièce jointe via SMTP)
- Mode candidature mis à jour vers `email`, statut → `envoyée`
- Log structuré avec `event=candidature_auto_apply_email_fallback`
- Si aucun email → erreur explicite (comme avant)

Ce fallback fonctionne aussi dans les opérations **bulk** (`bulk-auto-apply`, `bulk-generate-lm-and-auto-apply`).

### 3. Frontend : boutons email visibles pour sites auto-supportés

**Fichier :** `frontend/src/components/ApplyModal.tsx`

- `isAutoSupported` ne filtre plus sur `mode === 'plateforme'` — il suffit que l'URL soit emploi-territorial ou FHF
- Bouton **Email** affiché à côté des boutons Test/Auto-postuler quand un email de contact existe
- L'utilisateur peut choisir : auto-apply (avec fallback email intégré) ou envoi email direct

### 4. Séparation des actions portail tiers

**Problème :** Le bouton "Aller sur le portail tiers" marquait automatiquement la candidature comme `envoyée`, alors que l'utilisateur n'avait pas encore postulé sur le portail externe.

**Correction :** Deux boutons distincts :
- **"Aller sur le portail"** → ouvre le lien externe, ne change pas le statut
- **"Confirmer envoyée"** → marque comme envoyée une fois la candidature effectuée manuellement

### 5. Audit de production

Audit réalisé pour évaluer la mise en production :

**OK :** `.env` gitignored, gestion d'erreurs centralisée, healthcheck DB, logging structuré, config validée au startup.

**À faire pour un déploiement serveur :**
- Ajouter un reverse proxy (nginx/caddy) pour HTTPS + serving frontend static
- Créer un `docker-compose.prod.yml` (sans `--reload`, sans volume source)
- Changer le mot de passe DB par défaut
- Ajouter des workers Uvicorn (un seul actuellement, bloqué pendant les auto-apply Playwright)
- Mettre en place un backup DB

**Suffisant pour un usage localhost** (usage personnel sur PC).

### Validation

- Build frontend OK
- Build API Docker OK
- 4 candidatures brouillon testées et envoyées (2 auto-apply + 2 email)
- Commit : `bd7cb11`

---

## 2026-03-08 — Distinction frontend des plateformes + durcissement HelloWork

### 1. Frontend : libellés de mode plus précis

**Demande :** Ne plus afficher seulement `plateforme` côté interface, mais distinguer les plateformes automatiques connues.

**Correction :**
- Ajout d'un helper frontend pour mapper les URLs vers `FHF`, `Emploi-Territorial`, `HelloWork`
- Affichage détaillé dans la table des candidatures et la modale de postulation
- Filtre des offres mis à jour pour proposer `FHF`, `Emploi-Territorial`, `HelloWork`, `Email`, `Portail tiers`
- Suppression de `Inconnu` de l'interface de filtre

### 2. HelloWork : retour au login/mot de passe `.env`

**Contexte :** Le flux avait été orienté vers un login Google. Après vérification, l'usage réel est un compte HelloWork avec `HELLOWORK_LOGIN` / `HELLOWORK_PASSWORD`.

**Correction :**
- Retour au login email/mot de passe HelloWork
- Message d'erreur `AUTOAPPLY_MISSING_CREDENTIALS` aligné sur `HELLOWORK_LOGIN` et `HELLOWORK_PASSWORD`
- Nettoyage de `.env.example` et `app/config.py` pour retirer les variables Google devenues inutiles

### 3. HelloWork : inspection du site réel

Inspection réalisée en Edge visible, sans soumission :

- L'ancienne URL `https://www.hellowork.com/fr-fr/login.html` renvoie une `404`
- La vraie page de connexion est `https://www.hellowork.com/fr-fr/candidat/connexion-inscription.html#connexion`
- Le bouton `Postuler` existe bien sur les offres actives
- Certaines offres affichent d'abord une étape d'auth/création de compte après clic sur `Postuler`
- Certaines offres sont bloquées par la modale cookies avant clic sur `Postuler`

Captures produites :
- `scripts/screenshots/hellowork_login_inspect.png`
- `scripts/screenshots/hellowork_real_login_page.png`
- `scripts/screenshots/hellowork_google_redirect.png`
- `scripts/screenshots/hellowork_active_offer_1.png`

### 4. HelloWork : durcissement du flow auto-apply

**Fichier :** `app/automation/hellowork.py`

Améliorations ajoutées :
- correction de l'URL de login HelloWork
- gestion de la bannière cookies avant interaction
- support du vrai bouton `Postuler`, y compris la variante `data-cy=\"applyButton\"`
- détection d'une étape intermédiaire auth/création de compte après clic sur `Postuler`
- sauvegarde du `storage_state` quand la connexion réussit

**Important :** la détection du gate d'auth après `Postuler` est maintenant présente, mais la reprise automatique complète de cette branche n'est pas encore implémentée.

### Validation

- Tests API backend OK : `python -m unittest tests.test_candidatures_api`
- Aucune régression détectée sur FHF / Emploi-Territorial dans les tests existants
