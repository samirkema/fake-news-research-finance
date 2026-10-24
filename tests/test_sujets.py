"""Section « Sujets » : création réservée aux contributeurs, débat ouvert à tous
les comptes connectés, analyses réservées aux contributeurs, retrait par le
superadmin (masquage)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from fakenews.frontend.app import app, get_session
from fakenews.models import Compte, Sujet, RattachementSujet, SujetMessage
from test_commentaires import _article, _connecter, _creer_compte, _csrf


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def _contributeur(client, db_session, mode_heberge, pseudo="carole"):
    mode_heberge("secret")
    _creer_compte(db_session, pseudo, "contributeur", "code-personnel-long")
    client.post("/login", data={"pseudo": pseudo, "mot_de_passe": "code-personnel-long"})
    db_session.flush()


def _creer(client, titre="Faux rachat de banque", description="Rumeurs de rachat."):
    return client.post(
        "/sujets",
        data={"titre": titre, "description": description, "csrf": _csrf(client, "/sujets")},
        follow_redirects=False,
    )


def _sujet(db_session, titre="Sujet test"):
    sujet = Sujet(titre=titre, description="desc", cree_par="carole")
    db_session.add(sujet)
    db_session.flush()
    return sujet


def test_un_contributeur_cree_un_sujet(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    r = _creer(client)
    assert r.status_code == 303
    sujet = db_session.execute(select(Sujet)).scalars().one()
    assert sujet.cree_par == "carole"
    assert r.headers["location"] == f"/sujets/{sujet.id}"
    assert "Faux rachat de banque" in client.get("/sujets").text


def test_un_spectateur_ne_cree_pas_de_sujet(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "alice")
    csrf = _csrf(client, "/sujets")
    r = client.post("/sujets", data={"titre": "T", "description": "D", "csrf": csrf})
    assert r.status_code == 404
    assert db_session.execute(select(Sujet)).first() is None
    assert "Ouvrir un nouveau sujet" not in client.get("/sujets").text


def test_creation_sans_csrf_refusee(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    r = client.post("/sujets", data={"titre": "T", "description": "D", "csrf": "faux"})
    assert r.status_code == 403
    assert db_session.execute(select(Sujet)).first() is None


@pytest.mark.parametrize(
    "titre,description",
    [("", "d"), ("   ", "d"), ("t", ""), ("x" * 151, "d"), ("t", "y" * 2001)],
)
def test_validation_du_sujet(client, db_session, mode_heberge, titre, description):
    _contributeur(client, db_session, mode_heberge)
    r = _creer(client, titre, description)
    assert r.status_code == 303 and "erreur=" in r.headers["location"]
    assert db_session.execute(select(Sujet)).first() is None


def test_titre_en_double_refuse(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    _creer(client, "Mon sujet")
    r = _creer(client, "  mon   SUJET ")
    assert "sujet_existe" in r.headers["location"]
    assert len(db_session.execute(select(Sujet)).scalars().all()) == 1


def test_plafond_de_creation(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    for i in range(5):
        assert "erreur" not in _creer(client, f"Sujet {i}").headers["location"]
    assert "plafond_sujets" in _creer(client, "Sujet de trop").headers["location"]


def test_le_html_du_sujet_est_echappe(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    r = _creer(client, "<script>alert(1)</script>", "<img src=x onerror=alert(1)>")
    page = client.get(r.headers["location"]).text
    assert "<script>alert(1)" not in page and "<img src=x" not in page


def test_un_spectateur_debat_mais_ne_publie_pas_d_analyse(client, db_session, mode_heberge):
    mode_heberge("secret")
    sujet = _sujet(db_session)
    _connecter(client, db_session, "alice")
    csrf = _csrf(client, f"/sujets/{sujet.id}")
    chemin = f"/sujets/{sujet.id}/messages"

    ok = client.post(chemin, data={"texte": "Je doute.", "genre": "debat", "csrf": csrf}, follow_redirects=False)
    assert ok.status_code == 303
    interdit = client.post(chemin, data={"texte": "Analyse", "genre": "analyse", "csrf": csrf})
    assert interdit.status_code == 404
    messages = db_session.execute(select(SujetMessage)).scalars().all()
    assert [(m.genre, m.pseudo) for m in messages] == [("debat", "alice")]
    assert "Publier une analyse" not in client.get(f"/sujets/{sujet.id}").text


def test_un_contributeur_publie_une_analyse(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    sujet = _sujet(db_session)
    csrf = _csrf(client, f"/sujets/{sujet.id}")
    client.post(f"/sujets/{sujet.id}/messages", data={"texte": "Évolution sur 3 mois.", "genre": "analyse", "csrf": csrf})
    page = client.get(f"/sujets/{sujet.id}").text
    assert "Évolution sur 3 mois." in page


def test_message_invalide(client, db_session, mode_heberge):
    mode_heberge("secret")
    sujet = _sujet(db_session)
    _connecter(client, db_session, "alice")
    csrf = _csrf(client, f"/sujets/{sujet.id}")
    chemin = f"/sujets/{sujet.id}/messages"
    assert "erreur=" in client.post(chemin, data={"texte": "  ", "csrf": csrf}, follow_redirects=False).headers["location"]
    assert "erreur=" in client.post(chemin, data={"texte": "x" * 2001, "csrf": csrf}, follow_redirects=False).headers["location"]
    assert client.post(chemin, data={"texte": "ok", "genre": "autre", "csrf": csrf}).status_code == 400
    assert client.post(chemin, data={"texte": "ok", "csrf": "faux"}).status_code == 403
    assert db_session.execute(select(SujetMessage)).first() is None


def test_rattacher_un_article(client, db_session, mode_heberge):
    _contributeur(client, db_session, mode_heberge)
    sujet = _sujet(db_session)
    article = _article(db_session)
    chemin = f"/articles/{article.id}"
    for _ in range(2):  # idempotent
        r = client.post(
            f"{chemin}/sujets",
            data={"sujet_id": str(sujet.id), "csrf": _csrf(client, chemin)},
            follow_redirects=False,
        )
        assert r.status_code == 303
    assert len(db_session.execute(select(RattachementSujet)).scalars().all()) == 1
    assert article.titre in client.get(f"/sujets/{sujet.id}").text
    assert sujet.titre in client.get(chemin).text


def test_un_spectateur_ne_rattache_pas(client, db_session, mode_heberge):
    mode_heberge("secret")
    sujet = _sujet(db_session)
    article = _article(db_session)
    _connecter(client, db_session, "alice")
    csrf = _csrf(client, f"/articles/{article.id}")
    r = client.post(f"/articles/{article.id}/sujets", data={"sujet_id": str(sujet.id), "csrf": csrf})
    assert r.status_code == 404
    assert db_session.execute(select(RattachementSujet)).first() is None


def test_retrait_reserve_au_superadmin_et_masque_sans_effacer(client, db_session, mode_heberge):
    mode_heberge("secret")
    sujet = _sujet(db_session)
    msg = SujetMessage(sujet_id=sujet.id, genre="debat", pseudo="bob", texte="Message litigieux")
    db_session.add(msg)
    db_session.flush()

    _contributeur(client, db_session, mode_heberge)
    csrf = _csrf(client, f"/sujets/{sujet.id}")
    assert client.post(f"/sujets/messages/{msg.id}/retirer", data={"csrf": csrf}).status_code == 404
    assert client.post(f"/sujets/{sujet.id}/retirer", data={"csrf": csrf}).status_code == 404

    _creer_compte(db_session, "root", "superadmin", "code-super-secret")
    root = TestClient(app, base_url="https://testserver")
    root.post("/login", data={"pseudo": "root", "mot_de_passe": "code-super-secret"})
    csrf = _csrf(root, f"/sujets/{sujet.id}")
    assert root.post(f"/sujets/messages/{msg.id}/retirer", data={"csrf": csrf}, follow_redirects=False).status_code == 303
    db_session.refresh(msg)
    assert msg.retire_par == "root" and msg.texte == "Message litigieux"
    assert "Message litigieux" not in client.get(f"/sujets/{sujet.id}").text
    assert "Message litigieux" in root.get(f"/sujets/{sujet.id}").text

    root.post(f"/sujets/{sujet.id}/retirer", data={"csrf": csrf})
    assert client.get(f"/sujets/{sujet.id}").status_code == 404
    assert sujet.titre not in client.get("/sujets").text
    assert root.get(f"/sujets/{sujet.id}").status_code == 200


def test_acces_anonyme_redirige(client, mode_heberge):
    mode_heberge("secret")
    assert client.get("/sujets", follow_redirects=False).status_code in (302, 303, 307)
