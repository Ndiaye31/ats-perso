"""Applicator pour app.beetween.com.

Flow candidature (SPA Vuetify, pas de login requis) :
  1. Naviguer vers l'offre, attendre le rendu SPA (~8s)
  2. Cliquer "Postuler à cette offre" (scroll vers formulaire inline)
  3. Remplir : Prénom, Nom, Email, Message (LM), upload CV
  4. Cliquer "Postuler" (submit)
"""
from app.automation.base import BaseApplicator


class BeetweenApplicator(BaseApplicator):
    site_url = "https://app.beetween.com"

    async def login(self, page, login: str, password: str) -> bool:
        """Beetween n'a pas de login — no-op, retourne toujours True."""
        return True

    async def navigate_to_offer(self, page, offer_url: str) -> bool:
        """Navigue vers l'offre et attend le rendu SPA."""
        try:
            await page.goto(offer_url, timeout=30000)
            # SPA Vuetify : attendre que le contenu se charge
            await page.wait_for_timeout(8000)
            # Vérifier que la page a bien chargé (pas "Loading...")
            body_text = await page.locator("body").inner_text()
            if "Loading" in body_text and len(body_text) < 50:
                await page.wait_for_timeout(5000)
            return True
        except Exception as e:
            print(f"[beetween][navigate_to_offer] Erreur : {e}")
            return False

    async def find_apply_button(self, page) -> bool:
        """Clique 'Postuler à cette offre' pour scroller vers le formulaire."""
        selectors = [
            "button:has-text('Postuler à cette offre')",
            "a:has-text('Postuler à cette offre')",
            "button:has-text('Postuler')",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        print("[beetween] Aucun bouton Postuler trouvé")
        return False

    async def fill_form(self, page, lm_texte: str, cv_path: str,
                        profil: dict = None, offer_title: str = "", offer_company: str = "") -> bool:
        """Remplit Prénom, Nom, Email, Message et upload CV."""
        try:
            # Les 3 inputs visibles sont dans l'ordre : Prénom, Nom, Email
            visible_inputs = await page.locator("input[type='text']:visible").all()
            if len(visible_inputs) < 3:
                print(f"[beetween] Seulement {len(visible_inputs)} input(s) trouvé(s), 3 attendus")
                return False

            prenom = ""
            nom = ""
            email = ""
            if profil:
                full_name = profil.get("profil", {}).get("nom", "")
                parts = full_name.split(" ", 1) if full_name else []
                prenom = parts[0] if len(parts) >= 1 else ""
                nom = parts[1] if len(parts) >= 2 else ""
                email = profil.get("profil", {}).get("email", "")

            await visible_inputs[0].fill(prenom)
            print(f"[beetween] Prénom rempli : {prenom}")

            await visible_inputs[1].fill(nom)
            print(f"[beetween] Nom rempli : {nom}")

            await visible_inputs[2].fill(email)
            print(f"[beetween] Email rempli : {email}")

            # Message (textarea) — LM
            textarea = page.locator("textarea:visible").first
            if await textarea.count() > 0 and lm_texte:
                await textarea.fill(lm_texte)
                print("[beetween] Message rempli avec la LM")

            # Upload CV (input file hidden)
            if cv_path:
                file_input = page.locator("input[type='file']").first
                if await file_input.count() > 0:
                    await file_input.set_input_files(cv_path)
                    print(f"[beetween] CV uploadé : {cv_path}")

            return True
        except Exception as e:
            print(f"[beetween][fill_form] Erreur : {e}")
            return False

    async def submit(self, page) -> bool:
        """Clique sur le bouton 'Postuler' (submit du formulaire)."""
        try:
            # Le bouton submit est le dernier "Postuler" (pas "Postuler à cette offre")
            submit_btn = page.locator(
                "button:has-text('Postuler'):not(:has-text('cette offre'))"
            ).first
            if await submit_btn.count() == 0:
                # Fallback : dernier bouton Postuler
                all_postuler = page.locator("button:has-text('Postuler')")
                count = await all_postuler.count()
                if count > 0:
                    submit_btn = all_postuler.nth(count - 1)
                else:
                    print("[beetween] Bouton Postuler (submit) non trouvé")
                    return False

            # Vérifier que le bouton n'est pas disabled
            is_disabled = await submit_btn.evaluate(
                "el => el.classList.contains('v-btn--disabled') || el.disabled"
            )
            if is_disabled:
                print("[beetween] Bouton Postuler encore disabled — champs requis manquants ?")
                return False

            await submit_btn.click()
            await page.wait_for_timeout(3000)
            print("[beetween] Formulaire soumis")
            return True
        except Exception as e:
            print(f"[beetween][submit] Erreur : {e}")
            return False
