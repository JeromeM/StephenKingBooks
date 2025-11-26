"""Service d'envoi d'emails."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict

from ..config import GMAIL_USER, GMAIL_APP_PASSWORD
from ..models import Book


def send_summary(added_books: list[Book], recipient: str | None = None) -> bool:
    """Envoie un email récapitulatif des livres ajoutés."""
    print("-> Envoi de l'email récapitulatif...")

    recipient = recipient or GMAIL_USER

    if added_books:
        subject = f"📚 Agent King : {len(added_books)} nouveau(x) livre(s) ajouté(s)"
        html = _build_html_success(added_books)
    else:
        subject = "📚 Agent King : Aucun nouveau livre"
        html = _build_html_empty()

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, recipient, msg.as_string())
        print("   [OK] Email envoyé.")
        return True
    except Exception as e:
        print(f"   [ERREUR] Envoi email: {e}")
        return False


def _build_html_success(books: list[Book]) -> str:
    """Construit le HTML pour un email avec des livres ajoutés."""
    # Grouper par catégorie
    by_category: dict[str, list[Book]] = defaultdict(list)
    for book in books:
        by_category[book.category].append(book)

    # Construire les sections par catégorie
    sections_html = ""
    for category, cat_books in sorted(by_category.items()):
        rows = ""
        for b in sorted(cat_books, key=lambda x: x.annee_vo):
            rows += f"""
                <tr>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #eee;">{b.titre_vf}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #eee; color: #666; font-style: italic;">{b.titre_vo}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #eee; text-align: center;">{b.annee_vo}</td>
                </tr>"""

        sections_html += f"""
            <div style="margin-bottom: 24px;">
                <h3 style="color: #8B0000; margin: 0 0 12px 0; font-size: 16px; border-bottom: 2px solid #8B0000; padding-bottom: 4px;">
                    {category} ({len(cat_books)})
                </h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 8px 12px; text-align: left;">Titre FR</th>
                            <th style="padding: 8px 12px; text-align: left;">Titre VO</th>
                            <th style="padding: 8px 12px; text-align: center;">Année</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #8B0000; margin: 0; font-size: 24px;">📚 Agent King</h1>
            <p style="color: #666; margin: 8px 0 0 0;">Bibliographie Stephen King</p>
        </div>

        <div style="background: #f0fff0; border-left: 4px solid #228B22; padding: 12px 16px; margin-bottom: 24px;">
            <strong style="color: #228B22;">{len(books)} livre(s) ajouté(s)</strong>
        </div>

        {sections_html}

        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 12px; color: #999; text-align: center;">
            Les onglets ont été triés chronologiquement.<br>
            <em>Agent King - Mise à jour automatique</em>
        </div>
    </body>
    </html>"""


def _build_html_empty() -> str:
    """Construit le HTML pour un email sans nouveaux livres."""
    return """
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #8B0000; margin: 0; font-size: 24px;">📚 Agent King</h1>
            <p style="color: #666; margin: 8px 0 0 0;">Bibliographie Stephen King</p>
        </div>

        <div style="background: #f5f5f5; border-left: 4px solid #999; padding: 12px 16px; text-align: center;">
            <p style="margin: 0; color: #666;">Aucun nouveau livre identifié.</p>
            <p style="margin: 8px 0 0 0; font-size: 14px; color: #999;">La bibliographie est à jour.</p>
        </div>

        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 12px; color: #999; text-align: center;">
            <em>Agent King - Mise à jour automatique</em>
        </div>
    </body>
    </html>"""
