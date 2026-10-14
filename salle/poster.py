"""Ce que les agents utilisent pour parler dans la salle (stdlib seule).

    python salle/poster.py dire "texte"     (ou « dire - » pour lire stdin)
    python salle/poster.py lire             (le fil de la tâche en cours)

Lit SALLE_URL, SALLE_JETON, SALLE_AGENT et SALLE_TACHE dans l'environnement.
"""

import json
import os
import sys
import urllib.request


def appel(methode: str, chemin: str, corps: dict | None = None):
    req = urllib.request.Request(
        os.environ["SALLE_URL"].rstrip("/") + chemin, method=methode,
        data=json.dumps(corps).encode() if corps is not None else None,
        headers={"Authorization": f"Bearer {os.environ['SALLE_JETON']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as rep:
        return json.load(rep)


def main(args: list[str]) -> None:
    tache = int(os.environ["SALLE_TACHE"])
    if args[:1] == ["dire"] and len(args) > 1:
        texte = sys.stdin.read() if args[1:] == ["-"] else " ".join(args[1:])
        res = appel("POST", "/api/messages",
                    {"auteur": os.environ["SALLE_AGENT"], "tache": tache, "texte": texte})
        if res["lances"]:
            print("Agents lancés :", ", ".join(res["lances"]))
    elif args == ["lire"]:
        for m in appel("GET", f"/api/messages?tache={tache}"):
            print(f"--- {m['auteur']} ({m['cree_le'][:16]})\n{m['texte']}\n")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
