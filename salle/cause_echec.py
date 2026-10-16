"""Cause d'un run d'agent en échec, lue dans la sortie de claude-code-action.

    python salle/cause_echec.py "$RUNNER_TEMP/claude-execution-output.json"

Imprime le texte du message `result` quand il signale une erreur, sinon rien.
Ne lève jamais : un fichier absent ou illisible ne doit pas empêcher le
workflow de poster le bilan dans la salle.
"""

import json
import sys

LONGUEUR_MAX = 1500


def cause(messages: list) -> str:
    resultats = [m for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    if not resultats or not resultats[-1].get("is_error"):
        return ""
    return f"Cause : {resultats[-1].get('result') or 'non précisée par Claude'}"[:LONGUEUR_MAX]


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            print(cause(json.load(f)))
    except Exception as exc:  # noqa: BLE001 — le bilan doit partir quoi qu'il arrive.
        print(f"Cause : sortie de Claude illisible ({type(exc).__name__}).")
