"""Applicator pour hellowork.com.

Flow candidature (SPA, login requis) :
  1. Login via page connexion → remplir email/mdp
  2. Naviguer vers l'offre
  3. Cliquer "Postuler" (bouton ou lien #postuler)
  4. Remplir le formulaire (CV, message/LM)
  5. Soumettre

Note : HelloWork peut détecter les navigateurs headless.
Si Chromium headless est bloqué, configurer headless=False + xvfb.
"""
from app.automation.base import BaseApplicator


class HelloWorkApplicator(BaseApplicator):
    site_url = "https://www.hellowork.com"
    login_url = "https://www.hellowork.com/fr-fr/login.html"

    async def login(self, page, login: str, password: str) -> bool:
        """Connexion au compte HelloWork."""
        try:
            await page.goto(self.site_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Chercher le bouton/lien de connexion sur la page d'accueil
            login_selectors = [
                "a:has-text('Connexion')",
                "a:has-text('Se connecter')",
                "button:has-text('Connexion')",
                "a[href*='login']",
                "a[href*='connexion']",
            ]
            clicked = False
            for sel in login_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    clicked = True
                    break

            if not clicked:
                # Fallback : naviguer directement vers la page login
                await page.goto(self.login_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            # Remplir le formulaire de connexion
            email_selectors = [
                "input[name='email']",
                "input[type='email']",
                "input[id*='email']",
                "input[id*='login']",
                "input[name='username']",
            ]
            for sel in email_selectors:
                field = page.locator(sel).first
                if await field.count() > 0:
                    await field.fill(login)
                    print(f"[hellowork][login] Email rempli avec sélecteur: {sel}")
                    break
            else:
                print("[hellowork][login] Champ email non trouvé")
                return False

            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[id*='password']",
            ]
            for sel in password_selectors:
                field = page.locator(sel).first
                if await field.count() > 0:
                    await field.fill(password)
                    print(f"[hellowork][login] Mot de passe rempli avec sélecteur: {sel}")
                    break
            else:
                print("[hellowork][login] Champ mot de passe non trouvé")
                return False

            # Soumettre le formulaire
            submit_selectors = [
                "button[type='submit']",
                "button:has-text('Connexion')",
                "button:has-text('Se connecter')",
                "input[type='submit']",
            ]
            for sel in submit_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    break

            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            # Vérifier le succès (pas de page login, présence d'éléments user)
            current_url = page.url
            if "login" in current_url.lower() or "connexion" in current_url.lower():
                print("[hellowork][login] Échec — toujours sur la page de connexion")
                return False

            print("[hellowork][login] Connexion réussie")
            return True

        except Exception as e:
            print(f"[hellowork][login] Erreur : {e}")
            return False

    async def navigate_to_offer(self, page, offer_url: str) -> bool:
        """Navigue vers la page de l'offre HelloWork."""
        try:
            await page.goto(offer_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Vérifier que la page a bien chargé (présence d'un titre)
            h1 = page.locator("h1").first
            if await h1.count() > 0:
                title = await h1.inner_text()
                print(f"[hellowork][navigate] Page chargée : {title[:60]}")
                return True

            print("[hellowork][navigate] Page chargée mais pas de h1 trouvé")
            return True
        except Exception as e:
            print(f"[hellowork][navigate] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Cherche et clique sur le bouton Postuler."""
        selectors = [
            "a[href='#postuler']",
            "a[href*='postuler']",
            "button:has-text('Postuler')",
            "a:has-text('Postuler')",
            "button:has-text('Candidater')",
            "a:has-text('Candidater')",
            "#postuler",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    print(f"[hellowork][apply] Bouton cliqué : {sel}")
                    return True
            except Exception:
                continue

        print("[hellowork][apply] Aucun bouton Postuler trouvé")
        return False

    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil: dict = None, offer_title: str = "", offer_company: str = "") -> bool:
        """Remplit le formulaire de candidature HelloWork."""
        try:
            # Upload CV
            if cv_path:
                file_input = page.locator("input[type='file']").first
                if await file_input.count() > 0:
                    await file_input.set_input_files(cv_path)
                    print(f"[hellowork][fill_form] CV uploadé : {cv_path}")
                    await page.wait_for_timeout(2000)

            # Message / Lettre de motivation (textarea)
            if lm_texte:
                textarea_selectors = [
                    "textarea[name*='message']",
                    "textarea[name*='motivation']",
                    "textarea[id*='message']",
                    "textarea:visible",
                ]
                for sel in textarea_selectors:
                    textarea = page.locator(sel).first
                    if await textarea.count() > 0:
                        await textarea.fill(lm_texte)
                        print(f"[hellowork][fill_form] Message rempli avec : {sel}")
                        break

            return True
        except Exception as e:
            print(f"[hellowork][fill_form] Erreur : {e}")
            return False

    async def submit(self, page) -> bool:
        """Soumet le formulaire de candidature."""
        try:
            submit_selectors = [
                "button[type='submit']:has-text('Postuler')",
                "button[type='submit']:has-text('Envoyer')",
                "button:has-text('Envoyer ma candidature')",
                "button:has-text('Postuler')",
                "button[type='submit']",
            ]
            for sel in submit_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    # Vérifier que le bouton n'est pas disabled
                    is_disabled = await btn.is_disabled()
                    if is_disabled:
                        print(f"[hellowork][submit] Bouton disabled : {sel}")
                        continue
                    await btn.click()
                    await page.wait_for_timeout(5000)
                    print(f"[hellowork][submit] Formulaire soumis via : {sel}")
                    return True

            print("[hellowork][submit] Aucun bouton de soumission trouvé")
            return False
        except Exception as e:
            print(f"[hellowork][submit] Erreur : {e}")
            return False
