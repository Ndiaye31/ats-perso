# Sources de données – Offres d’emploi public (France)

Ce document liste un ensemble structuré de sites publics français exploitables pour un projet de scraping, parsing PDF, extraction d’emails, normalisation et déduplication d’offres d’emploi.

⚠️ Toujours vérifier :
- robots.txt
- Conditions générales d’utilisation
- Fréquence de requêtes (throttling recommandé : 1–2 req/sec)
- User-Agent explicite

---

# 1. AGRÉGATEURS NATIONAUX

## 1.1 Place de l’Emploi Public
URL : https://www.place-emploi-public.gouv.fr

### Type
Portail officiel interministériel regroupant les offres des 3 fonctions publiques :
- État
- Territoriale
- Hospitalière

### Structure technique
- Pages HTML structurées
- Filtres par catégorie, localisation, type de contrat
- Pagination classique
- Chaque offre possède une page dédiée
- Peu ou pas de PDF natif (renvois possibles vers autres portails)

### Champs généralement disponibles
- Titre
- Ministère / organisme
- Localisation
- Date limite
- Catégorie (A/B/C)
- Type de contrat
- Description détaillée
- Modalités de candidature
- Lien vers plateforme

### Intérêt technique
✔ Bon point d’entrée
✔ HTML propre
✔ Extraction simple
✔ Bon volume
✔ Utile pour scoring et normalisation

---

## 1.2 France Travail (ex-Pôle emploi)
URL : https://www.francetravail.fr

### Type
Portail national d’offres d’emploi (public + privé)

### Structure technique
- Interface fortement dynamique (JS)
- API interne probable
- Pagination dynamique
- Anti-bot léger
- Redirections fréquentes vers site employeur

### Particularités
- Certaines offres publiques redirigent vers portails officiels
- Métadonnées parfois partielles

### Intérêt technique
✔ Cas d’école pour Playwright
✔ Extraction URL finale
✔ Détection redirections

---

# 2. EMPLOI TERRITORIAL

## 2.1 Emploi Territorial
URL : https://www.emploi-territorial.fr

### Type
Portail spécialisé pour la fonction publique territoriale

### Structure technique
- Liste HTML paginée
- Fiches détaillées
- Beaucoup de PDF joints
- Modalités souvent par email direct

### Champs fréquents
- Cadre d’emploi
- Catégorie
- Collectivité
- Missions
- Profil
- Date limite
- Email RH
- Pièces demandées (CV, LM, diplômes)

### Complexité
- Parsing PDF nécessaire
- Emails souvent dans texte libre
- Offres parfois republiées ailleurs (déduplication importante)

### Intérêt technique
✔ Excellent terrain pour extraction email
✔ Parsing PDF
✔ Normalisation collectivités
✔ Gestion required_documents

---

# 3. FONCTION PUBLIQUE HOSPITALIÈRE

## 3.1 Fédération Hospitalière de France (FHF)
URL : https://emploi.fhf.fr

### Type
Portail d’offres hospitalières publiques

### Structure technique
- HTML structuré
- Pagination
- Parfois PDF
- Email direct fréquent

### Données utiles
- Hôpital
- Service
- Type de contrat
- Profil recherché
- Contact RH

### Intérêt technique
✔ Bon volume
✔ Cas simple d’email apply
✔ Normalisation établissements (CHU, CH, EHPAD)

---

# 4. COLLECTIVITÉS LOCALES (SITES INDÉPENDANTS)

Chaque collectivité dispose de sa propre page “Recrutement”.

## 4.1 Grandes Villes
Exemples :
- Ville de Paris
- Ville de Lyon
- Ville de Marseille

### Structure typique
- Page “Recrutement”
- Liste HTML ou PDF
- Candidature via :
  - Email
  - Formulaire interne
  - Plateforme dédiée

### Particularités
- Structure différente selon la ville
- Certaines redirigent vers Emploi Territorial

### Intérêt technique
✔ Cas variés (email + formulaire)
✔ Test Playwright
✔ Détection multi-sources

---

## 4.2 Régions
Exemples :
- Région Île-de-France
- Région Occitanie
- Région Auvergne-Rhône-Alpes

### Structure
- Page carrière dédiée
- Offres parfois en PDF
- Parfois plateforme externe

### Intérêt technique
✔ Normalisation régionale
✔ Extraction grade / catégorie

---

## 4.3 Départements
Exemples :
- Conseil départemental des Yvelines
- Conseil départemental du Nord

### Structure
- Page “Offres d’emploi”
- Souvent PDF
- Email direct fréquent

### Intérêt technique
✔ Extraction PDF
✔ Email dans texte libre
✔ Déduplication (souvent aussi sur Emploi Territorial)

---

# 5. UNIVERSITÉS & ÉTABLISSEMENTS D’ENSEIGNEMENT SUPÉRIEUR

Exemples :
- Université Paris Cité
- Université Lyon 1
- Université Bordeaux

### Types d’offres
- BIATSS
- Contractuels
- Ingénieurs
- Administratifs

### Structure
- Page recrutement
- PDF fréquents
- Parfois redirection vers Place de l’Emploi Public

### Complexité
- Structure très variable
- Parfois portails RH spécifiques

### Intérêt technique
✔ Cas multi-structures
✔ Parsing PDF
✔ Normalisation métier (BIATSS, ITRF)

---

# 6. ORGANISMES PUBLICS NATIONAUX

Exemples :
- CNRS
- INSERM
- ANSES
- Météo-France
- URSSAF
- CAF
- CPAM
- Chambres de Commerce (CCI)

### Structure
- Portail carrière interne
- Formulaire candidature
- Plateforme RH dédiée

### Particularités
- Certaines offres uniquement via portail interne
- Peu d’email direct

### Intérêt technique
✔ Automatisation formulaire (Playwright)
✔ Extraction multi-pages

---

# 7. CAS TECHNIQUES À ANTICIPER

## 7.1 PDF
- Offres en pièce jointe
- Emails dans corps du PDF
- Pièces demandées listées dans PDF

Outils recommandés :
- pdfplumber
- tika

---

## 7.2 Email Extraction
Heuristiques :
- Regex email
- Recherche mots-clés : “candidature”, “envoyer”, “CV”, “LM”
- Vérification domaine collectivité

---

## 7.3 Déduplication
Sources multiples possibles :
- Collectivité
- Emploi Territorial
- Place Emploi Public

Stratégie recommandée :
- Hash : titre normalisé + employeur + ville + deadline
- Similarité description (option avancée)

---

# 8. STRATÉGIE DE DÉMARRAGE RECOMMANDÉE

Ordre optimal pour implémentation :

1. Place de l’Emploi Public (HTML propre)
2. Emploi Territorial (PDF + email)
3. FHF (hospitalier)
4. Une grande ville
5. Une université

---

# 9. BONNES PRATIQUES SCRAPING

- Respect robots.txt
- Backoff exponentiel en cas d’erreur
- Timeout strict
- Logs détaillés
- Stockage HTML brut pour debug
- Screenshots en cas d’échec Playwright

---

# 10. OBJECTIF FINAL

Construire un pipeline :
Scrape → Normalize → Hash → Deduplicate → Score → Generate LM → Apply → Track

Ce document sert de base pour créer des connecteurs modulaires par source.

