"""
Script de diagnostic Playwright.
Usage :
    python scripts/explore_form.py emploi-territorial [URL_OFFRE]
    python scripts/explore_form.py fhf [URL_OFFRE]

Se connecte au site, navigue sur l'offre (ou page d'accueil), prend un screenshot
et liste tous les champs de formulaire trouvés.
"""
import asyncio
import sys
from pathlib import Path

# Permet d'importer app.config depuis la racine du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


SITES = {
    "emploi-territorial": {
        "login_url": "https://www.emploi-territorial.fr/login",
        "login": settings.emploi_territorial_login,
        "password": settings.emploi_territorial_password,
        "default_url": "https://www.emploi-territorial.fr",
    },
    "fhf": {
        "login_url": "https://emploi.fhf.fr/login",
        "login": settings.emploi_fhf_login,
        "password": settings.emploi_fhf_password,
        "default_url": "https://emploi.fhf.fr",
    },
}


async def explore(site_key: str, offer_url: str = None):
    from playwright.async_api import async_playwright

    site = SITES[site_key]
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible pour diagnostic
        page = await browser.new_page()

        print(f"\n--- Connexion sur {site['login_url']} ---")
        await page.goto(site["login_url"], wait_until="domcontentloaded", timeout=30000)

        # Champs de login détectés
        inputs = await page.locator("input").all()
        print(f"Champs input trouvés sur la page de login : {len(inputs)}")
        for inp in inputs:
            name = await inp.get_attribute("name") or ""
            itype = await inp.get_attribute("type") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            print(f"  input name='{name}' type='{itype}' placeholder='{placeholder}'")

        # Connexion
        try:
            await page.fill("input[name='email']", site["login"])
            await page.fill("input[name='password']", site["password"])
            await page.click("button[type='submit']")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            print(f"URL après login : {page.url}")
        except Exception as e:
            print(f"Erreur login : {e}")

        screenshot_login = screenshots_dir / f"{site_key}_after_login.png"
        await page.screenshot(path=str(screenshot_login), full_page=True)
        print(f"Screenshot login : {screenshot_login}")

        # Navigation vers l'offre
        target_url = offer_url or site["default_url"]
        print(f"\n--- Navigation vers {target_url} ---")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

        # Cherche bouton Postuler
        apply_selectors = [
            "a.btn-candidature",
            "button:has-text('Postuler')",
            "a:has-text('Postuler')",
            "button:has-text('Candidater')",
            "a:has-text('Candidater')",
        ]
        print("\nRecherche du bouton Postuler :")
        for sel in apply_selectors:
            count = await page.locator(sel).count()
            print(f"  {sel} → {count} trouvé(s)")

        screenshot_offer = screenshots_dir / f"{site_key}_offer.png"
        await page.screenshot(path=str(screenshot_offer), full_page=True)
        print(f"Screenshot offre : {screenshot_offer}")

        # Clic sur Postuler si trouvé
        for sel in apply_selectors:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                print(f"\nClic sur : {sel}")
                await btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                break

        # Inventaire des champs de formulaire
        print("\n--- Champs de formulaire ---")
        for tag in ["input", "textarea", "select"]:
            elements = await page.locator(tag).all()
            print(f"\n{tag} ({len(elements)} trouvé(s)) :")
            for el in elements:
                name = await el.get_attribute("name") or ""
                itype = await el.get_attribute("type") or ""
                placeholder = await el.get_attribute("placeholder") or ""
                label_for = await el.get_attribute("id") or ""
                print(f"  {tag} name='{name}' type='{itype}' placeholder='{placeholder}' id='{label_for}'")

        screenshot_form = screenshots_dir / f"{site_key}_form.png"
        await page.screenshot(path=str(screenshot_form), full_page=True)
        print(f"\nScreenshot formulaire : {screenshot_form}")

        await browser.close()
        print("\nTerminé.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SITES:
        print(f"Usage : python scripts/explore_form.py [{' | '.join(SITES.keys())}] [URL_OFFRE]")
        sys.exit(1)

    site_key = sys.argv[1]
    offer_url = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(explore(site_key, offer_url))


if __name__ == "__main__":
    main()
