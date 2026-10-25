"""Rattachement automatique des articles aux sujets par l'évaluateur."""

from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.evaluateur.sujets import rattacher_aux_sujets
from fakenews.models import Article, RattachementSujet, Sujet
from tests._llm_factice import ClientFactice


def _article(db_session, n):
    article = Article(
        titre=f"Transfert de Mbappé {n}", contenu="rumeur", domaine_source="exemple.test",
        date_publication=datetime.now(timezone.utc), url=f"https://exemple.test/{n}",
        url_canonique=f"https://exemple.test/{n}", hash_contenu=f"h{n}", plateforme="rss", metadonnees={},
    )
    db_session.add(article)
    db_session.flush()
    return article


def _sujet(db_session, titre, retire=False):
    sujet = Sujet(titre=titre, description="desc", cree_par="carole")
    if retire:
        sujet.retire_le, sujet.retire_par = datetime.now(timezone.utc), "root"
    db_session.add(sujet)
    db_session.flush()
    return sujet


def test_rattache_selon_la_reponse_et_ignore_les_indices_invalides(db_session):
    foot, banque = _sujet(db_session, "Football"), _sujet(db_session, "Banques")
    _sujet(db_session, "Retiré", retire=True)
    a0, a1 = _article(db_session, 0), _article(db_session, 1)
    client = ClientFactice({"rattachements": [
        {"article": 0, "sujets": [0]},
        {"article": 1, "sujets": [0, 1, 7]},  # 7 : n'existe pas
        {"article": 9, "sujets": [0]},  # 9 : n'existe pas
    ]})

    assert rattacher_aux_sujets(db_session, [a0, a1], client) == 3
    paires = {(r.sujet_id, r.article_id, r.ajoute_par) for r in db_session.execute(select(RattachementSujet)).scalars()}
    assert paires == {(foot.id, a0.id, "evaluateur"), (foot.id, a1.id, "evaluateur"), (banque.id, a1.id, "evaluateur")}
    # Le sujet retiré n'est pas proposé au modèle.
    assert "Retiré" not in client.dernier_appel["messages"][0]["content"]

    # Rejouer ne duplique rien.
    assert rattacher_aux_sujets(db_session, [a0, a1], client) == 0


def test_sans_sujet_aucun_appel(db_session):
    client = ClientFactice({"rattachements": []})
    assert rattacher_aux_sujets(db_session, [_article(db_session, 0)], client) == 0
    assert client.dernier_appel is None


def test_un_echec_du_modele_ne_bloque_pas(db_session):
    _sujet(db_session, "Football")
    client = ClientFactice(leve=RuntimeError("quota"))
    assert rattacher_aux_sujets(db_session, [_article(db_session, 0)], client) == 0
