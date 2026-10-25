"""Collecte des sources sociales ouvertes : Hacker News, Lemmy, 4chan /biz/ et
YouTube (si une clé est fournie). Listes et volumes dans sources_sociales.py.

Même contrat que les autres collecteurs : une source injoignable ou un post
illisible est journalisé et ignoré, jamais bloquant (cf. doc/V0/architecture.md,
dégrader jamais bloquer).
"""

import json
import logging
import os
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from fakenews.normalisation import canonicaliser_url, hacher_contenu
from fakenews.scraper.persistance import enregistrer_ou_mettre_a_jour
from fakenews.scraper.rss import _telecharger, nettoyer_html, titre_depuis_texte
from fakenews.scraper.sources_sociales import (
    HACKERNEWS_PAR_RECHERCHE,
    HACKERNEWS_RECHERCHES,
    LEMMY_COMMUNAUTES,
    LEMMY_INSTANCE,
    LEMMY_PAR_COMMUNAUTE,
    QUATRECHAN_NB_FILS,
    QUATRECHAN_PLANCHE,
    YOUTUBE_PAR_RECHERCHE,
    YOUTUBE_RECHERCHES,
)

logger = logging.getLogger(__name__)


def _json(url: str, entetes: dict | None = None):
    """JSON d'une URL, ou None si elle est injoignable ou illisible."""
    brut = _telecharger(url, entetes=entetes)
    if brut is None:
        return None
    try:
        return json.loads(brut)
    except ValueError:
        logger.warning("réponse JSON illisible : %s", url.split("?")[0])
        return None


def _date_iso(texte: str) -> datetime:
    date = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def _article(titre, contenu, auteur, domaine, date, url, plateforme, metadonnees,
             url_canonique: str | None = None) -> dict | None:
    """Schéma commun du stockage partagé ; None s'il n'y a rien à évaluer.

    `url_canonique` explicite quand l'identifiant du post est dans la query
    string (Hacker News `?id=`, YouTube `?v=`) : `canonicaliser_url` la retire,
    et tous les posts de la source fusionneraient en un seul."""
    titre = (titre or "").strip() or titre_depuis_texte(contenu)
    if not titre:
        return None
    return {
        "titre": titre,
        "contenu": contenu,
        "auteur": auteur,
        "domaine_source": domaine,
        "date_publication": date,
        "url": url,
        "url_canonique": url_canonique or canonicaliser_url(url),
        "hash_contenu": hacher_contenu(titre, contenu),
        "plateforme": plateforme,
        "metadonnees": metadonnees,
    }


