"""Applicator pour choisirleservicepublic.gouv.fr (CSP).

Flow candidature :
  1. login             → connexion sur /connexion avec csp_login / csp_password
  2. navigate_to_offer → navigue vers l'URL CSP de l'offre
  3. find_apply_button → cherche le bouton "Postuler" ; si la page redirige
                         vers un domaine non-CSP, stocke l'URL dans
                         self.external_portal_url et retourne False.
  4. fill_form         → upload CV + LM PDF (ou textarea LM)
  5. submit            → soumet le formulaire
"""
from app.automation.base import BaseApplicator

CSP_DOMAIN = "choisirleservicepublic.gouv.fr"


class ChoisirServicePublicApplicator(BaseApplicator):
    site_url = "https://choisirleservicepublic.gouv.fr"
    login_url = "https://choisirleservicepublic.gouv.fr/connexion"

    def __init__(self):
        self.external_portal_url: str | None = None

    async def login(self, page, login: str, password: str) -> bool:
        try:
            await page.goto(self.login_url, wait_until="networkidle", timeout=30000)
            await page.fill("input[type='email']", login)
            await page.fill("input[type='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle", timeout=15000)
            return "/connexion" not in page.url and "/login" not in page.url
        except Exception as e:
            print(f"[csp][login] {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Clique Postuler. Si redirection hors CSP → stocke external_portal_url, retourne False."""
        selectors = [
            "a:has-text('Postuler')",
            "button:has-text('Postuler')",
            "a:has-text('Candidater')",
            "button:has-text('Candidater')",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    if CSP_DOMAIN not in page.url:
                        print(f"[csp] Portail externe détecté : {page.url}")
                        self.external_portal_url = page.url
                        return False
                    return True
            except Exception:
                continue
        print("[csp] Aucun bouton Postuler trouvé")
        return False

    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil=None, offer_title: str = "",
                        offer_company: str = "") -> bool:
        """CV et diplôme déjà présents dans le profil CSP — on remplit uniquement la LM."""
        try:
            selectors = [
                "textarea[name*='lettre']",
                "textarea[name*='message']",
                "textarea[name*='motivation']",
                "textarea[placeholder*='motivation']",
                "textarea[placeholder*='lettre']",
            ]
            for sel in selectors:
                ta = page.locator(sel).first
                if await ta.count() > 0:
                    if lm_texte:
                        await ta.fill(lm_texte)
                        print("[csp] LM remplie dans textarea")
                    return True
            # Aucun textarea trouvé — la plateforme n'en demande peut-être pas
            print("[csp] Pas de textarea LM trouvé, on continue")
            return True
        except Exception as e:
            print(f"[csp][fill_form] {e}")
            return False

    async def submit(self, page) -> bool:
        try:
            for sel in [
                "button:has-text('Envoyer ma candidature'):visible",
                "button:has-text('Valider'):visible",
                "button[type='submit']:visible",
                "input[type='submit']:visible",
            ]:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    print("[csp] Candidature soumise")
                    return True
            print("[csp] Bouton de soumission non trouvé")
            return False
        except Exception as e:
            print(f"[csp][submit] {e}")
            return False
