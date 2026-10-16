"""Extraction en LECTURE SEULE de la boîte de contact du site (product-triage).

Ce module tourne dans le job GitHub Actions de triage, AVANT que Claude ne soit
lancé : il récupère les mails récents adressés à la boîte de contact et les écrit
dans un JSON que l'agent `product-triage` lit comme de simples données (jamais des
instructions). Le mot de passe d'application Gmail n'est visible que de ce step,
jamais de Claude — même logique d'isolation que `DATABASE_URL` pour les retours forum.

Contraintes assumées (cf. tâche) :
- Bibliothèque standard uniquement, aucune dépendance nouvelle.
- Dégradation propre : si le mot de passe n'est pas (encore) configuré, on écrit un
  tableau vide et on sort en 0, pour que le workflow continue de tourner.
- JAMAIS journaliser ni écrire le mot de passe.
- Connexion IMAP en lecture seule (`readonly=True`), on ne modifie jamais la boîte.
"""

import email
import email.header
import email.utils
import imaplib
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Adresse de la boîte de contact affichée en pied de page du site. Sert de défaut
# si GMAIL_ADDRESS n'est pas renseignée.
ADRESSE_PAR_DEFAUT = "fakenewstrackingbase@gmail.com"

# Le triage tourne CHAQUE JOUR : la fenêtre couvre un jour, plus une heure de marge
# pour un run retardé. Plus large, chaque mail revenait dans plusieurs issues
# « Backlog » successives — trente avec l'ancienne fenêtre de 30 jours (audit
# phase 24, F24-03). Même fenêtre que les retours du forum (triage_hebdomadaire.yml).
FENETRE = timedelta(hours=25)
MAX_MAILS = 200

# Longueur maximale du corps conservé par mail : au-delà, c'est du bruit pour le
# triage et ça gonfle inutilement le JSON transmis à Claude.
CORPS_MAX = 4000


def _decoder_octets(octets: bytes, charset: str | None) -> str:
    """Décode avec le charset déclaré, ou utf-8 s'il est absent ou INCONNU.

    Un charset inventé (`charset=x-inconnu`) levait `LookupError`, que rien ne
    rattrapait avant `main` : un seul mail malformé vidait la boîte entière
    (audit phase 24, F24-04). Le charset est écrit par l'expéditeur, donc par
    n'importe qui."""
    try:
        return octets.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return octets.decode("utf-8", errors="replace")


def _decoder_entete(valeur: str) -> str:
    """Décode un en-tête MIME éventuellement encodé (=?utf-8?..?=) en texte lisible.

    `decode_header` renvoie une liste de fragments (octets + charset ou texte déjà
    décodé) ; on les recolle en tolérant les charsets absents ou invalides."""
    if not valeur:
        return ""
    fragments = []
    for partie, charset in email.header.decode_header(valeur):
        if isinstance(partie, bytes):
            fragments.append(_decoder_octets(partie, charset))
        else:
            fragments.append(partie)
    return "".join(fragments).strip()


def _collapser_espaces(texte: str) -> str:
    """Normalise les blancs (retours ligne, tabulations, espaces multiples) en un
    seul espace : un corps de mail lisible sur une ligne par le triage."""
    return " ".join(texte.split())


def _strip_html(html: str) -> str:
    """Retrait minimal des balises HTML, sans dépendance externe. Suffisant pour un
    mail qui n'a qu'une partie HTML : on veut le texte, pas un rendu fidèle."""
    sortie = []
    dans_balise = False
    for caractere in html:
        if caractere == "<":
            dans_balise = True
        elif caractere == ">":
            dans_balise = False
        elif not dans_balise:
            sortie.append(caractere)
    return "".join(sortie)


def _decoder_partie(partie) -> str:
    """Décode la charge utile d'une partie (ou d'un message simple) avec son charset
    déclaré, en retombant sur utf-8 et en remplaçant les octets invalides."""
    charge = partie.get_payload(decode=True)
    if charge is None:
        return ""
    return _decoder_octets(charge, partie.get_content_charset())


def _extraire_corps(msg) -> str:
    """Extrait le corps texte d'un message : on préfère la première partie
    text/plain (en parcourant le multipart), et on retombe sur l'HTML détaguée
    seulement s'il n'existe pas de text/plain. Renvoie toujours du texte brut."""
    html_repli = ""
    if msg.is_multipart():
        for partie in msg.walk():
            if partie.is_multipart():
                continue
            # On ignore les pièces jointes présentées en "attachment".
            disposition = str(partie.get("Content-Disposition") or "")
            if "attachment" in disposition.lower():
                continue
            type_contenu = partie.get_content_type()
            if type_contenu == "text/plain":
                return _decoder_partie(partie)
            if type_contenu == "text/html" and not html_repli:
                html_repli = _strip_html(_decoder_partie(partie))
        return html_repli

    # Message simple (non multipart).
    texte = _decoder_partie(msg)
    if msg.get_content_type() == "text/html":
        return _strip_html(texte)
    return texte


