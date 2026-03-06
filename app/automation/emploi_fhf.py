"""Applicator pour emploi.fhf.fr.

Flow candidature :
  1. find_apply_button → clique "Je candidate!" + "Je confirme" (1ère modale)
  2. fill_form         → remplit le textarea "message lié à votre candidature"
  3. submit            → clique "Envoyer ma candidature"
"""
from app.automation.base import BaseApplicator


class EmploiFHFApplicator(BaseApplicator):
    site_url = "https://emploi.fhf.fr"
    login_url = "https://emploi.fhf.fr/login"

    async def login(self, page, login: str, password: str) -> bool:
        try:
            await page.goto(self.login_url, wait_until="networkidle", timeout=30000)
            await page.click("a:has-text('Connexion'), button:has-text('Connexion')")
            await page.wait_for_timeout(1500)
            await page.fill("#edit-name--2", login)
            await page.fill("#edit-pass", password)
            await page.click("#edit-submit--2")
            await page.wait_for_load_state("networkidle", timeout=15000)
            if "/login" not in page.url:
                return True
            print("[fhf] Login échoué (toujours sur /login)")
            return False
        except Exception as e:
            print(f"[fhf][login] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Clique 'Je candidate!' puis 'Je confirme' (1ère modale de confirmation)."""
        try:
            # Étape 1 : bouton "Je candidate!"
            btn = page.locator("a:has-text('Je candidate!'), button:has-text('Je candidate!')").first
            if await btn.count() == 0:
                print("[fhf] Bouton 'Je candidate!' non trouvé")
                return False
            await btn.click()
            await page.wait_for_timeout(2000)

            # Étape 2 : modale "Souhaitez-vous confirmer votre candidature et envoyer votre CV ?"
            confirm = page.locator("button:has-text('Je confirme'), a:has-text('Je confirme')").first
            if await confirm.count() == 0:
                print("[fhf] Modale 'Je confirme' non trouvée")
                return False
            await confirm.click()
            await page.wait_for_timeout(2000)
            print("[fhf] Je confirme cliqué — textarea message attendu")
            return True
        except Exception as e:
            print(f"[fhf][find_apply_button] Erreur : {e}")
            return False

    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil: dict = None, offer_title: str = "", offer_company: str = "") -> bool:
        """Remplit le textarea 'message lié à votre candidature' avec la LM (optionnel)."""
        try:
            textarea = page.locator("textarea[name='message'], textarea[placeholder*='message']").first
            if await textarea.count() > 0:
                if lm_texte:
                    await textarea.fill(lm_texte)
                    print("[fhf] Message de candidature rempli avec la LM")
                else:
                    print("[fhf] Pas de LM — textarea laissé vide")
            else:
                print("[fhf] Textarea message non trouvé — on continue quand même")
            return True
        except Exception as e:
            print(f"[fhf][fill_form] Erreur : {e}")
            return False

    async def submit(self, page) -> bool:
        """Clique sur 'Envoyer ma candidature'.

        Drupal génère un <input type=submit> caché + un <button> visible.
        On cible le bouton visible pour éviter un timeout sur l'input hidden.
        """
        try:
            btn = page.locator(
                "button:has-text('Envoyer ma candidature'):visible, "
                "button:has-text('Envoyer'):visible"
            ).first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                print("[fhf] Candidature envoyée")
                return True
            print("[fhf] Bouton 'Envoyer ma candidature' non trouvé")
            return False
        except Exception as e:
            print(f"[fhf][submit] Erreur : {e}")
            return False
