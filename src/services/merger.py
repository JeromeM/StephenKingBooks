"""Service de fusion et déduplication des sources de livres."""

import re
from typing import Any


class BookMerger:
    """Fusionne les livres de plusieurs sources et déduplique."""

    def merge(
        self,
        *sources: list[dict[str, Any]],
        existing_titles: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fusionne plusieurs listes de livres et déduplique.

        Args:
            *sources: Listes de livres à fusionner
            existing_titles: Titres déjà en base (pour filtrage)

        Returns:
            Liste de livres uniques, non présents dans existing_titles
        """
        existing_titles = existing_titles or set()
        existing_normalized = {self._normalize(t) for t in existing_titles}

        all_books: dict[str, dict] = {}

        for source in sources:
            for book in source:
                title = book.get("Titre_VO", "")
                if not title:
                    continue

                key = self._normalize(title)

                # Ignorer si déjà en base
                if self._is_existing(key, existing_normalized):
                    continue

                # Ajouter ou mettre à jour
                if key not in all_books:
                    all_books[key] = book
                else:
                    # Fusionner les infos (garder le plus complet)
                    self._merge_book_data(all_books[key], book)

        result = list(all_books.values())
        print(f"-> Merge: {len(result)} livres uniques après fusion.")
        return result

    def _normalize(self, title: str) -> str:
        """Normalise un titre pour comparaison."""
        title = title.lower().strip()
        # Supprimer articles
        title = re.sub(r"^(the|a|an)\s+", "", title)
        # Supprimer ponctuation
        title = re.sub(r"[^\w\s]", "", title)
        # Normaliser espaces
        title = re.sub(r"\s+", " ", title)
        return title.strip()

    def _is_existing(self, normalized_key: str, existing_normalized: set[str]) -> bool:
        """Vérifie si un titre existe déjà (avec variantes)."""
        if normalized_key in existing_normalized:
            return True

        # Nettoyer les suffixes d'édition courants
        base_title = self._extract_base_title(normalized_key)

        # Vérifier si le titre de base existe
        if base_title != normalized_key and base_title in existing_normalized:
            return True

        # Vérifier si un titre existant contient le titre de base
        for existing in existing_normalized:
            existing_base = self._extract_base_title(existing)
            if base_title == existing_base and len(base_title) > 3:
                return True

        return False

    def _extract_base_title(self, title: str) -> str:
        """Extrait le titre de base sans les variantes d'édition."""
        # Supprimer les variantes d'édition courantes (après normalisation, donc sans ponctuation)
        patterns = [
            r"\s+the\s+complete.*$",  # "the complete uncut edition"
            r"\s+complete\s*(and\s*)?uncut.*$",
            r"\s+uncut\s*edition.*$",
            r"\s+expanded\s*edition.*$",
            r"\s+special\s*edition.*$",
            r"\s+illustrated\s*edition.*$",
            r"\s+directors\s*cut.*$",
            r"\s+\d{4}\s*edition.*$",  # ex: "2020 edition"
        ]
        result = title
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        return result.strip()

    def _merge_book_data(self, existing: dict, new: dict) -> None:
        """Fusionne les données d'un livre (complète les champs vides)."""
        for key, value in new.items():
            if key not in existing or not existing[key]:
                existing[key] = value
            elif key == "Raw_Info" and value and len(value) > len(existing.get(key, "")):
                existing[key] = value
