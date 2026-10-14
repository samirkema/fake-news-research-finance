"""Tests purs (sans réseau ni identifiants) de `message_vers_dict`.

On construit les messages en mémoire avec `email.message.EmailMessage` /
`email.message_from_string`, donc ces tests tournent inconditionnellement en CI.
"""

from email.message import EmailMessage
from email import message_from_string

from fakenews.product.extraire_mails import CORPS_MAX, message_vers_dict


def _mail_multipart(sujet: str, expediteur: str, corps_texte: str) -> EmailMessage:
    """Construit un mail multipart (text/plain + text/html) en mémoire."""
    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = expediteur
    msg["Date"] = "Mon, 13 Oct 2025 09:30:00 +0000"
    msg.set_content(corps_texte)
    msg.add_alternative(f"<html><body><p>{corps_texte}</p></body></html>", subtype="html")
    return msg


def test_multipart_text_plain_decode():
    """(a) Un mail multipart avec une partie text/plain donne sujet/expéditeur/corps attendus."""
    msg = _mail_multipart(
        "Idée de fonctionnalité",
        "Visiteur Curieux <visiteur@example.com>",
        "Bonjour, ce serait bien d'ajouter un filtre par source.",
    )

    resultat = message_vers_dict(msg)

    assert resultat["sujet"] == "Idée de fonctionnalité"
    assert resultat["expediteur"] == "Visiteur Curieux <visiteur@example.com>"
    # La partie text/plain est prioritaire sur la variante HTML.
    assert resultat["corps"] == "Bonjour, ce serait bien d'ajouter un filtre par source."
    assert resultat["date"].startswith("2025-10-13T09:30:00")


def test_corps_tronque_a_4000():
    """(b) Un corps de plus de 4000 caractères est tronqué à <= 4000."""
    long_texte = "a" * 5000
    msg = _mail_multipart("Long", "a@example.com", long_texte)

    resultat = message_vers_dict(msg)

    assert len(resultat["corps"]) <= CORPS_MAX
    assert len(resultat["corps"]) == CORPS_MAX


def test_sujet_mime_encode_decode():
    """(c) Un en-tête Subject encodé MIME (=?utf-8?..?=) est décodé."""
    brut = (
        "Subject: =?utf-8?Q?Probl=C3=A8me_de_d=C3=A9tection?=\r\n"
        "From: =?utf-8?Q?Andr=C3=A9?= <andre@example.com>\r\n"
        "Date: Tue, 14 Oct 2025 12:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Un bug a ete detecte.\r\n"
    )
    msg = message_from_string(brut)

    resultat = message_vers_dict(msg)

    assert resultat["sujet"] == "Problème de détection"
    assert resultat["expediteur"] == "André <andre@example.com>"
    assert resultat["corps"] == "Un bug a ete detecte."
