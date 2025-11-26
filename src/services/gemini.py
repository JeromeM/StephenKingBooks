"""Service d'interaction avec l'API Gemini."""

import json
import time
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

from ..config import GEMINI_API_KEY, TAB_MAPPING, MAX_RETRIES


class GeminiService:
    """Encapsule les appels à l'API Gemini."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def _call_with_retry(self, prompt: str, schema: types.Schema) -> dict | list | None:
        """Appelle l'API avec retry en cas d'erreur temporaire."""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                return json.loads(response.text)

            except APIError as e:
                if "503" in str(e) or "429" in str(e):
                    delay = 2**attempt
                    print(f"   Erreur API ({e}). Retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(delay)
                else:
                    print(f"   Erreur API non retentable: {e}")
                    return None
            except Exception as e:
                print(f"   Erreur inattendue: {e}")
                return None

        print(f"   Échec après {MAX_RETRIES} tentatives.")
        return None

    def fetch_bibliography(self, existing_titles: set[str]) -> list[dict[str, Any]]:
        """Recherche et structure la bibliographie de Stephen King."""
        print("-> Recherche de la bibliographie via Gemini...")

        schema = types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "Titre_VO": types.Schema(type=types.Type.STRING),
                    "Annee_VO": types.Schema(type=types.Type.INTEGER),
                    "Raw_Info": types.Schema(type=types.Type.STRING),
                    "Is_Duplicate_or_Ignore": types.Schema(type=types.Type.BOOLEAN),
                },
                required=["Titre_VO", "Annee_VO", "Raw_Info", "Is_Duplicate_or_Ignore"],
            ),
        )

        prompt = f"""
        Tu es un expert de Stephen King. Recherche sur les SITES DE FANS pour trouver des œuvres.

        SOURCES À CONSULTER (sites de fans Stephen King) :
        - stephenking.com (site officiel)
        - Club Stephen King (fansite français)
        - StephenKingFR
        - Goodreads reviews et listes de fans

        FOCUS : Cherche des œuvres qui pourraient manquer sur Wikipedia :
        - Novellas récentes ou moins connues
        - Collaborations avec d'autres auteurs
        - Livres publiés récemment (2022-2025)
        - Éditions limitées ou spéciales

        ŒUVRES À IGNORER :
        - Essais et non-fiction
        - Nouvelles individuelles (seulement les recueils)
        - Bandes dessinées/comics
        - Adaptations (films, séries)

        Titres DÉJÀ CONNUS (ne pas inclure) :
        {', '.join(list(existing_titles)[:50])}...

        Pour chaque livre trouvé, Is_Duplicate_or_Ignore = TRUE si déjà dans la liste.

        Retourne un tableau JSON avec les livres trouvés sur ces sites de fans.
        """

        result = self._call_with_retry(prompt, schema)
        if result:
            print(f"   {len(result)} titres trouvés.")
        return result or []

    def categorize_book(self, book_data: dict, existing_titles: set[str]) -> dict | None:
        """Analyse un livre pour traduction, catégorisation et détails."""
        print(f"-> Analyse: '{book_data['Titre_VO']}'...")

        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "Titre_VF": types.Schema(type=types.Type.STRING),
                "Annee_FR": types.Schema(type=types.Type.INTEGER),
                "Details": types.Schema(type=types.Type.STRING),
                "Category": types.Schema(type=types.Type.STRING, enum=list(TAB_MAPPING.keys())),
                "Is_Duplicate_or_Ignore": types.Schema(type=types.Type.BOOLEAN),
            },
            required=["Titre_VF", "Annee_FR", "Details", "Category", "Is_Duplicate_or_Ignore"],
        )

        prompt = f"""
        Analyse ce livre de Stephen King pour catalogage :

        LIVRE À ANALYSER :
        - Titre VO : "{book_data['Titre_VO']}"
        - Année VO : {book_data['Annee_VO']}
        - Info : "{book_data.get('Raw_Info', '')}"

        TÂCHES :
        1. Trouver le titre français officiel (Titre_VF)
        2. Trouver l'année de première publication en France (Annee_FR, 0 si inconnu ou pas traduit)
        3. Écrire un résumé court (20 mots max)
        4. Classer dans la bonne catégorie

        CATÉGORIES (choisir UNE) :
        - "Romans" : romans solo standard
        - "La Tour Sombre" : série Dark Tower (The Gunslinger, Drawing of the Three, etc.)
        - "Série Bill Hodges" : Mr Mercedes, Finders Keepers, End of Watch, The Outsider, If It Bleeds
        - "Série Gwendy Peterson" : Gwendy's Button Box, Gwendy's Magic Feather, Gwendy's Final Task
        - "Richard Bachman" : publiés sous ce pseudonyme (Rage, The Long Walk, Roadwork, Running Man, Thinner, Blaze, etc.)
        - "Recueils de nouvelles" : collections de nouvelles (Night Shift, Skeleton Crew, etc.)

        DÉTECTION DOUBLON - Is_Duplicate_or_Ignore = TRUE si :
        - Le TITRE FRANÇAIS que tu vas traduire existe DÉJÀ dans la liste ci-dessous
        - Exemple : "The Stand: Complete & Uncut" → "Le Fléau" → Si "Le Fléau" existe → DOUBLON
        - C'est une réédition, édition illustrée, director's cut, version longue
        - Le livre n'a JAMAIS été traduit en français (Annee_FR = 0)

        TITRES DÉJÀ EN BASE (VO et VF mélangés) :
        {', '.join(existing_titles)}

        IMPORTANT : Vérifie bien que le titre FR n'existe pas déjà avant de dire Is_Duplicate_or_Ignore = false !

        Retourne le JSON.
        """

        result = self._call_with_retry(prompt, schema)
        if result:
            result.update(book_data)
        return result

    def complete_book_info(self, book_data: dict) -> dict | None:
        """Complète les informations manquantes d'un livre."""
        missing = book_data.get("missing", [])
        if not missing:
            return None

        print(f"-> Complétion: '{book_data['Titre_VO']}' (manque: {', '.join(missing)})...")

        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "Titre_VF": types.Schema(type=types.Type.STRING),
                "Annee_VO": types.Schema(type=types.Type.INTEGER),
                "Annee_VF": types.Schema(type=types.Type.INTEGER),
                "Details": types.Schema(type=types.Type.STRING),
            },
            required=["Titre_VF", "Annee_VO", "Annee_VF", "Details"],
        )

        prompt = f"""
        Complète les informations manquantes pour ce livre de Stephen King :

        LIVRE :
        - Titre VO : "{book_data['Titre_VO']}"
        - Titre VF actuel : "{book_data.get('Titre_VF', '')}"
        - Année VO actuelle : {book_data.get('Annee_VO', 0)}
        - Année VF actuelle : {book_data.get('Annee_VF', 0)}

        INFOS MANQUANTES À TROUVER : {', '.join(missing)}

        RÈGLES :
        - Titre_VF : titre français officiel (pas de traduction littérale)
        - Annee_VO : année de première publication en anglais
        - Annee_VF : année de première publication en français (0 si jamais traduit)
        - Details : résumé très court (15 mots max)

        Retourne TOUTES les infos, même celles déjà connues.
        """

        return self._call_with_retry(prompt, schema)
