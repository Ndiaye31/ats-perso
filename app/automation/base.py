"""BaseApplicator : classe abstraite pour automatiser les candidatures Playwright."""
from abc import ABC, abstractmethod
from pathlib import Path


class BaseApplicator(ABC):
    site_url: str = ""
    login_url: str = ""

    async def login(self, page, login: str, password: str) -> bool:
        """Connexion au site. Retourne True si réussie."""
        try:
            await page.goto(self.login_url, wait_until="domcontentloaded", timeout=30000)
            await page.fill("input[name='email']", login)
            await page.fill("input[name='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            return True
        except Exception as e:
            print(f"[login] Erreur : {e}")
            return False

    async def navigate_to_offer(self, page, offer_url: str) -> bool:
        """Navigue vers la page de l'offre."""
        try:
            await page.goto(offer_url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            print(f"[navigate_to_offer] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Cherche et clique sur le bouton Postuler / Candidater."""
        selectors = [
            "a.btn-candidature",
            "button:has-text('Postuler')",
            "a:has-text('Postuler')",
            "button:has-text('Candidater')",
            "a:has-text('Candidater')",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
            except Exception:
                continue
        print("[find_apply_button] Aucun bouton Postuler trouvé")
        return False

    async def screenshot(self, page, path: str) -> None:
        """Prend un screenshot de la page courante."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=path, full_page=True)
        print(f"[screenshot] Sauvegardé : {path}")

    @abstractmethod
    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil: dict = None, offer_title: str = "",
                        offer_company: str = "") -> bool:
        """Remplit le formulaire de candidature (CV + LM)."""

    @abstractmethod
    async def submit(self, page) -> bool:
        """Soumet le formulaire de candidature."""
