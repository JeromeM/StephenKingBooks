"""Configuration et constantes du projet."""

import os
from pathlib import Path

# Charge .env en local si disponible (ignoré en production GCF)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_env(key: str, default: str | None = None) -> str:
    """Récupère une variable d'environnement avec validation."""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Variable d'environnement manquante: {key}")
    return value


# API Keys (depuis variables d'environnement)
GEMINI_API_KEY = get_env("GEMINI_API_KEY")
GMAIL_USER = get_env("GMAIL_USER")
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD")

# Configuration Google Sheets
SPREADSHEET_ID = "1oUd2x_kKjE-BjyEOaLf3Gn6I_NSWSYWjJlfnZeHAuWQ"
SERVICE_ACCOUNT_PATH = Path(__file__).parent.parent / "service_account.json"

# Mappage des onglets
TAB_MAPPING = {
    "Romans": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
    "La Tour Sombre": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
    "Série Bill Hodges": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
    "Série Gwendy Peterson": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
    "Richard Bachman": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
    "Recueils de nouvelles": {"col_titre_vo": 2, "col_annee_origine": 3, "col_annee_fr": 4, "col_details": 5},
}

# Constantes
MAX_RETRIES = 3
API_DELAY_SECONDS = 6
