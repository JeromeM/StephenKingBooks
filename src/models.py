"""Modèles de données."""

from dataclasses import dataclass


@dataclass
class Book:
    """Représente un livre de Stephen King."""

    titre_vo: str
    annee_vo: int
    titre_vf: str = ""
    annee_vf: int = 0
    details: str = ""
    category: str = "Romans"
    raw_info: str = ""

    def to_row(self) -> list:
        """Convertit le livre en ligne pour Google Sheets."""
        return [
            self.titre_vf,
            self.titre_vo,
            self.annee_vo,
            self.annee_vf,
        ]

    @classmethod
    def from_raw(cls, data: dict) -> "Book":
        """Crée un Book depuis les données brutes de l'API."""
        return cls(
            titre_vo=data.get("Titre_VO", ""),
            annee_vo=data.get("Annee_VO", 0),
            raw_info=data.get("Raw_Info", ""),
        )

    def update_from_analysis(self, analysis: dict) -> None:
        """Met à jour le livre avec les données d'analyse IA."""
        self.titre_vf = analysis.get("Titre_VF", "")
        self.annee_vf = analysis.get("Annee_FR", 0)
        self.details = analysis.get("Details", "")
        self.category = analysis.get("Category", "Romans")
