import csv
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app.email_sender import send_candidature_email
from app.profil import load_profil

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
CONTACTS_FILE = BASE_DIR / "contacts.csv"
LOG_FILE      = BASE_DIR / "envois.json"

# Données du profil pour la signature
_profil   = load_profil()
_NOM      = _profil.get("nom", "")
_TEL      = _profil.get("telephone", "")
_EMAIL    = _profil.get("email", "")

# ─────────────────────────────────────────────
# 3 TEMPLATES D'EMAIL
# ─────────────────────────────────────────────
TEMPLATES = {
    "data": {
        "sujet": "Candidature – Data Analyste | 4 ans d'expérience",
        "corps": f"""Bonjour {{prenom}},

Je me permets de vous contacter dans le cadre d'une candidature spontanée pour un poste de Data Analyste.

Fort de 4 ans d'expérience en analyse de données, je maîtrise Python, SQL et Power BI (certifié PL-300) pour transformer des données brutes en insights actionnables.

Je serais ravi d'échanger sur les besoins de {{entreprise}} dans ce domaine.

Cordialement,
{_NOM}
{_TEL}
{_EMAIL}"""
    },

    "powerbi": {
        "sujet": "Candidature – Consultant Power BI | Certifié PL-300",
        "corps": f"""Bonjour {{prenom}},

Je vous contacte pour une candidature spontanée au poste de Consultant Power BI.

Certifié PL-300 avec 4 ans d'expérience, j'interviens sur la conception de dashboards, modélisation DAX, dataflows et déploiement en environnement Power BI Service.

N'hésitez pas à me contacter pour discuter d'une opportunité chez {{entreprise}}.

Cordialement,
{_NOM}
{_TEL}
{_EMAIL}"""
    },

    "sharepoint": {
        "sujet": "Candidature – Administrateur SharePoint Online | M365",
        "corps": f"""Bonjour {{prenom}},

Je me permets de vous adresser ma candidature pour un poste d'Administrateur SharePoint Online.

Avec 4 ans d'expérience sur l'écosystème Microsoft 365, j'interviens sur l'administration SharePoint Online, la gestion des permissions, la gouvernance et les migrations.

Je serais heureux d'en discuter avec vous concernant {{entreprise}}.

Cordialement,
{_NOM}
{_TEL}
{_EMAIL}"""
    }
}

# ─────────────────────────────────────────────
# CHARGEMENT DU LOG (évite les doublons)
# ─────────────────────────────────────────────
def charger_log():
    if LOG_FILE.exists():
        with open(str(LOG_FILE), "r") as f:
            return json.load(f)
    return {}

def sauvegarder_log(log):
    with open(str(LOG_FILE), "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────
def main():
    log = charger_log()
    envoyes = 0
    ignores = 0
    erreurs = 0

    print("\n🚀 Démarrage de l'envoi des candidatures...\n")

    with open(str(CONTACTS_FILE), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row["email"].strip()
            prenom = row["prenom"].strip()
            entreprise = row["entreprise"].strip()
            profil = row["profil"].strip().lower()  # data / powerbi / sharepoint

            # Vérifie si déjà envoyé
            if email in log:
                print(f"⏭️  Ignoré (déjà envoyé) : {prenom} <{email}>")
                ignores += 1
                continue

            # Vérifie que le profil existe
            if profil not in TEMPLATES:
                print(f"⚠️  Profil inconnu '{profil}' pour {email} — ignoré")
                ignores += 1
                continue

            template = TEMPLATES[profil]
            sujet = template["sujet"]
            corps = template["corps"].format(prenom=prenom, entreprise=entreprise)

            try:
                send_candidature_email(to_email=email, subject=sujet, lm_texte=corps)
                log[email] = {
                    "prenom": prenom,
                    "entreprise": entreprise,
                    "profil": profil,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                sauvegarder_log(log)
                print(f"✅ Envoyé : {prenom} ({entreprise}) — profil {profil}")
                envoyes += 1
            except Exception as e:
                print(f"❌ Erreur pour {email} : {e}")
                erreurs += 1

    print(f"\n─────────────────────────────")
    print(f"📊 Résultat :")
    print(f"   ✅ Envoyés  : {envoyes}")
    print(f"   ⏭️  Ignorés  : {ignores}")
    print(f"   ❌ Erreurs  : {erreurs}")
    print(f"─────────────────────────────\n")
    return {"envoyes": envoyes, "ignores": ignores, "erreurs": erreurs}

if __name__ == "__main__":
    main()
