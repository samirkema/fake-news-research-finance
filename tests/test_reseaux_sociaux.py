"""Sources réseaux sociaux : Mastodon (flux RSS par hashtag, sans titre) et
Bluesky (recherche publique de api.bsky.app)."""

import json
from types import SimpleNamespace

from sqlalchemy import select

from fakenews.models import Article
from fakenews.scraper import bluesky, rss
from fakenews.scraper.rss import titre_depuis_texte


def _post(texte="Le marché va s'effondrer demain, vendez tout", rkey="3abc", reponse=False):
    record = {"text": texte, "createdAt": "2026-10-24T12:51:10.295Z"}
    if reponse:
        record["reply"] = {"parent": {"uri": "at://x"}}
    return {
        "uri": f"at://did:plc:auteur/app.bsky.feed.post/{rkey}",
        "author": {"did": "did:plc:auteur", "handle": "auteur.bsky.social"},
        "record": record,
        "likeCount": 3,
        "repostCount": 1,
        "replyCount": 0,
    }


def test_titre_depuis_texte():
    assert titre_depuis_texte("Première ligne\nseconde") == "Première ligne"
    assert titre_depuis_texte("") == ""
    long = "mot " * 60
    titre = titre_depuis_texte(long)
    assert len(titre) <= 121 and titre.endswith("…") and not titre.endswith(" …")


def test_normaliser_post_bluesky():
    article = bluesky.normaliser_post(_post(), "stocks")
    assert article["plateforme"] == "bluesky"
    assert article["url"] == "https://bsky.app/profile/did:plc:auteur/post/3abc"
    assert article["titre"] == article["contenu"] == "Le marché va s'effondrer demain, vendez tout"
    assert article["date_publication"].tzinfo is not None
    assert article["metadonnees"] == {"recherche": "stocks", "likes": 3, "reposts": 1, "reponses": 0}


def test_reponses_et_posts_vides_ignores():
    assert bluesky.normaliser_post(_post(reponse=True), "stocks") is None
    assert bluesky.normaliser_post(_post(texte="  "), "stocks") is None


def test_collecte_bluesky(db_session, monkeypatch):
    """Une recherche répond, l'autre est injoignable : la première est
    persistée, la seconde marquée indisponible, sans interrompre la collecte."""
    monkeypatch.setattr(bluesky, "RECHERCHES", ["stocks", "panne"])

    def _faux_telecharger(url):
        if "panne" in url:
            return None
        return json.dumps({"posts": [_post(rkey="a"), _post(rkey="b", reponse=True)]}).encode()

    monkeypatch.setattr(bluesky, "_telecharger", _faux_telecharger)
    bilan = bluesky.collecter_bluesky(db_session)

    assert bilan["stocks"] == {"statut": "ok", "ajoutes": 1, "mis_a_jour": 0, "ignores": 1}
    assert bilan["panne"]["statut"] == "indisponible"
    article = db_session.execute(select(Article)).scalars().one()
    assert article.plateforme == "bluesky" and article.domaine_source == "bsky.app"


def test_post_mastodon_sans_titre_est_collecte(db_session, monkeypatch):
    """Un post Mastodon n'a pas de <title> : il était ignoré comme « incomplet »."""
    source = {"nom": "Mastodon #stocks", "domaine_source": "mastodon.social",
              "url": "https://mastodon.social/tags/stocks.rss", "plateforme": "mastodon"}
    entree = {"link": "https://mastodon.social/@x/1", "summary": "<p>$HBAN bénéfice en hausse</p>",
              "published_parsed": (2026, 10, 24, 7, 39, 2, 0, 0, 0)}
    monkeypatch.setattr(rss, "RSS_SOURCES", [source])
    monkeypatch.setattr(rss, "_recuperer_flux", lambda s: (s, SimpleNamespace(entries=[entree])))

    bilan = rss.collecter_rss(db_session)

    assert bilan["Mastodon #stocks"]["ajoutes"] == 1
    article = db_session.execute(select(Article)).scalars().one()
    assert (article.titre, article.plateforme) == ("$HBAN bénéfice en hausse", "mastodon")
