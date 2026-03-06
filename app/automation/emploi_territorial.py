"""Applicator pour emploi-territorial.fr."""
from app.automation.base import BaseApplicator


class EmploiTerritorialApplicator(BaseApplicator):
    site_url = "https://www.emploi-territorial.fr"
    login_url = "https://www.emploi-territorial.fr/demandeur/login"

    async def login(self, page, login: str, password: str) -> bool:
        try:
            await page.goto(self.login_url, wait_until="networkidle", timeout=30000)
            await page.fill("input[name='identCand']", login)
            await page.fill("input[name='password']", password)
            await page.click("button:has-text('me connecter')")
            await page.wait_for_load_state("networkidle", timeout=15000)
            # Vérifie qu'on n'est plus sur la page de login
            if "/login" not in page.url:
                return True
            print("[emploi-territorial] Login échoué (toujours sur /login)")
            return False
        except Exception as e:
            print(f"[emploi-territorial][login] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Clique sur le bouton 'Déposer ma candidature'."""
        selectors = [
            "a.btn-candidature-top",
            "button.btn-candidature-top",
            "a:has-text('Déposer ma candidature')",
            "button:has-text('Déposer ma candidature')",
            "a:has-text('Postuler')",
            "button:has-text('Postuler')",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except Exception:
                continue
        print("[emploi-territorial] Aucun bouton candidature trouvé")
        return False

    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil: dict = None, offer_title: str = "", offer_company: str = "") -> bool:
        """Upload CV (champ 1) + LM générée en PDF (champ 2) + diplôme (champ 3)."""
        try:
            from app.config import settings

            file_inputs = await page.locator("input[type='file']").all()
            print(f"[emploi-territorial] {len(file_inputs)} champ(s) fichier trouvé(s)")

            if len(file_inputs) >= 1:
                await file_inputs[0].set_input_files(cv_path)
                print("[emploi-territorial] CV uploadé")

            if len(file_inputs) >= 2:
                if lm_texte and profil:
                    from app.automation.lm_generator import generate_lm_pdf
                    lm_pdf = generate_lm_pdf(lm_texte, profil, offer_title, offer_company)
                    await file_inputs[1].set_input_files(str(lm_pdf))
                    print(f"[emploi-territorial] LM PDF uploadée : {lm_pdf}")
                else:
                    await file_inputs[1].set_input_files(cv_path)
                    print("[emploi-territorial] LM fallback : CV uploadé à la place")

            if len(file_inputs) >= 3 and settings.diplome_path:
                await file_inputs[2].set_input_files(settings.diplome_path)
                print(f"[emploi-territorial] Diplôme uploadé : {settings.diplome_path}")

            return True
        except Exception as e:
            print(f"[emploi-territorial][fill_form] Erreur : {e}")
            return False

    async def submit(self, page) -> bool:
        """Coche la checkbox RGPD puis soumet le formulaire."""
        try:
            # Checkbox RGPD — plusieurs sélecteurs possibles
            rgpd_selectors = [
                "input[type='checkbox'][name*='rgpd']",
                "input[type='checkbox'][name*='cnil']",
                "input[type='checkbox'][name*='politique']",
                "input[type='checkbox'][name*='traitement']",
                "input[type='checkbox'][name*='donnees']",
                "input[type='checkbox'][name*='gdpr']",
                "input[type='checkbox'][id*='rgpd']",
                "input[type='checkbox'][id*='cnil']",
                "input[type='checkbox'][id*='politique']",
            ]
            for sel in rgpd_selectors:
                cb = page.locator(sel).first
                if await cb.count() > 0:
                    if not await cb.is_checked():
                        await cb.check()
                        print(f"[emploi-territorial] Checkbox RGPD cochée ({sel})")
                    break
            else:
                # Fallback : cherche la dernière checkbox du formulaire
                all_checkboxes = page.locator("input[type='checkbox']")
                count = await all_checkboxes.count()
                if count > 0:
                    last_cb = all_checkboxes.nth(count - 1)
                    if not await last_cb.is_checked():
                        await last_cb.check()
                        print("[emploi-territorial] Dernière checkbox cochée (fallback RGPD)")

            submit_selectors = [
                "button:has-text('Postuler à cet')",
                "button:has-text('POSTULER')",
                "button:has-text('Postuler')",
                "input[type='submit']",
                "button[type='submit']",
                "button:has-text('Envoyer')",
                "button:has-text('Valider')",
            ]
            for sel in submit_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    print("[emploi-territorial] Formulaire soumis")
                    return True
            print("[emploi-territorial] Bouton de soumission non trouvé")
            return False
        except Exception as e:
            print(f"[emploi-territorial][submit] Erreur : {e}")
            return False
