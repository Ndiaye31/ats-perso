from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str = ""

    emploi_territorial_login: str = ""
    emploi_territorial_password: str = ""
    emploi_fhf_login: str = ""
    emploi_fhf_password: str = ""
    cv_path: str = ""
    diplome_path: str = ""
    auto_apply_step_retries: int = 2
    auto_apply_retry_delay_s: float = 1.0

    smtp_email: str = ""       # adresse Gmail expéditrice
    smtp_password: str = ""    # conservé pour fallback SMTP si réseau le permet

    # France Travail API
    ft_client_id: str = ""
    ft_client_secret: str = ""

    # Hunter.io
    hunter_api_key: str = ""

    # Gmail API OAuth2 (fonctionne sur tous les réseaux)
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""

    scheduler_enabled: bool = False
    scheduler_scrape_interval_s: int = 3600
    scheduler_scrape_weekdays_only: bool = True
    scheduler_scrape_hour: int = 8
    scheduler_scrape_minute: int = 0
    scheduler_timezone: str = "Europe/Paris"
    scheduler_rescore_interval_s: int = 3600
    scheduler_batch_enabled: bool = False
    scheduler_batch_interval_s: int = 7200
    scheduler_batch_limit: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def validate_startup_config() -> None:
    """Valide la configuration critique au démarrage de l'API."""
    errors: list[str] = []
    in_docker = Path("/.dockerenv").exists()

    if not settings.database_url.strip():
        errors.append("DATABASE_URL est requis et ne peut pas être vide.")

    for env_name, path_value in (
        ("CV_PATH", settings.cv_path),
        ("DIPLOME_PATH", settings.diplome_path),
    ):
        if not path_value:
            continue
        # Les chemins /app/... sont résolus dans le conteneur Docker.
        if not in_docker and path_value.startswith("/app/"):
            continue
        if not Path(path_value).exists():
            errors.append(
                f"{env_name} pointe vers un chemin introuvable: '{path_value}'."
            )

    if errors:
        raise RuntimeError("Configuration invalide au démarrage: " + " ".join(errors))
