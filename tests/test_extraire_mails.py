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


# --- Audit phase 24 : F24-03 (fenêtre) et F24-04 (un mail ne masque pas la boîte) ---

import email.utils
import json
from datetime import datetime, timedelta, timezone

from fakenews.product import extraire_mails


def _brut(sujet: str, charset: str = "utf-8", il_y_a: timedelta = timedelta(hours=1)) -> bytes:
    date = email.utils.format_datetime(datetime.now(timezone.utc) - il_y_a)
    return (
        f"Subject: {sujet}\r\nFrom: v@example.com\r\nDate: {date}\r\n"
        f"Content-Type: text/plain; charset={charset}\r\n\r\ncorps {sujet}\r\n"
    ).encode()


class _ImapFactice:
    """Double d'`imaplib.IMAP4_SSL` : SEARCH renvoie tous les messages, FETCH les
    sert dans l'ordre. `readonly` est mémorisé pour vérifier la lecture seule."""

    def __init__(self, messages):
        self.messages = messages
        self.readonly = None

    def __call__(self, hote):
        return self

    def login(self, adresse, mot_de_passe):
        pass

    def select(self, boite, readonly=False):
        self.readonly = readonly

    def search(self, charset, *critere):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.messages)))]

    def fetch(self, identifiant, quoi):
        return "OK", [(b"", self.messages[int(identifiant) - 1])]

    def logout(self):
        pass


def test_charset_inconnu_decode_en_utf8():
    msg = message_from_string(_brut("x", charset="x-inconnu").decode())
    assert message_vers_dict(msg)["corps"] == "corps x"


def test_un_mail_illisible_ne_vide_pas_la_boite(monkeypatch):
    imap = _ImapFactice([_brut("bon"), _brut("piege", charset="x-inconnu"), _brut("explose")])
    monkeypatch.setattr(extraire_mails.imaplib, "IMAP4_SSL", imap)

    def _decodage(msg):
        if msg["Subject"] == "explose":
            raise ValueError("mail illisible")
        return message_vers_dict(msg)

    monkeypatch.setattr(extraire_mails, "message_vers_dict", _decodage)
    sujets = [m["sujet"] for m in extraire_mails._recuperer_mails("a", "b")]
    assert sujets == ["piege", "bon"]
    assert imap.readonly is True


def test_fenetre_d_un_jour(monkeypatch):
    imap = _ImapFactice([_brut("vieux", il_y_a=timedelta(hours=30)), _brut("recent")])
    monkeypatch.setattr(extraire_mails.imaplib, "IMAP4_SSL", imap)
    assert [m["sujet"] for m in extraire_mails._recuperer_mails("a", "b")] == ["recent"]


def test_echec_imap_ecrit_un_marqueur_pas_une_boite_vide(monkeypatch, tmp_path):
    def _refus(hote):
        raise OSError("connexion refusée")

    monkeypatch.setattr(extraire_mails.imaplib, "IMAP4_SSL", _refus)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "x")
    chemin = tmp_path / "mails.json"
    monkeypatch.setattr(extraire_mails.sys, "argv", ["prog", str(chemin)])
    extraire_mails.main()
    assert json.loads(chemin.read_text()) == [{"erreur_extraction": "OSError: connexion refusée"}]


def test_secret_absent_ecrit_une_boite_vide(monkeypatch, tmp_path):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    chemin = tmp_path / "mails.json"
    monkeypatch.setattr(extraire_mails.sys, "argv", ["prog", str(chemin)])
    extraire_mails.main()
    assert json.loads(chemin.read_text()) == []
