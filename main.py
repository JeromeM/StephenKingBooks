"""Agent King - Gestion automatique de la bibliographie Stephen King."""

import re
import time

from src.config import API_DELAY_SECONDS
from src.models import Book
from src.services import (
    GeminiService,
    SheetsService,
    WikipediaService,
    BookMerger,
    send_summary,
)


def normalize_title(title: str) -> str:
    """Normalise un titre pour comparaison."""
    title = title.lower().strip()
    # Supprimer les préfixes de série (La Tour Sombre I:, Dark Tower V:, etc.)
    title = re.sub(r"^(the\s+)?dark\s+tower\s*[ivxlc0-9]*\s*:\s*", "", title)
    title = re.sub(r"^la\s+tour\s+sombre\s*[ivxlc0-9]*\s*:\s*", "", title)
    title = re.sub(r"^gwendy[''s]*\s*", "", title)  # Gwendy's Button Box -> Button Box
    # Supprimer les articles
    title = re.sub(r"^(the|a|an|le|la|les|l'|un|une)\s+", "", title)
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calcule la distance de Levenshtein entre deux chaînes."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def is_similar_title(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Vérifie si deux titres sont similaires (détecte les typos)."""
    if not title1 or not title2:
        return False
    if title1 == title2:
        return True
    # Ignorer les titres trop courts (risque de faux positifs)
    if len(title1) < 5 or len(title2) < 5:
        return False
    # Distance de Levenshtein
    distance = levenshtein_distance(title1, title2)
    max_len = max(len(title1), len(title2))
    ratio = 1 - (distance / max_len)
    return ratio >= threshold


def main() -> None:
    """Point d'entrée principal."""
    print("=== AGENT KING (Hybride) ===\n")

    # Initialisation des services
    sheets = SheetsService()
    wikipedia = WikipediaService()
    gemini = GeminiService()
    merger = BookMerger()

    # 1. Récupération des titres existants
    existing_titles = sheets.get_existing_titles()
    existing_normalized = {normalize_title(t) for t in existing_titles}

    # 2. Collecte depuis plusieurs sources
    print("\n--- COLLECTE DES SOURCES ---")
    wiki_books = wikipedia.fetch_bibliography()
    gemini_books = gemini.fetch_bibliography(existing_titles)

    # 3. Fusion et déduplication
    print("\n--- FUSION ---")
    all_books = merger.merge(wiki_books, gemini_books, existing_titles=existing_titles)

    if not all_books:
        print("Aucun nouveau livre trouvé. Arrêt.")
        send_summary([])
        return

    print(f"\n--- TRAITEMENT DE {len(all_books)} LIVRE(S) ---")
    added_books: list[Book] = []

    # 4. Catégorisation et ajout de chaque livre
    for raw_book in all_books:
        print(f"\n-> {raw_book['Titre_VO']} ({raw_book.get('Annee_VO', '?')})")

        # Analyse détaillée via Gemini (traduction, catégorisation)
        analysis = gemini.categorize_book(raw_book, existing_titles)
        if not analysis:
            print("   [SKIP] Analyse échouée.")
            continue

        # Vérification finale anti-doublon par Gemini
        if analysis.get("Is_Duplicate_or_Ignore", True):
            print("   [SKIP] Doublon détecté par Gemini.")
            continue

        # Filtrer les livres non traduits en français
        annee_fr = analysis.get("Annee_FR", 0)
        if not annee_fr or annee_fr == 0:
            print("   [SKIP] Non traduit en français.")
            continue

        # Vérification programmatique du titre FR (plus fiable que l'IA)
        titre_vf = analysis.get("Titre_VF", "")
        titre_vf_normalized = normalize_title(titre_vf)

        # Check exact match
        if titre_vf_normalized in existing_normalized:
            print(f"   [SKIP] Titre FR '{titre_vf}' déjà existant.")
            continue

        # Check fuzzy match (typos comme "La Clar des vents" vs "La Clé des vents")
        is_duplicate = False
        for existing in existing_normalized:
            if is_similar_title(titre_vf_normalized, existing):
                print(f"   [SKIP] Titre FR '{titre_vf}' similaire à un existant.")
                is_duplicate = True
                break
        if is_duplicate:
            continue

        # Création et ajout du livre
        book = Book.from_raw(raw_book)
        book.update_from_analysis(analysis)

        if sheets.add_book(book):
            added_books.append(book)
            # Ajouter aux titres existants pour éviter les doublons suivants
            existing_titles.add(book.titre_vo)
            existing_titles.add(book.titre_vf)
            existing_normalized.add(normalize_title(book.titre_vo))
            existing_normalized.add(normalize_title(book.titre_vf))

        time.sleep(API_DELAY_SECONDS)

    # 5. Complétion des lignes incomplètes
    print("\n--- COMPLÉTION DES INFOS MANQUANTES ---")
    incomplete_rows = sheets.get_incomplete_rows()
    completed_count = 0

    for row_data in incomplete_rows:
        completion = gemini.complete_book_info(row_data)
        if completion:
            # Ne mettre à jour que les champs manquants
            updates = {}
            if "Titre_VF" in row_data["missing"] and completion.get("Titre_VF"):
                updates["Titre_VF"] = completion["Titre_VF"]
            if "Annee_VO" in row_data["missing"] and completion.get("Annee_VO"):
                updates["Annee_VO"] = completion["Annee_VO"]
            if "Annee_VF" in row_data["missing"] and completion.get("Annee_VF"):
                updates["Annee_VF"] = completion["Annee_VF"]
            if not row_data.get("Details") and completion.get("Details"):
                updates["Details"] = completion["Details"]

            if updates and sheets.update_row(row_data["tab"], row_data["row"], updates):
                print(f"   [OK] {row_data['Titre_VO']} complété.")
                completed_count += 1

        time.sleep(API_DELAY_SECONDS)

    # 6. Tri et notification
    print("\n--- FINALISATION ---")
    sheets.sort_all_sheets()
    send_summary(added_books)

    print(f"\n=== TERMINÉ : {len(added_books)} ajouté(s), {completed_count} complété(s) ===")


def run(request) -> str:
    """Point d'entrée pour Google Cloud Functions."""
    main()
    return "OK"


if __name__ == "__main__":
    main()
