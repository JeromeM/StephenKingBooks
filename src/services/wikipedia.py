"""Service de scraping Wikipedia pour la bibliographie Stephen King."""

import re
import requests
from bs4 import BeautifulSoup


class WikipediaService:
    """Scrape la bibliographie de Stephen King depuis Wikipedia."""

    URL = "https://en.wikipedia.org/wiki/Stephen_King_bibliography"
    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StephenKingBot/1.0)"}

    def fetch_bibliography(self) -> list[dict]:
        """Récupère tous les romans et recueils depuis Wikipedia."""
        print("-> Scraping Wikipedia...")

        try:
            response = requests.get(self.URL, headers=self.HEADERS, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"   [ERREUR] Impossible de récupérer Wikipedia: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        books: list[dict] = []

        # Parser les sections Novels et Collections (pas Nonfiction = essais)
        books.extend(self._parse_section(soup, "Novels"))
        books.extend(self._parse_section(soup, "Collections"))

        print(f"   {len(books)} livres trouvés sur Wikipedia.")
        return books

    def _parse_section(self, soup: BeautifulSoup, section_id: str) -> list[dict]:
        """Parse une section (Novels ou Collections) de la page."""
        books: list[dict] = []

        # Trouver le heading de la section
        heading = soup.find("h2", id=section_id) or soup.find(
            "span", {"id": section_id}
        )
        if not heading:
            # Essayer avec le parent
            heading = soup.find("h2", string=re.compile(section_id, re.IGNORECASE))

        if not heading:
            print(f"   Section '{section_id}' non trouvée.")
            return books

        # Trouver la table suivante
        table = None
        for sibling in heading.find_all_next():
            if sibling.name == "table" and "wikitable" in sibling.get("class", []):
                table = sibling
                break
            if sibling.name == "h2":  # Nouvelle section, arrêter
                break

        if not table:
            print(f"   Table non trouvée pour '{section_id}'.")
            return books

        # Parser les lignes de la table avec gestion du rowspan
        rows = table.find_all("tr")[1:]  # Skip header
        current_year = 0

        for row in rows:
            book = self._parse_row(row, current_year)
            if book:
                current_year = book["Annee_VO"]  # Mémoriser l'année pour rowspan
                book["Source"] = "Wikipedia"
                book["Section"] = section_id
                books.append(book)

        return books

    def _parse_row(self, row, previous_year: int = 0) -> dict | None:
        """Parse une ligne de table pour extraire titre et année."""
        cells = row.find_all(["td", "th"])
        if len(cells) < 1:
            return None

        # Chercher l'année dans la première cellule <td> (pas <th>)
        year = 0
        first_td = row.find("td")
        if first_td:
            year_text = first_td.get_text(strip=True)
            year_match = re.search(r"\d{4}", year_text)
            year = int(year_match.group()) if year_match else 0

        # Si pas d'année trouvée, utiliser l'année précédente (rowspan)
        if year == 0:
            year = previous_year

        # Validation de l'année (doit être entre 1970 et 2030)
        if year < 1970 or year > 2030:
            year = previous_year if 1970 <= previous_year <= 2030 else 0

        # Toujours pas d'année valide ? Ignorer
        if year == 0:
            return None

        # Titre : chercher dans les <th> avec scope="row" (format Wikipedia standard)
        title_cell = row.find("th", {"scope": "row"})
        if not title_cell:
            # Fallback: deuxième colonne
            title_cell = cells[1] if len(cells) > 1 else None

        if not title_cell:
            return None

        # Chercher le lien dans le titre (italique avec lien)
        link = title_cell.find("a")
        italic = title_cell.find("i")

        if italic and italic.find("a"):
            title = italic.find("a").get_text(strip=True)
        elif link:
            title = link.get_text(strip=True)
        elif italic:
            title = italic.get_text(strip=True)
        else:
            title = title_cell.get_text(strip=True)

        # Nettoyer le titre
        title = self._clean_title(title)

        # Validation : ignorer si trop court ou ressemble à un éditeur
        if not title or len(title) < 2:
            return None

        publishers = ["doubleday", "viking", "signet", "scribner", "simon", "putnam"]
        if any(pub in title.lower() for pub in publishers):
            return None

        # Notes : chercher dans les dernières colonnes (structure variable selon les tables)
        notes = ""
        for cell in reversed(cells):
            text = cell.get_text(strip=True)
            # Ignorer les cellules vides ou très courtes (refs, ISBN)
            if len(text) > 15 and not re.match(r"^[\d\-X]+$", text):
                notes = text[:200]
                break

        # Détecter si c'est un livre Richard Bachman
        is_bachman = "bachman" in notes.lower()

        return {
            "Titre_VO": title,
            "Annee_VO": year,
            "Raw_Info": notes,
            "Is_Bachman": is_bachman,
            "Is_Duplicate_or_Ignore": False,
        }

    def _clean_title(self, title: str) -> str:
        """Nettoie un titre (supprime annotations, etc.)."""
        # Supprimer les références [1], [2], etc.
        title = re.sub(r"\[\d+\]", "", title)
        # Supprimer les parenthèses de désambiguïsation
        title = re.sub(r"\s*\(novel\)", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\(novella\)", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\(collection\)", "", title, flags=re.IGNORECASE)
        return title.strip()
