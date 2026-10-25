"""Rattachement automatique des articles aux sujets du site (section « Sujets »).

Après la notation, Claude reçoit par lots la liste des sujets ouverts et les
titres des articles du run, et indique quels articles relèvent de quel sujet.
Un lot = un appel : le coût reste de quelques centimes par mois, quel que soit
le nombre de sujets.

Écrit dans `sujet_articles` (`ajoute_par = "evaluateur"`), la table que les
contributeurs remplissent à la main depuis la fiche d'un article ; un
rattachement existant n'est jamais dupliqué. N'entre dans aucun score.
"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from fakenews.llm import CONSIGNE_CONTENU_NON_FIABLE, appeler_structure, encadrer_contenu_non_fiable
from fakenews.models import RattachementSujet, Sujet

logger = logging.getLogger(__name__)

AUTEUR = "evaluateur"
TAILLE_LOT = 50

SCHEMA = {
    "type": "object",
    "properties": {
        "rattachements": {
            "type": "array",
            "description": "Seulement les articles qui relèvent clairement d'au moins un sujet.",
            "items": {
                "type": "object",
                "properties": {
                    "article": {"type": "integer", "description": "numéro A de l'article"},
                    "sujets": {"type": "array", "items": {"type": "integer"}, "description": "numéros S"},
                },
                "required": ["article", "sujets"],
            },
        }
    },
    "required": ["rattachements"],
}

SYSTEM = (
    "Tu classes des articles et des posts de réseaux sociaux dans des sujets "
    "thématiques. Rattache un article à un sujet seulement s'il en traite "
    "clairement le thème ; dans le doute, ne le rattache pas. La plupart des "
    "articles ne relèvent d'aucun sujet : ne les mentionne pas."
    + CONSIGNE_CONTENU_NON_FIABLE
)


def _prompt(sujets: list, articles: list) -> str:
    liste_sujets = "\n".join(
        f"S{i} : {s.titre} — {s.description[:300]}" for i, s in enumerate(sujets)
    )
    liste_articles = "\n".join(
        f"A{i} : {a.titre[:200]} — {' '.join(a.contenu.split())[:150]}" for i, a in enumerate(articles)
    )
    # Titres et descriptions des sujets sont écrits par des contributeurs : tiers
    # eux aussi, donc dans le même cadre que les articles.
    return (
        "Sujets :\n" + encadrer_contenu_non_fiable(liste_sujets)
        + "\n\nArticles :\n" + encadrer_contenu_non_fiable(liste_articles)
    )


def rattacher_aux_sujets(session: Session, articles: list, client) -> int:
    """Retourne le nombre de rattachements créés. Ne lève jamais : un lot en
    échec (quota, budget, réponse inexploitable) est journalisé et sauté."""
    sujets = session.execute(
        select(Sujet).where(Sujet.retire_le.is_(None)).order_by(Sujet.date_creation)
    ).scalars().all()
    if not sujets or not articles:
        return 0

    crees = 0
    for debut in range(0, len(articles), TAILLE_LOT):
        lot = articles[debut:debut + TAILLE_LOT]
        try:
            reponse = appeler_structure(client, SYSTEM, _prompt(sujets, lot), SCHEMA, max_tokens=2048)
            paires = {
                (sujets[s].id, lot[r["article"]].id)
                for r in reponse.get("rattachements", [])
                if isinstance(r.get("article"), int) and 0 <= r["article"] < len(lot)
                for s in r.get("sujets", [])
                if isinstance(s, int) and 0 <= s < len(sujets)
            }
            for sujet_id, article_id in paires:
                resultat = session.execute(
                    insert(RattachementSujet)
                    .values(sujet_id=sujet_id, article_id=article_id, ajoute_par=AUTEUR)
                    .on_conflict_do_nothing()
                )
                crees += resultat.rowcount
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("Rattachement aux sujets impossible pour un lot (%s).", type(exc).__name__)
    logger.info("%d rattachement(s) automatique(s) d'articles à des sujets.", crees)
    return crees
