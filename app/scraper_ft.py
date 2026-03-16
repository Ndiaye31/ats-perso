import requests
import csv
import time
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG — clés API France Travail (depuis .env)
# ─────────────────────────────────────────────
CLIENT_ID     = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")

OUTPUT_FILE = "entreprises.csv"

# Mots-clés et profil associé
RECHERCHES = [
    {"q": "data analyste",        "profil": "data"},
    {"q": "power bi consultant",  "profil": "powerbi"},
    {"q": "sharepoint online",    "profil": "sharepoint"},
]

# ─────────────────────────────────────────────
# AUTHENTIFICATION
# ─────────────────────────────────────────────
def get_token():
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    params = {"realm": "/partenaire"}
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "api_offresdemploiv2 o2dsoffre"
    }
    r = requests.post(url, params=params, data=data)
    r.raise_for_status()
    token = r.json()["access_token"]
    print("✅ Token obtenu")
    return token

# ─────────────────────────────────────────────
# EXTRACTION DU DOMAINE
# ─────────────────────────────────────────────
def extraire_domaine(url_site):
    if not url_site:
        return ""
    try:
        parsed = urlparse(url_site if url_site.startswith("http") else "https://" + url_site)
        domaine = parsed.netloc.replace("www.", "")
        return domaine
    except:
        return ""

# ─────────────────────────────────────────────
# RECHERCHE DES OFFRES
# ─────────────────────────────────────────────
def chercher_offres(token, motcle, max_offres=50):
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    params = {
        "motsCles":    motcle,
        "range":       f"0-{max_offres - 1}",
        "publieeDepuis": 31  # offres des 31 derniers jours
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        print(f"⚠️  Erreur API pour '{motcle}' : {r.status_code}")
        return []
    resultats = r.json().get("resultats", [])
    print(f"   → {len(resultats)} offres trouvées pour '{motcle}'")
    return resultats

# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────
def main():
    print("\n🚀 Démarrage du scraping France Travail...\n")

    token = get_token()

    entreprises = {}  # domaine → données (pour éviter les doublons)

    for recherche in RECHERCHES:
        motcle = recherche["q"]
        profil = recherche["profil"]
        print(f"\n🔍 Recherche : {motcle}")

        offres = chercher_offres(token, motcle)

        for offre in offres:
            entreprise_info = offre.get("entreprise", {})
            nom        = entreprise_info.get("nom", "").strip()
            url_site   = entreprise_info.get("url", "").strip()
            domaine    = extraire_domaine(url_site)
            lieu       = offre.get("lieuTravail", {}).get("libelle", "")
            titre      = offre.get("intitule", "")

            if not nom:
                continue

            cle = domaine if domaine else nom.lower().replace(" ", "")

            if cle not in entreprises:
                entreprises[cle] = {
                    "entreprise": nom,
                    "domaine":    domaine,
                    "lieu":       lieu,
                    "profil":     profil,
                    "offre":      titre
                }

        time.sleep(1)  # pause pour ne pas surcharger l'API

    # Sauvegarde CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["entreprise", "domaine", "lieu", "profil", "offre"])
        writer.writeheader()
        writer.writerows(entreprises.values())

    print(f"\n✅ {len(entreprises)} entreprises uniques sauvegardées dans '{OUTPUT_FILE}'")
    print("👉 Lance maintenant : python find_emails.py\n")
    return {"entreprises": len(entreprises)}

if __name__ == "__main__":
    main()
