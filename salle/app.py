"""Salle des agents : le CEO donne ses ordres, les agents racontent leur travail.

Site séparé du produit (projet Vercel distinct, racine `salle/`). Deux publics :
- le CEO, connecté par SALLE_CODE (cookie signé) ;
- les agents, qui tournent sur GitHub Actions et postent avec SALLE_JETON
  via `salle/poster.py`.

Écrire « @pipeline-dev ... » dans le fil lance réellement l'agent (workflow
GitHub `agent_salle.yml`). Un agent peut en mentionner un autre ; le nombre de
lancements par tâche est plafonné.

Variables d'environnement : SALLE_DATABASE_URL, SALLE_CODE, SALLE_JETON,
GITHUB_DISPATCH_TOKEN (fine-grained, Actions: write sur ce seul dépôt).
"""

import hashlib
import hmac
import json
import os
import re
import time
import urllib.request

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import create_engine, text

# Agents définis dans .claude/agents/ de ce dépôt : les seuls qui existent sur GitHub.
AGENTS = {"product-triage", "pipeline-dev", "frontend-forum-dev", "release-captain"}
MAX_LANCEMENTS_PAR_TACHE = 10
DEPOT = os.environ.get("GITHUB_REPO", "samirkema/fake-news-trading")
COOKIE = "salle"
DUREE_SESSION = 30 * 24 * 3600
# Le code ouvre le lancement d'agents qui poussent dans le dépôt. Le sleep(1) de
# /login ne borne pas le parallélisme (instances Vercel multiples) : seule la
# longueur du code protège réellement (audit phase 24, F24-06).
CODE_LONGUEUR_MIN = 32

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_engine = None


@app.exception_handler(Exception)
async def _erreur(request: Request, exc: Exception):
    # Seules les routes authentifiées touchent la base : seul le CEO voit ce détail.
    # La 1re ligne d'une erreur psycopg2 ne contient jamais le mot de passe.
    detail = (str(exc).strip().splitlines() or [""])[0]
    return PlainTextResponse(f"{type(exc).__name__}: {detail}", status_code=500)


def sql(requete: str, **params) -> list:
    global _engine
    if _engine is None:
        # postgres://, postgresql://, postgresql+psycopg://… : on force le seul pilote installé.
        url = "postgresql+psycopg2://" + os.environ["SALLE_DATABASE_URL"].split("://", 1)[1]
        _engine = create_engine(url, pool_pre_ping=True)
    with _engine.begin() as conn:
        res = conn.execute(text(requete), params)
        return res.mappings().all() if res.returns_rows else []


# --- Authentification -------------------------------------------------------


def _egal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _code() -> str:
    """SALLE_CODE, refusé s'il est absent ou trop court — à l'entrée ET pour les
    cookies déjà émis : raccourcir le code ferme la porte, il ne l'entrouvre pas."""
    code = os.environ.get("SALLE_CODE", "")
    if len(code) < CODE_LONGUEUR_MIN:
        raise HTTPException(500, f"SALLE_CODE absente ou trop courte ({CODE_LONGUEUR_MIN} caractères "
                                 "minimum) : Vercel → Settings → Environment Variables, puis Redeploy.")
    return code


def _signature(expiration: str) -> str:
    return hmac.new(_code().encode(), expiration.encode(), hashlib.sha256).hexdigest()


def _auteur(request: Request) -> str | None:
    """« ceo » (cookie valide), « agent » (jeton valide) ou None."""
    jeton = os.environ.get("SALLE_JETON")
    entete = request.headers.get("authorization", "")
    if jeton and entete.startswith("Bearer ") and _egal(entete[7:], jeton):
        return "agent"
    exp, _, sig = (request.cookies.get(COOKIE) or "").partition(":")
    if exp.isdigit() and int(exp) > time.time() and _egal(sig, _signature(exp)):
        return "ceo"
    return None


@app.post("/login")
def login(code: str = Form(...)):
    if not _egal(code, _code()):
        time.sleep(1)  # ponytail: freine le bruteforce, code long obligatoire quand même
        return RedirectResponse("/?erreur=1", status_code=303)
    exp = str(int(time.time()) + DUREE_SESSION)
    rep = RedirectResponse("/", status_code=303)
    rep.set_cookie(COOKIE, f"{exp}:{_signature(exp)}", max_age=DUREE_SESSION,
                   httponly=True, secure=True, samesite="strict")
    return rep