def message_vers_dict(msg) -> dict:
    """Convertit un `email.message.Message` en dict sérialisable pour le triage.

    Fonction PURE et sans réseau : testable directement en construisant un message
    en mémoire. Décode les en-têtes MIME, aplatit le corps (text/plain prioritaire,
    HTML détaguée en repli), normalise les blancs et tronque à CORPS_MAX caractères."""
    # Date en ISO si parsable, sinon chaîne vide (on ne devine pas).
    date_iso = ""
    brut_date = msg.get("Date")
    if brut_date:
        try:
            dt = email.utils.parsedate_to_datetime(brut_date)
            if dt is not None:
                date_iso = dt.isoformat()
        except (TypeError, ValueError):
            date_iso = ""

    corps = _collapser_espaces(_extraire_corps(msg))[:CORPS_MAX]

    return {
        "date": date_iso,
        "expediteur": _decoder_entete(msg.get("From", "")),
        "sujet": _decoder_entete(msg.get("Subject", "")),
        "corps": corps,
    }


def _avant(date_iso: str, depuis: datetime) -> bool:
    """Vrai si la date du mail est connue et antérieure à `depuis`. Une date
    absente ou sans fuseau est GARDÉE : mieux vaut un doublon qu'un mail perdu."""
    if not date_iso:
        return False
    date = datetime.fromisoformat(date_iso)
    return date.tzinfo is not None and date < depuis


def _ecrire(chemin: str, mails: list) -> None:
    """Écrit la liste de mails en JSON UTF-8 lisible (accents conservés)."""
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(mails, f, ensure_ascii=False, indent=2)


def _recuperer_mails(adresse: str, mot_de_passe: str) -> list:
    """Se connecte en IMAP lecture seule, récupère les mails de la fenêtre récente,
    et renvoie la liste des dicts, du plus récent au plus ancien.

    Le mot de passe n'est jamais journalisé ni renvoyé."""
    client = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        client.login(adresse, mot_de_passe)
        # Lecture seule : on ne touche jamais aux drapeaux ni au contenu de la boîte.
        client.select("INBOX", readonly=True)

        depuis = datetime.now(timezone.utc) - FENETRE
        # IMAP SEARCH SINCE ne connaît que la DATE (01-Jan-2026) : il ramène jusqu'à
        # un jour de trop, filtré à l'heure près plus bas.
        critere_date = depuis.strftime("%d-%b-%Y")
        statut, donnees = client.search(None, "SINCE", critere_date)
        if statut != "OK" or not donnees or not donnees[0]:
            return []

        ids = donnees[0].split()
        # Les derniers IDs correspondent aux messages les plus récents : on garde le
        # plafond par la fin, puis on inverse pour obtenir du plus récent au plus ancien.
        ids = ids[-MAX_MAILS:]

        mails = []
        for identifiant in reversed(ids):
            statut, charge = client.fetch(identifiant, "(RFC822)")
            if statut != "OK" or not charge or not charge[0]:
                continue
            brut = charge[0][1]
            if not isinstance(brut, (bytes, bytearray)):
                continue
            try:
                mail = message_vers_dict(email.message_from_bytes(brut))
            except Exception as exc:  # noqa: BLE001 — un mail illisible ne masque pas les autres.
                logger.warning("Mail %s ignoré (%s: %s).", identifiant.decode(), type(exc).__name__, exc)
                continue
            if _avant(mail["date"], depuis):
                continue
            mails.append(mail)
        return mails
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001 — la fermeture ne doit jamais masquer le résultat.
            pass


def main() -> None:
    """Point d'entrée du step GitHub Actions. Ne lève jamais, sort toujours en 0
    pour que le triage continue : secret absent ⇒ `[]` (boîte volontairement non
    branchée) ; erreur IMAP/connexion ⇒ `[{"erreur_extraction": ...}]`, que le
    triage doit signaler plutôt que de conclure à une boîte vide."""
    chemin = sys.argv[1] if len(sys.argv) > 1 else "mails.json"
    adresse = os.environ.get("GMAIL_ADDRESS") or ADRESSE_PAR_DEFAUT
    mot_de_passe = os.environ.get("GMAIL_APP_PASSWORD", "")

    # Dégradation propre tant que le secret n'est pas configuré : on n'échoue pas.
    if not mot_de_passe.strip():
        logger.info(
            "GMAIL_APP_PASSWORD absent : boîte de contact non lue, écriture d'un JSON vide "
            "dans %s (dégradation propre, le workflow continue).",
            chemin,
        )
        _ecrire(chemin, [])
        return

    try:
        mails = _recuperer_mails(adresse, mot_de_passe)
        _ecrire(chemin, mails)
        logger.info("%d mail(s) extrait(s) de la boîte de contact vers %s.", len(mails), chemin)
    except Exception as exc:  # noqa: BLE001 — jamais faire échouer le workflow sur l'IMAP.
        # On ne journalise que le type/texte de l'erreur, jamais le mot de passe.
        # Le workflow continue, mais l'échec reste VISIBLE : un `[]` nu se lisait
        # « aucun retour » dans le backlog, alors que la boîte n'avait pas été lue
        # (audit phase 24, F24-04). Le prompt du triage reporte ce marqueur.
        logger.warning("Extraction des mails impossible (%s) : marqueur d'échec écrit.", exc)
        _ecrire(chemin, [{"erreur_extraction": f"{type(exc).__name__}: {exc}"}])


if __name__ == "__main__":
    main()
