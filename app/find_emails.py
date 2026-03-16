import requests
import csv
import time
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG — clé API Hunter.io (depuis .env)
# ─────────────────────────────────────────────
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

INPUT_FILE  = "entreprises.csv"
OUTPUT_FILE = "contacts.csv"

# ─────────────────────────────────────────────
# RECHERCHE EMAIL VIA HUNTER.IO
# ─────────────────────────────────────────────
def _extraire_depuis_data(data):
    """Extrait le meilleur email RH depuis une réponse Hunter."""
    emails = data.get("emails", [])
    mots_rh = ["rh", "hr", "recrutement", "recruitment", "talent", "people", "drh"]

    for email_data in emails:
        poste = (email_data.get("position") or "").lower()
        if any(mot in poste for mot in mots_rh):
            return (
                email_data.get("value"),
                email_data.get("first_name") or "Madame/Monsieur",
                email_data.get("last_name") or ""
            )

    if emails:
        e = emails[0]
        return (
            e.get("value"),
            e.get("first_name") or "Madame/Monsieur",
            e.get("last_name") or ""
        )

    return None, None, None


def chercher_email(domaine, entreprise=""):
    """Cherche par domaine si disponible, sinon par nom d'entreprise."""
    url = "https://api.hunter.io/v2/domain-search"

    # Tentative 1 : recherche par domaine
    if domaine:
        try:
            r = requests.get(url, params={"domain": domaine, "api_key": HUNTER_API_KEY, "limit": 5}, timeout=10)
            data = r.json().get("data", {})
            email, prenom, nom = _extraire_depuis_data(data)
            if email:
                return email, prenom, nom
        except Exception as ex:
            print(f"   ⚠️  Erreur Hunter (domaine) : {ex}")

    # Tentative 2 : recherche par nom d'entreprise
    if entreprise:
        try:
            r = requests.get(url, params={"company": entreprise, "api_key": HUNTER_API_KEY, "limit": 5}, timeout=10)
            data = r.json().get("data", {})
            email, prenom, nom = _extraire_depuis_data(data)
            if email:
                return email, prenom, nom
        except Exception as ex:
            print(f"   ⚠️  Erreur Hunter (company) : {ex}")

    return None, None, None

# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────
def main():
    print("\n🔍 Recherche des emails RH via Hunter.io...\n")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier '{INPUT_FILE}' introuvable. Lance d'abord scraper_ft.py")
        return

    contacts = []
    trouves  = 0
    ignores  = 0

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        lignes = list(reader)

    total = len(lignes)

    for i, row in enumerate(lignes):
        entreprise = row["entreprise"]
        domaine    = row["domaine"]
        profil     = row["profil"]
        lieu       = row["lieu"]

        print(f"[{i+1}/{total}] {entreprise} ({domaine or 'pas de domaine → recherche par nom'})")

        email, prenom, nom = chercher_email(domaine, entreprise)

        if email:
            contacts.append({
                "prenom":     prenom,
                "nom":        nom,
                "email":      email,
                "entreprise": entreprise,
                "profil":     profil,
                "lieu":       lieu
            })
            print(f"   ✅ {prenom} {nom} — {email}")
            trouves += 1
        else:
            print(f"   ❌ Aucun email trouvé")
            ignores += 1

        time.sleep(1.0)  # respecter le rate limit Hunter (2 appels possibles par entreprise)

    # Sauvegarde
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["prenom", "nom", "email", "entreprise", "profil", "lieu"])
        writer.writeheader()
        writer.writerows(contacts)

    print(f"\n─────────────────────────────")
    print(f"📊 Résultat :")
    print(f"   ✅ Emails trouvés : {trouves}")
    print(f"   ⏭️  Ignorés        : {ignores}")
    print(f"   📁 Fichier généré : {OUTPUT_FILE}")
    print(f"\n👉 Lance maintenant : python send_candidatures.py\n")
    return {"trouves": trouves, "ignores": ignores}

if __name__ == "__main__":
    main()