@app.post("/logout")
def logout():
    rep = RedirectResponse("/", status_code=303)
    rep.delete_cookie(COOKIE)
    return rep


# --- Messages et lancement des agents --------------------------------------


def mentions(texte: str, auteur: str) -> list[str]:
    """Agents mentionnés, sans doublon, dans l'ordre, sans l'auteur lui-même."""
    vus = []
    for nom in re.findall(r"@([a-z][a-z-]*)", texte):
        if nom in AGENTS and nom != auteur and nom not in vus:
            vus.append(nom)
    return vus


def lancer_agent(agent: str, tache: int, consigne: str) -> None:
    corps = json.dumps({"ref": "main", "inputs": {
        "agent": agent, "tache": str(tache), "consigne": consigne}}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{DEPOT}/actions/workflows/agent_salle.yml/dispatches",
        data=corps, method="POST", headers={
            "Authorization": f"Bearer {os.environ['GITHUB_DISPATCH_TOKEN']}",
            "Accept": "application/vnd.github+json"})
    urllib.request.urlopen(req, timeout=10).close()


def poster(auteur: str, texte: str, tache: int | None) -> dict:
    texte = texte.strip()
    if not texte or len(texte) > 20000:
        raise HTTPException(422, "message vide ou trop long")
    if tache is not None and not sql("select 1 from salle_messages where id = :t and tache = :t", t=tache):
        raise HTTPException(404, "tâche inconnue")
    msg = sql("insert into salle_messages (tache, auteur, texte) values (:t, :a, :x) returning id",
              t=tache, a=auteur, x=texte)[0]
    if tache is None:
        tache = msg["id"]
        sql("update salle_messages set tache = :t where id = :t", t=tache)

    deja = sql("select coalesce(sum(ordres), 0) as n from salle_messages where tache = :t", t=tache)[0]["n"]
    lances, erreurs = [], []
    for agent in mentions(texte, auteur):
        if deja + len(lances) >= MAX_LANCEMENTS_PAR_TACHE:
            erreurs.append(f"@{agent} non lancé : plafond de {MAX_LANCEMENTS_PAR_TACHE} lancements atteint sur cette tâche.")
            continue
        try:
            lancer_agent(agent, tache, texte)
            lances.append(agent)
        except Exception as exc:
            erreurs.append(f"@{agent} non lancé : {exc}")
    if lances:
        sql("update salle_messages set ordres = :n where id = :id", n=len(lances), id=msg["id"])
        sql("insert into salle_messages (tache, auteur, texte) values (:t, 'salle', :x)",
            t=tache, x="Lancé : " + ", ".join(lances))
    for e in erreurs:
        sql("insert into salle_messages (tache, auteur, texte) values (:t, 'salle', :x)", t=tache, x=e)
    return {"id": msg["id"], "tache": tache, "lances": lances}


@app.post("/api/messages")
async def api_poster(request: Request):
    qui = _auteur(request)
    if qui is None:
        raise HTTPException(401)
    corps = await request.json()
    auteur = "ceo" if qui == "ceo" else corps.get("auteur")
    if qui == "agent" and auteur not in AGENTS:
        raise HTTPException(422, "auteur inconnu")
    tache = corps.get("tache")
    if tache is not None and not str(tache).isdigit():
        raise HTTPException(422, "tâche invalide")
    return poster(auteur, str(corps.get("texte", "")), int(tache) if tache is not None else None)


@app.get("/api/messages")
def api_lire(request: Request, apres: int = 0, tache: int | None = None):
    if _auteur(request) is None:
        raise HTTPException(401)
    lignes = sql(
        "select id, tache, auteur, texte, cree_le from salle_messages where id > :apres"
        " and (cast(:tache as bigint) is null or tache = :tache) order by id limit 500",
        apres=apres, tache=tache)
    return [dict(l, cree_le=l["cree_le"].isoformat()) for l in lignes]


# --- Page --------------------------------------------------------------------

