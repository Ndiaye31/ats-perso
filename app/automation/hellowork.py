"""Applicator pour hellowork.com avec login email/mot de passe."""
from __future__ import annotations

from pathlib import Path

from app.automation.base import BaseApplicator
from app.config import settings


class HelloWorkApplicator(BaseApplicator):
    site_url = "https://www.hellowork.com/fr-fr/"
    login_url = "https://www.hellowork.com/fr-fr/candidat/connexion-inscription.html#connexion"

    def _storage_state_path(self) -> Path:
        return Path(settings.hellowork_storage_state_path)

    async def _dismiss_cookie_banner(self, page) -> None:
        selectors = (
            "button:has-text('Continuer sans accepter')",
            "button:has-text('Tout accepter')",
            ".hw-cc-modal__wrapper button",
            "#hw-cc-notice-continue-without-accepting",
        )
        for sel in selectors:
            try:
                button = page.locator(sel).first
                if await button.count() == 0:
                    continue
                await button.click(timeout=1500)
                await page.wait_for_timeout(1000)
                return
            except Exception:
                continue

    async def _looks_like_auth_gate(self, page) -> bool:
        checks = (
            "text=Se connecter à Hellowork avec Google",
            "text=Continuer avec Google",
            "text=Créez votre compte",
            "text=Ravi de vous retrouver sur Hellowork !",
            "a[href*='connexion-inscription']",
        )
        for sel in checks:
            try:
                locator = page.locator(sel).first
                if await locator.count() > 0:
                    return True
            except Exception:
                continue
        return False

    async def _is_logged_in(self, page) -> bool:
        try:
            url = (page.url or "").lower()
            if "hellowork.com" not in url:
                return False
            if "connexion-inscription" in url:
                return False
            for sel in (
                "a[href*='mon-compte']",
                "a[href*='logoff']",
                "a:has-text('Déconnexion')",
                "a:has-text('Mon compte')",
            ):
                locator = page.locator(sel).first
                if await locator.count() > 0:
                    return True
            return False
        except Exception:
            return False

    async def _save_storage_state(self, page) -> None:
        try:
            path = self._storage_state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            await page.context.storage_state(path=str(path))
        except Exception as e:
            print(f"[hellowork][auth] Impossible de sauvegarder le storage_state: {e}")

    async def login(self, page, login: str, password: str) -> bool:
        try:
            await page.goto(self.site_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            await self._dismiss_cookie_banner(page)
            if await self._is_logged_in(page):
                await self._save_storage_state(page)
                return True

            await page.goto(self.login_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            await self._dismiss_cookie_banner(page)

            email_selectors = (
                "input[name='email']",
                "input[type='email']",
                "input[autocomplete='username']",
            )
            password_selectors = (
                "input[name='password']",
                "input[type='password']",
                "input[autocomplete='current-password']",
            )
            submit_selectors = (
                "button[type='submit']",
                "button:has-text('Je me connecte')",
                "button:has-text('Se connecter')",
            )

            email_filled = False
            for sel in email_selectors:
                field = page.locator(sel).first
                if await field.count() > 0:
                    await field.fill(login)
                    email_filled = True
                    break
            if not email_filled:
                print("[hellowork][login] Champ email introuvable")
                return False

            password_filled = False
            for sel in password_selectors:
                field = page.locator(sel).first
                if await field.count() > 0:
                    await field.fill(password)
                    password_filled = True
                    break
            if not password_filled:
                print("[hellowork][login] Champ mot de passe introuvable")
                return False

            for sel in submit_selectors:
                button = page.locator(sel).first
                if await button.count() > 0:
                    await button.click()
                    break

            await page.wait_for_timeout(4000)
            if await self._is_logged_in(page):
                await self._save_storage_state(page)
                return True

            current_url = (page.url or "").lower()
            if "connexion-inscription" in current_url:
                print("[hellowork][login] Échec — toujours sur la page de connexion")
                return False

            await self._save_storage_state(page)
            return True
        except Exception as e:
            print(f"[hellowork][login] Erreur : {e}")
            return False

    async def navigate_to_offer(self, page, offer_url: str) -> bool:
        try:
            await page.goto(offer_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)
            await self._dismiss_cookie_banner(page)
            return True
        except Exception as e:
            print(f"[hellowork][navigate] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        await self._dismiss_cookie_banner(page)
        selectors = [
            "[data-cy='applyButton']",
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
                    await page.wait_for_timeout(2500)
                    if await self._looks_like_auth_gate(page):
                        print("[hellowork][apply] Étape auth/création de compte détectée après clic Postuler")
                    return True
            except Exception:
                continue
        print("[hellowork][apply] Aucun bouton Postuler trouvé")
        return False

    async def fill_form(
        self,
        page,
        lm_texte: str,
        cv_path: str,
        profil: dict = None,
        offer_title: str = "",
        offer_company: str = "",
    ) -> bool:
        try:
            await self._dismiss_cookie_banner(page)
            if cv_path:
                file_input = page.locator("input[type='file']").first
                if await file_input.count() > 0:
                    await file_input.set_input_files(cv_path)
                    await page.wait_for_timeout(1500)

            if lm_texte:
                for sel in (
                    "textarea[name*='message']",
                    "textarea[name*='motivation']",
                    "textarea[id*='message']",
                    "textarea:visible",
                ):
                    area = page.locator(sel).first
                    if await area.count() > 0:
                        await area.fill(lm_texte)
                        break
            return True
        except Exception as e:
            print(f"[hellowork][fill_form] Erreur : {e}")
            return False

    async def submit(self, page) -> bool:
        try:
            for sel in (
                "button[type='submit']:has-text('Postuler')",
                "button[type='submit']:has-text('Envoyer')",
                "button:has-text('Envoyer ma candidature')",
                "button:has-text('Postuler')",
                "button[type='submit']",
            ):
                btn = page.locator(sel).first
                if await btn.count() == 0:
                    continue
                if await btn.is_disabled():
                    continue
                await btn.click()
                await page.wait_for_timeout(4000)
                return True
            return False
        except Exception as e:
            print(f"[hellowork][submit] Erreur : {e}")
            return False
