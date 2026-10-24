"""Collecte Bluesky : posts publics récents trouvés par la recherche de api.bsky.app.

Même contrat que reddit.py : une recherche indisponible ou un post illisible est
journalisé et ignoré, jamais bloquant (cf. doc/V0/architecture.md, dégrader
jamais bloquer).
"""

import json
import logging
from datetime import datetime
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from fakenews.normalisation import canonicaliser_url, hacher_contenu
from fakenews.scraper.persistance import enregistrer_ou_mettre_a_jour
from fakenews.scraper.rss import _telecharger, titre_depuis_texte
from fakenews.scraper.sources_bluesky import NB_POSTS_PAR_RECHERCHE, RECHERCHES

logger = logging.getLogger(__name__)

URL_RECHERCHE = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def normaliser_post(post: dict, recherche: str) -> dict | None:
    """Post Bluesky (JSON de searchPosts) → schéma commun du stockage partagé.

    None pour une réponse ou un post sans texte : ils ne portent aucune
    affirmation à évaluer. L'URL utilise le DID, stable, plutôt que le pseudo,
    qui peut changer et créerait des doublons."""
    record = post["record"]
    texte = (record.get("text") or "").strip()
    if not texte or record.get("reply"):
        return None
    did, rkey = post["author"]["did"], post["uri"].rsplit("/", 1)[-1]
    url = f"https://bsky.app/profile/{did}/post/{rkey}"
    titre = titre_depuis_texte(texte)
    return {
        "titre": titre,
        "contenu": texte,
        "auteur": post["author"].get("handle"),
        "domaine_source": "bsky.app",
        "date_publication": datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00")),
        "url": url,
        "url_canonique": canonicaliser_url(url),
        "hash_contenu": hacher_contenu(titre, texte),
        "plateforme": "bluesky",
        "metadonnees": {
            "recherche": recherche,
            "likes": post.get("likeCount", 0),
            "reposts": post.get("repostCount", 0),
            "reponses": post.get("replyCount", 0),
        },
    }


def collecter_bluesky(session: Session) -> dict:
    """Collecte les posts récents de chaque recherche configurée et les persiste."""
    bilan = {}
    for recherche in RECHERCHES:
        url = f"{URL_RECHERCHE}?{urlencode({'q': recherche, 'limit': NB_POSTS_PAR_RECHERCHE, 'sort': 'latest'})}"
        brut = _telecharger(url)
        try:
            posts = json.loads(brut)["posts"] if brut is not None else None
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("recherche Bluesky illisible: %r (%s)", recherche, type(exc).__name__)
            posts = None
        if posts is None:
            bilan[recherche] = {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
            continue

        compteurs = {"ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
        for post in posts:
            try:
                article = normaliser_post(post, recherche)
                if article is None:
                    compteurs["ignores"] += 1
                    continue
                with session.begin_nested():
                    resultat = enregistrer_ou_mettre_a_jour(session, article)
            except Exception as exc:
                logger.warning("post Bluesky ignoré (%r): %s", recherche, type(exc).__name__)
                compteurs["ignores"] += 1
                continue
            if resultat == "ajoute":
                compteurs["ajoutes"] += 1
            elif resultat == "mis_a_jour":
                compteurs["mis_a_jour"] += 1

        session.commit()
        bilan[recherche] = {"statut": "ok", **compteurs}
        logger.info("Bluesky %r: %s", recherche, bilan[recherche])
    return bilan