def persister(session: Session, elements: list | None, normaliser) -> dict:
    """Normalise et enregistre chaque élément ; bilan au format des autres
    collecteurs. `elements` à None : la source n'a pas répondu."""
    if elements is None:
        return {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
    compteurs = {"ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
    for element in elements:
        try:
            article = normaliser(element)
            if article is None:
                compteurs["ignores"] += 1
                continue
            with session.begin_nested():
                resultat = enregistrer_ou_mettre_a_jour(session, article)
        except Exception as exc:
            logger.warning("élément ignoré (%s)", type(exc).__name__)
            compteurs["ignores"] += 1
            continue
        if resultat == "ajoute":
            compteurs["ajoutes"] += 1
        elif resultat == "mis_a_jour":
            compteurs["mis_a_jour"] += 1
    session.commit()
    return {"statut": "ok", **compteurs}


# --- Normalisation, une fonction par source -----------------------------------


def normaliser_hackernews(hit: dict, recherche: str) -> dict | None:
    return _article(
        hit.get("title"),
        nettoyer_html(hit.get("story_text") or ""),
        hit.get("author"),
        "news.ycombinator.com",
        _date_iso(hit["created_at"]),
        f"https://news.ycombinator.com/item?id={hit['objectID']}",
        "hackernews",
        {"recherche": recherche, "points": hit.get("points") or 0,
         "commentaires": hit.get("num_comments") or 0, "lien": hit.get("url")},
        url_canonique=f"https://news.ycombinator.com/item?id={hit['objectID']}",
    )


def normaliser_lemmy(vue: dict, communaute: str) -> dict | None:
    post = vue["post"]
    return _article(
        post.get("name"),
        (post.get("body") or "").strip(),
        vue.get("creator", {}).get("name"),
        LEMMY_INSTANCE.split("//", 1)[1],
        _date_iso(post["published"]),
        post["ap_id"],
        "lemmy",
        {"communaute": communaute, "score": vue.get("counts", {}).get("score", 0),
         "commentaires": vue.get("counts", {}).get("comments", 0), "lien": post.get("url")},
    )


def normaliser_quatrechan(fil: dict) -> dict | None:
    """Fil du catalogue 4chan. Les fils épinglés (règles de la planche) sont ignorés."""
    if fil.get("sticky"):
        return None
    return _article(
        nettoyer_html(fil.get("sub") or ""),
        nettoyer_html(fil.get("com") or ""),
        None,  # anonyme par construction
        "boards.4chan.org",
        datetime.fromtimestamp(fil["time"], tz=timezone.utc),
        f"https://boards.4chan.org/{QUATRECHAN_PLANCHE}/thread/{fil['no']}",
        "4chan",
        {"planche": QUATRECHAN_PLANCHE, "reponses": fil.get("replies", 0)},
    )


def normaliser_youtube(item: dict, recherche: str) -> dict | None:
    snippet = item["snippet"]
    return _article(
        unescape(snippet.get("title") or ""),
        unescape(snippet.get("description") or ""),
        snippet.get("channelTitle"),
        "youtube.com",
        _date_iso(snippet["publishedAt"]),
        f"https://www.youtube.com/watch?v={item['id']['videoId']}",
        "youtube",
        {"recherche": recherche, "chaine": snippet.get("channelId")},
        url_canonique=f"https://www.youtube.com/watch?v={item['id']['videoId']}",
    )


# --- Collecte ------------------------------------------------------------------


def collecter_sociaux(session: Session) -> dict:
    bilan = {}

    for recherche in HACKERNEWS_RECHERCHES:
        url = "https://hn.algolia.com/api/v1/search_by_date?" + urlencode(
            {"query": recherche, "tags": "story", "hitsPerPage": HACKERNEWS_PAR_RECHERCHE})
        reponse = _json(url)
        hits = reponse.get("hits") if isinstance(reponse, dict) else None
        bilan[f"Hacker News {recherche!r}"] = persister(
            session, hits, lambda h, r=recherche: normaliser_hackernews(h, r))

    for communaute in LEMMY_COMMUNAUTES:
        url = f"{LEMMY_INSTANCE}/api/v3/post/list?" + urlencode(
            {"community_name": communaute, "sort": "New", "limit": LEMMY_PAR_COMMUNAUTE})
        reponse = _json(url)
        posts = reponse.get("posts") if isinstance(reponse, dict) else None
        bilan[f"Lemmy c/{communaute}"] = persister(
            session, posts, lambda v, c=communaute: normaliser_lemmy(v, c))

    catalogue = _json(f"https://a.4cdn.org/{QUATRECHAN_PLANCHE}/catalog.json")
    fils = ([f for page in catalogue for f in page.get("threads", [])][:QUATRECHAN_NB_FILS]
            if isinstance(catalogue, list) else None)
    bilan[f"4chan /{QUATRECHAN_PLANCHE}/"] = persister(session, fils, normaliser_quatrechan)

    cle = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not cle:
        logger.info("YouTube non collecté : YOUTUBE_API_KEY absente.")
    for recherche in YOUTUBE_RECHERCHES if cle else []:
        url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(
            {"part": "snippet", "q": recherche, "type": "video", "order": "date",
             "maxResults": YOUTUBE_PAR_RECHERCHE})
        reponse = _json(url, entetes={"X-Goog-Api-Key": cle})
        items = reponse.get("items") if isinstance(reponse, dict) else None
        bilan[f"YouTube {recherche!r}"] = persister(
            session, items, lambda i, r=recherche: normaliser_youtube(i, r))

    for nom, resultat in bilan.items():
        logger.info("%s: %s", nom, resultat)
    return bilan
