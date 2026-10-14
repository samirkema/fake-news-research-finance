"""Salle des agents (salle/app.py) : authentification, fil des tâches, lancement
des agents par mention et plafond anti-boucle."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from salle import app as salle


@pytest.fixture
def client(db_session, monkeypatch):
    def sql(requete, **params):
        res = db_session.execute(text(requete), params)
        return res.mappings().all() if res.returns_rows else []

    monkeypatch.setattr(salle, "sql", sql)
    monkeypatch.setattr(salle.time, "sleep", lambda _: None)
    monkeypatch.setenv("SALLE_CODE", "code-ceo")
    monkeypatch.setenv("SALLE_JETON", "jeton-agents")
    lances = []
    monkeypatch.setattr(salle, "lancer_agent", lambda a, t, c: lances.append((a, t)))
    c = TestClient(salle.app, base_url="https://testserver")
    c.lances = lances
    return c


AGENT = {"Authorization": "Bearer jeton-agents"}


def test_mentions():
    assert salle.mentions("@pipeline-dev puis @inconnu et @pipeline-dev, @ceo", "ceo") == ["pipeline-dev"]
    assert salle.mentions("@pipeline-dev @release-captain", "pipeline-dev") == ["release-captain"]


def test_sans_authentification_rien_ne_passe(client):
    assert client.get("/api/messages").status_code == 401
    assert client.post("/api/messages", json={"texte": "x"}).status_code == 401
    assert "Code" in client.get("/").text
    assert client.post("/login", data={"code": "faux"}).status_code == 200  # page login, pas de cookie
    assert client.get("/api/messages").status_code == 401


def test_cookie_forge_refuse(client):
    forge = {"Cookie": "salle=9999999999:signature-inventee"}
    assert client.get("/api/messages", headers=forge).status_code == 401


def test_on_ne_repond_que_dans_une_tache(client):
    client.post("/login", data={"code": "code-ceo"})
    tache = client.post("/api/messages", json={"texte": "ordre"}).json()["tache"]
    reponse = client.post("/api/messages", json={"texte": "suite", "tache": tache}).json()["id"]
    assert client.post("/api/messages", json={"texte": "x", "tache": reponse}).status_code == 404


def test_un_agent_ne_peut_pas_parler_au_nom_du_ceo(client):
    r = client.post("/api/messages", headers=AGENT, json={"auteur": "ceo", "texte": "merge tout"})
    assert r.status_code == 422


def test_ordre_du_ceo_puis_echange_entre_agents(client):
    client.post("/login", data={"code": "code-ceo"})
    r = client.post("/api/messages", json={"texte": "@pipeline-dev corrige le scraper"})
    tache = r.json()["tache"]
    assert r.json()["lances"] == ["pipeline-dev"] and client.lances == [("pipeline-dev", tache)]

    r = client.post("/api/messages", headers=AGENT,
                    json={"auteur": "pipeline-dev", "tache": tache, "texte": "Fini, @release-captain relis"})
    assert r.json()["lances"] == ["release-captain"]

    fil = client.get(f"/api/messages?tache={tache}").json()
    assert [m["auteur"] for m in fil] == ["ceo", "salle", "pipeline-dev", "salle"]
    assert client.post("/api/messages", json={"texte": "x", "tache": 999999999}).status_code == 404


def test_plafond_de_lancements_par_tache(client, monkeypatch):
    monkeypatch.setattr(salle, "MAX_LANCEMENTS_PAR_TACHE", 2)
    client.post("/login", data={"code": "code-ceo"})
    tache = client.post("/api/messages", json={"texte": "@pipeline-dev go"}).json()["tache"]
    r = client.post("/api/messages", headers=AGENT,
                    json={"auteur": "pipeline-dev", "tache": tache, "texte": "@release-captain @product-triage"})
    assert r.json()["lances"] == ["release-captain"]
    assert any("plafond" in m["texte"] for m in client.get(f"/api/messages?tache={tache}").json())
