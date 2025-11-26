"""Service d'interaction avec Google Sheets."""

import gspread

from ..config import SPREADSHEET_ID, SERVICE_ACCOUNT_PATH, TAB_MAPPING
from ..models import Book


class SheetsService:
    """Encapsule les opérations Google Sheets."""

    def __init__(self):
        self.client = gspread.service_account(filename=str(SERVICE_ACCOUNT_PATH))
        self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)

    def get_existing_titles(self) -> set[str]:
        """Récupère tous les titres existants (VF et VO) de tous les onglets."""
        print("-> Indexation des titres existants...")
        titles: set[str] = set()

        for tab_name in TAB_MAPPING:
            try:
                sheet = self.spreadsheet.worksheet(tab_name)
                titles_vf = sheet.col_values(1)[1:]  # Col 1, skip header
                titles_vo = sheet.col_values(2)[1:]  # Col 2, skip header

                titles.update(t.strip() for t in titles_vf if t.strip())
                titles.update(t.strip() for t in titles_vo if t.strip())

            except gspread.WorksheetNotFound:
                print(f"   Onglet '{tab_name}' non trouvé, ignoré.")
            except Exception as e:
                print(f"   Erreur lecture '{tab_name}': {e}")

        print(f"   {len(titles)} titres indexés.")
        return titles

    def add_book(self, book: Book) -> bool:
        """Ajoute un livre dans l'onglet approprié."""
        if book.category not in TAB_MAPPING:
            print(f"   [ERREUR] Catégorie '{book.category}' non reconnue.")
            return False

        try:
            sheet = self.spreadsheet.worksheet(book.category)
            sheet.append_rows([book.to_row()], value_input_option="USER_ENTERED")
            print(f"   [OK] {book.titre_vf} ({book.titre_vo}) -> {book.category}")
            return True
        except Exception as e:
            print(f"   [ERREUR] Écriture '{book.category}': {e}")
            return False

    def get_incomplete_rows(self) -> list[dict]:
        """Récupère les lignes avec des infos manquantes (année ou titre)."""
        print("-> Recherche des lignes incomplètes...")
        incomplete: list[dict] = []

        for tab_name in TAB_MAPPING:
            try:
                sheet = self.spreadsheet.worksheet(tab_name)
                rows = sheet.get_all_values()

                for row_idx, row in enumerate(rows[1:], start=2):  # Skip header
                    if len(row) < 5:
                        row.extend([""] * (5 - len(row)))

                    titre_vf, titre_vo, annee_vo, annee_vf, details = row[:5]

                    # Vérifier s'il manque des infos importantes
                    missing = []
                    if not titre_vf.strip():
                        missing.append("Titre_VF")
                    if not annee_vo.strip() or annee_vo.strip() == "0":
                        missing.append("Annee_VO")
                    if not annee_vf.strip() or annee_vf.strip() == "0":
                        missing.append("Annee_VF")

                    if missing and titre_vo.strip():  # On a besoin du titre VO
                        incomplete.append({
                            "tab": tab_name,
                            "row": row_idx,
                            "Titre_VO": titre_vo.strip(),
                            "Titre_VF": titre_vf.strip(),
                            "Annee_VO": annee_vo.strip(),
                            "Annee_VF": annee_vf.strip(),
                            "Details": details.strip(),
                            "missing": missing,
                        })

            except Exception as e:
                print(f"   [ERREUR] Lecture '{tab_name}': {e}")

        print(f"   {len(incomplete)} ligne(s) incomplète(s) trouvée(s).")
        return incomplete

    def update_row(self, tab_name: str, row_idx: int, data: dict) -> bool:
        """Met à jour une ligne avec les nouvelles données."""
        try:
            sheet = self.spreadsheet.worksheet(tab_name)

            updates = []
            if data.get("Titre_VF"):
                updates.append({"range": f"A{row_idx}", "values": [[data["Titre_VF"]]]})
            if data.get("Annee_VO"):
                updates.append({"range": f"C{row_idx}", "values": [[data["Annee_VO"]]]})
            if data.get("Annee_VF"):
                updates.append({"range": f"D{row_idx}", "values": [[data["Annee_VF"]]]})
            if data.get("Details") and not sheet.cell(row_idx, 5).value:
                updates.append({"range": f"E{row_idx}", "values": [[data["Details"]]]})

            if updates:
                sheet.batch_update(updates, value_input_option="USER_ENTERED")
                return True
            return False

        except Exception as e:
            print(f"   [ERREUR] Mise à jour ligne {row_idx}: {e}")
            return False

    def sort_all_sheets(self) -> None:
        """Trie tous les onglets par année (préserve le formatage)."""
        print("\n-> Tri des onglets...")

        for tab_name in TAB_MAPPING:
            try:
                sheet = self.spreadsheet.worksheet(tab_name)
                last_row = len(sheet.get_all_values())

                if last_row <= 1:
                    continue

                sort_request = {
                    "sortRange": {
                        "range": {
                            "sheetId": sheet.id,
                            "startRowIndex": 1,
                            "endRowIndex": last_row,
                        },
                        "sortSpecs": [
                            {"dimensionIndex": 2, "sortOrder": "ASCENDING"},
                            {"dimensionIndex": 3, "sortOrder": "ASCENDING"},
                        ],
                    }
                }

                self.spreadsheet.batch_update({"requests": [sort_request]})
                print(f"   [OK] '{tab_name}' trié.")

            except Exception as e:
                print(f"   [ERREUR] Tri '{tab_name}': {e}")