PAGE_LOGIN = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Salle des agents</title><style>body{font:16px system-ui;max-width:24rem;margin:20vh auto;padding:0 1rem}
input,button{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin-top:.5rem}</style>
<h1>Salle des agents</h1><form method=post action=/login><input type=password name=code
placeholder=Code autofocus required><button>Entrer</button></form>"""

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Salle des agents</title>
<style>
:root{--fond:#fafafa;--carte:#fff;--texte:#222;--doux:#777;--bord:#ddd;--ceo:#fff4d6;--salle:#eef}
@media (prefers-color-scheme:dark){:root{--fond:#16171a;--carte:#1f2024;--texte:#e6e6e6;--doux:#999;--bord:#333;--ceo:#3a3220;--salle:#24263a}}
body{font:15px/1.45 system-ui;margin:0;background:var(--fond);color:var(--texte)}
header{display:flex;gap:1rem;align-items:center;padding:.75rem 1rem;border-bottom:1px solid var(--bord)}
header h1{font-size:1.1rem;margin:0;flex:1}a{color:inherit}
#fil{max-width:52rem;margin:0 auto;padding:1rem 1rem 9rem}
.m{background:var(--carte);border:1px solid var(--bord);border-radius:8px;padding:.6rem .8rem;margin:.5rem 0}
.m.ceo{background:var(--ceo)}.m.salle{background:var(--salle);font-size:.9em}
.meta{color:var(--doux);font-size:.8em}.meta b{color:var(--texte)}
.t{white-space:pre-wrap;word-wrap:break-word;margin-top:.2rem}
form#envoi{position:fixed;bottom:0;left:0;right:0;background:var(--fond);border-top:1px solid var(--bord);padding:.75rem 1rem}
form#envoi div{max-width:52rem;margin:0 auto;display:flex;gap:.5rem}
textarea{flex:1;font:inherit;padding:.5rem;min-height:3rem;background:var(--carte);color:var(--texte);border:1px solid var(--bord);border-radius:6px}
button{font:inherit;padding:.5rem 1rem}
</style>
<header><h1>Salle des agents <span id=filtre></span></h1>
<form method=post action=/logout><button>Sortir</button></form></header>
<main id=fil></main>
<form id=envoi><div><textarea id=texte placeholder="@pipeline-dev fais…  (agents : AGENTS)"></textarea>
<button>Envoyer</button></div></form>
<script>
const tache = new URLSearchParams(location.search).get('tache');
const fil = document.getElementById('fil');
let dernier = 0;
if (tache) document.getElementById('filtre').innerHTML = '— tâche #' + Number(tache) + ' · <a href="/">tout voir</a>';
function lien(parent, s) {  // texte brut, seules les URL https deviennent des liens
  for (const morceau of s.split(/(https:\\/\\/\\S+)/)) {
    if (morceau.startsWith('https://')) { const a = document.createElement('a'); a.href = a.textContent = morceau; a.target = '_blank'; parent.append(a); }
    else parent.append(morceau);
  }
}
async function charger() {
  const r = await fetch('/api/messages?apres=' + dernier + (tache ? '&tache=' + tache : ''));
  if (r.status === 401) return location.reload();
  const bas = innerHeight + scrollY >= document.body.scrollHeight - 40;
  for (const m of await r.json()) {
    dernier = m.id;
    const d = document.createElement('div'); d.className = 'm ' + m.auteur;
    const meta = document.createElement('div'); meta.className = 'meta';
    const b = document.createElement('b'); b.textContent = m.auteur;
    const a = document.createElement('a'); a.href = '/?tache=' + m.tache; a.textContent = '#' + m.tache;
    meta.append(b, ' · ', a, ' · ' + new Date(m.cree_le).toLocaleString());
    const t = document.createElement('div'); t.className = 't'; lien(t, m.texte);
    d.append(meta, t); fil.append(d);
    if (bas) scrollTo(0, document.body.scrollHeight);
  }
}
document.getElementById('envoi').onsubmit = async e => {
  e.preventDefault();
  const champ = document.getElementById('texte');
  const r = await fetch('/api/messages', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({texte: champ.value, tache: tache ? Number(tache) : null})});
  if (r.ok) { champ.value = ''; const {tache: t} = await r.json(); if (!tache) location.href = '/?tache=' + t; else charger(); }
  else alert('Refusé : ' + (await r.text()));
};
charger(); setInterval(charger, 4000);
</script>"""


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    if _auteur(request) != "ceo":
        return PAGE_LOGIN
    return PAGE.replace("AGENTS", ", ".join(sorted(AGENTS)))
