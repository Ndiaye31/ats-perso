import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


def _request(session: requests.Session, method: str, url: str, **kwargs) -> tuple[bool, Any, str]:
    try:
        timeout = kwargs.pop("timeout", 45)
        resp = session.request(method, url, timeout=timeout, **kwargs)
        if resp.status_code >= 400:
            return False, None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        if resp.status_code == 204:
            return True, None, "No content"
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return True, resp.json(), "OK"
        return True, resp.text, "OK"
    except Exception as e:
        return False, None, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validation bout-en-bout mon-ATS (health -> scrape -> candidature -> LM -> auto-apply dry-run -> email test)."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL API FastAPI")
    parser.add_argument(
        "--run-email-test",
        action="store_true",
        help="Exécute l'étape d'envoi email réel (sinon SKIP)",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    session = requests.Session()

    results: list[StepResult] = []
    created_candidature_id: str | None = None
    dry_run_screenshot: str | None = None

    # 1) health
    ok, data, detail = _request(session, "GET", f"{base}/health")
    if ok and isinstance(data, dict) and data.get("status") == "ok":
        results.append(StepResult("health", True, "API healthy"))
    else:
        results.append(StepResult("health", False, detail or "health KO"))

    # 2) scrape
    ok, data, detail = _request(session, "POST", f"{base}/offres/scrape", timeout=180)
    if ok and isinstance(data, dict):
        inserted_total = 0
        for source_data in data.values():
            if isinstance(source_data, dict):
                inserted_total += int(source_data.get("inserted", 0))
        results.append(StepResult("scrape", True, f"Scrape OK, inserted={inserted_total}"))
    else:
        results.append(StepResult("scrape", False, detail or "scrape KO"))

    # 3) get one offer
    ok, data, detail = _request(session, "GET", f"{base}/offers/table?limit=25&offset=0")
    offer_id: str | None = None
    if ok and isinstance(data, dict) and isinstance(data.get("items"), list):
        items = data["items"]
        candidate = next(
            (
                o for o in items
                if o.get("id")
                and o.get("url")
                and not o.get("candidature_url")
                and (
                    "emploi-territorial.fr" in str(o.get("url", ""))
                    or "fhf.fr" in str(o.get("url", ""))
                )
            ),
            None,
        )
        if not candidate:
            candidate = next((o for o in items if o.get("id") and o.get("url")), None)
        if not candidate and items:
            candidate = items[0]
        if candidate:
            offer_id = str(candidate["id"])
            results.append(StepResult("pick_offer", True, f"Offer selected: {offer_id}"))
        else:
            results.append(StepResult("pick_offer", False, "Aucune offre disponible"))
    else:
        results.append(StepResult("pick_offer", False, detail or "impossible de charger les offres"))

    # 4) create candidature
    if offer_id:
        ok, data, detail = _request(
            session,
            "POST",
            f"{base}/candidatures",
            json={"offer_id": offer_id},
        )
        if ok and isinstance(data, dict) and data.get("id"):
            created_candidature_id = str(data["id"])
            results.append(StepResult("create_candidature", True, f"Candidature: {created_candidature_id}"))
        else:
            results.append(StepResult("create_candidature", False, detail or "KO création candidature"))

    # 5) generate LM
    if created_candidature_id:
        ok, data, detail = _request(
            session,
            "POST",
            f"{base}/candidatures/{created_candidature_id}/generate-lm",
        )
        if ok and isinstance(data, dict) and isinstance(data.get("lm_texte"), str):
            lm_len = len(data["lm_texte"])
            results.append(StepResult("generate_lm", True, f"LM générée ({lm_len} chars)"))
        else:
            results.append(StepResult("generate_lm", False, detail or "KO génération LM"))

    # 6) auto-apply dry-run
    if created_candidature_id:
        ok, data, detail = _request(
            session,
            "POST",
            f"{base}/candidatures/{created_candidature_id}/auto-apply?dry_run=true",
        )
        if ok and isinstance(data, dict):
            success = bool(data.get("success"))
            dry_run_screenshot = data.get("screenshot_path")
            if success:
                msg = str(data.get("message", "Dry-run OK"))
                if dry_run_screenshot:
                    msg += f" | screenshot={dry_run_screenshot}"
                results.append(StepResult("auto_apply_dry_run", True, msg))
            else:
                results.append(StepResult("auto_apply_dry_run", False, str(data.get("message", "Dry-run KO"))))
        else:
            results.append(StepResult("auto_apply_dry_run", False, detail or "KO auto-apply dry-run"))

    # 7) email test
    if created_candidature_id:
        if args.run_email_test:
            ok, data, detail = _request(
                session,
                "POST",
                f"{base}/candidatures/{created_candidature_id}/send-email",
            )
            if ok and isinstance(data, dict) and data.get("success"):
                results.append(StepResult("send_email_test", True, str(data.get("message", "Email OK"))))
            else:
                results.append(StepResult("send_email_test", False, detail or "KO envoi email"))
        else:
            results.append(StepResult("send_email_test", False, "SKIP (utiliser --run-email-test pour l'exécuter)"))

    # Capture copy if available
    copied_capture: str | None = None
    if dry_run_screenshot:
        src = Path(dry_run_screenshot)
        if src.exists() and src.is_file():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst_dir = Path("scripts") / "screenshots"
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / f"validation_dry_run_{stamp}{src.suffix or '.png'}"
            shutil.copy2(src, dst)
            copied_capture = str(dst)

    ok_count = sum(1 for r in results if r.ok)
    ko_count = len(results) - ok_count

    print("\n=== VALIDATION PIPELINE mon-ATS ===")
    print(f"Base URL: {base}")
    print(f"Résultat global: {'OK' if ko_count == 0 else 'KO'}")
    print(f"Étapes OK: {ok_count} | Étapes KO/SKIP: {ko_count}\n")

    for r in results:
        status = "OK" if r.ok else "KO"
        print(f"[{status}] {r.name}: {r.detail}")

    if copied_capture:
        print(f"\nCapture copiée dans: {copied_capture}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "base_url": base,
        "global_ok": ko_count == 0,
        "ok_count": ok_count,
        "ko_count": ko_count,
        "steps": [r.__dict__ for r in results],
        "copied_capture": copied_capture,
    }
    report_path = Path("scripts") / "screenshots" / "validation_last_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rapport: {report_path}")

    return 0 if ko_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
