"""Charge et expose le profil utilisateur depuis config/profil.yml."""
from pathlib import Path
from typing import Any

import yaml

_PROFIL_PATH = Path(__file__).resolve().parents[1] / "config" / "profil.yml"


def load_profil() -> dict[str, Any]:
    with open(_PROFIL_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("profil", {})


# Instance chargée une seule fois au démarrage
profil = load_profil()
