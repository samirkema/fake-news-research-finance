"""Sources réseaux sociaux : Mastodon (flux RSS par hashtag, sans titre) et
Bluesky (recherche publique de api.bsky.app)."""

import json
from types import SimpleNamespace

from sqlalchemy import select

from fakenews.models import Article
from fakenews.scraper import bluesky, rss, sociaux
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

    def _faux_telecharger(url, entetes=None):
        if "panne" in url:
            return None
        return json.dumps({"posts": [_post(rkey="a"), _post(rkey="b", reponse=True)]}).encode()

    monkeypatch.setattr(sociaux, "_telecharger", _faux_telecharger)
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


# --- Hacker News, Lemmy, 4chan, YouTube ----------------------------------------

HN = {"objectID": "42", "title": "SEC opens probe into meme stock", "story_text": "<p>Details</p>",
      "author": "pg", "created_at": "2026-10-24T10:00:00Z", "points": 12, "num_comments": 3,
      "url": "https://example.com/a"}
LEMMY = {"post": {"name": "Puts on car industry", "body": "Rumeur de faillite", "published": "2026-10-24T10:00:00.123456",
                  "ap_id": "https://lemmy.world/post/7", "url": None},
         "creator": {"name": "bob"}, "counts": {"score": 5, "comments": 2}}
FIL = {"no": 99, "sub": "", "com": "BBBY va remonter<br>croyez-moi", "time": 1792836000, "replies": 40}
VIDEO = {"id": {"videoId": "abc"}, "snippet": {"title": "Crash &amp; panique", "description": "Le marché",
         "channelTitle": "Chaîne", "channelId": "UC1", "publishedAt": "2026-10-24T10:00:00Z"}}


def test_normaliser_sources_ouvertes():
    hn = sociaux.normaliser_hackernews(HN, "SEC")
    assert (hn["plateforme"], hn["url"], hn["contenu"]) == ("hackernews", "https://news.ycombinator.com/item?id=42", "Details")
    lemmy = sociaux.normaliser_lemmy(LEMMY, "stocks")
    assert lemmy["plateforme"] == "lemmy" and lemmy["date_publication"].tzinfo is not None
    fil = sociaux.normaliser_quatrechan(FIL)
    assert (fil["titre"], fil["auteur"], fil["plateforme"]) == ("BBBY va remonter croyez-moi", None, "4chan")
    assert sociaux.normaliser_quatrechan({**FIL, "sticky": 1}) is None
    video = sociaux.normaliser_youtube(VIDEO, "crypto news")
    assert (video["titre"], video["url"]) == ("Crash & panique", "https://www.youtube.com/watch?v=abc")


def test_collecte_sources_ouvertes(db_session, monkeypatch):
    """Chaque source est persistée ; YouTube n'est appelé qu'avec une clé, et la
    clé voyage dans un en-tête, jamais dans l'URL (qui est journalisée en cas
    d'échec)."""
    import json as _j

    monkeypatch.setattr(sociaux, "HACKERNEWS_RECHERCHES", ["SEC"])
    monkeypatch.setattr(sociaux, "LEMMY_COMMUNAUTES", ["stocks"])
    monkeypatch.setattr(sociaux, "YOUTUBE_RECHERCHES", ["crypto news"])
    appels = []

    def _faux(url, entetes=None):
        appels.append((url, entetes))
        if "algolia" in url:
            return _j.dumps({"hits": [HN]}).encode()
        if "lemmy" in url:
            return _j.dumps({"posts": [LEMMY]}).encode()
        if "4cdn" in url:
            return _j.dumps([{"threads": [FIL, {**FIL, "no": 1, "sticky": 1}]}]).encode()
        return _j.dumps({"items": [VIDEO]}).encode()

    monkeypatch.setattr(sociaux, "_telecharger", _faux)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    bilan = sociaux.collecter_sociaux(db_session)
    assert not any("googleapis" in u for u, _ in appels)
    assert bilan["4chan /biz/"] == {"statut": "ok", "ajoutes": 1, "mis_a_jour": 0, "ignores": 1}

    monkeypatch.setenv("YOUTUBE_API_KEY", "cle-secrete")
    bilan = sociaux.collecter_sociaux(db_session)
    url, entetes = next((u, e) for u, e in appels if "googleapis" in u)
    assert "cle-secrete" not in url and entetes == {"X-Goog-Api-Key": "cle-secrete"}
    assert bilan["YouTube 'crypto news'"]["ajoutes"] == 1

    plateformes = sorted(db_session.execute(select(Article.plateforme)).scalars())
    assert plateformes == ["4chan", "hackernews", "lemmy", "youtube"]


def test_source_injoignable(db_session, monkeypatch):
    monkeypatch.setattr(sociaux, "_telecharger", lambda url, entetes=None: None)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    bilan = sociaux.collecter_sociaux(db_session)
    assert {r["statut"] for r in bilan.values()} == {"indisponible"}


def test_hackernews_et_youtube_gardent_leur_identifiant():
    """`canonicaliser_url` retire la query string : sans URL canonique explicite,
    tous les posts Hacker News (`?id=`) et YouTube (`?v=`) fusionnaient en un seul."""
    assert sociaux.normaliser_hackernews(HN, "SEC")["url_canonique"] != \
        sociaux.normaliser_hackernews({**HN, "objectID": "43"}, "SEC")["url_canonique"]
    assert sociaux.normaliser_youtube(VIDEO, "x")["url_canonique"] != \
        sociaux.normaliser_youtube({**VIDEO, "id": {"videoId": "xyz"}}, "x")["url_canonique"]
