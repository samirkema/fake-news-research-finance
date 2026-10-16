"""Coupe-circuit budgétaire des appels Claude — infrastructure neutre, partagée par
l'évaluateur et le contextualiseur au même titre que `fakenews.llm`.

Les plafonds par run (`LLM_PLAFOND_*`) bornent le NOMBRE d'appels, pas la dépense
cumulée : avec un run quotidien, ils laissent 30 runs par mois. Ici on borne les
euros dépensés par mois civil (UTC), compteur persisté en base (`usage_llm`, cf.
supabase/migrations/0009_usage_llm.sql) puisque chaque run GitHub Actions repart
d'un disque vierge.

Le garde est FAIL-CLOSED : si le compteur ne peut pas être lu (table absente,
base injoignable), l'appel n'est pas fait. Un budget qu'on ne sait pas mesurer
n'est pas un budget. Les appelants dégradent déjà proprement (signal exclu,
mise en contexte non générée) — cf. doc/V0/architecture.md.

Dépassement maximal : un appel (quelques millièmes d'euro), puisque le contrôle a
lieu avant chaque appel et la dépense est inscrite juste après."""

import logging
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, Integer, MetaData, Numeric, Table, Text, select
from sqlalchemy.dialects.postgresql import insert

from fakenews.config import reel_depuis_env

logger = logging.getLogger(__name__)

NOM_ENV_BUDGET = "LLM_BUDGET_MENSUEL_EUR"
BUDGET_MENSUEL_EUR_PAR_DEFAUT = 2.0

# $ par million de tokens (entrée, sortie). Converti 1 $ = 1 € : surestimation
# volontaire (l'euro vaut plus que le dollar), côté prudent pour un plafond.
# Modèle inconnu → tarif haut, jamais le tarif Haiku : mieux vaut s'arrêter trop
# tôt que sous-compter un modèle plus cher.
TARIFS_USD_PAR_MILLION = {
    "claude-haiku-4-5": (1.0, 5.0),
}
TARIF_INCONNU = (5.0, 25.0)

# Table hors `fakenews.models.Base` : voir la migration 0009.
_metadata = MetaData()
usage_llm = Table(
    "usage_llm",
    _metadata,
    Column("mois", Text, primary_key=True),
    Column("tokens_entree", BigInteger, nullable=False, default=0),
    Column("tokens_sortie", BigInteger, nullable=False, default=0),
    Column("nb_appels", Integer, nullable=False, default=0),
    Column("cout_eur", Numeric(12, 6), nullable=False, default=0),
)


class BudgetLLMEpuise(RuntimeError):
    """Le plafond mensuel est atteint, ou le compteur est illisible."""


def cout_eur(modele: str, tokens_entree: int, tokens_sortie: int) -> float:
    tarif = next(
        (t for prefixe, t in TARIFS_USD_PAR_MILLION.items() if modele.startswith(prefixe)),
        TARIF_INCONNU,
    )
    return (tokens_entree * tarif[0] + tokens_sortie * tarif[1]) / 1_000_000


def mois_courant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class GardeBudget:
    def __init__(self, plafond_eur: float, session_factory):
        self.plafond_eur = plafond_eur
        self._session_factory = session_factory
        self._deja_signale = False

    def depense_du_mois(self) -> float:
        with self._session_factory() as session:
            valeur = session.execute(
                select(usage_llm.c.cout_eur).where(usage_llm.c.mois == mois_courant())
            ).scalar_one_or_none()
        return float(valeur or 0.0)

    def verifier(self) -> None:
        """Lève `BudgetLLMEpuise` si l'appel ne doit pas partir."""
        try:
            depense = self.depense_du_mois()
        except Exception as exc:
            raise BudgetLLMEpuise(
                f"compteur de budget LLM illisible ({type(exc).__name__}) — appel "
                "bloqué par précaution (migration 0009_usage_llm appliquée ?)"
            ) from exc
        if depense >= self.plafond_eur:
            if not self._deja_signale:
                # Une seule alerte forte par run : le reste du run échouerait à
                # l'identique des centaines de fois.
                logger.error(
                    "Budget LLM du mois atteint (%.4f € sur %.2f €, %s) — plus aucun "
                    "appel Claude jusqu'au mois prochain. Plafond réglable via %s.",
                    depense, self.plafond_eur, NOM_ENV_BUDGET, NOM_ENV_BUDGET,
                )
                self._deja_signale = True
            raise BudgetLLMEpuise(
                f"budget LLM mensuel atteint ({depense:.4f} € / {self.plafond_eur:.2f} €)"
            )

    def enregistrer(self, modele: str, tokens_entree: int, tokens_sortie: int) -> None:
        """Inscrit la dépense d'un appel déjà effectué. Un échec d'écriture est
        journalisé, pas levé : l'appel est payé, perdre sa réponse n'y change rien
        — et le prochain `verifier()` dira si le compteur est devenu illisible."""
        cout = cout_eur(modele, tokens_entree, tokens_sortie)
        mois = mois_courant()
        try:
            with self._session_factory() as session:
                insertion = insert(usage_llm).values(
                    mois=mois, tokens_entree=tokens_entree, tokens_sortie=tokens_sortie,
                    nb_appels=1, cout_eur=cout,
                )
                session.execute(
                    insertion.on_conflict_do_update(
                        index_elements=[usage_llm.c.mois],
                        set_={
                            "tokens_entree": usage_llm.c.tokens_entree + tokens_entree,
                            "tokens_sortie": usage_llm.c.tokens_sortie + tokens_sortie,
                            "nb_appels": usage_llm.c.nb_appels + 1,
                            "cout_eur": usage_llm.c.cout_eur + cout,
                        },
                    )
                )
                session.commit()
        except Exception as exc:
            logger.error(
                "Dépense LLM de %.6f € NON inscrite (%s) — le compteur sous-estime.",
                cout, type(exc).__name__,
            )


def activer_budget(session_factory=None) -> GardeBudget:
    """À appeler au début de chaque point d'entrée qui appelle Claude."""
    from fakenews import llm

    if session_factory is None:
        from fakenews.db import SessionLocal as session_factory
    garde = GardeBudget(
        reel_depuis_env(NOM_ENV_BUDGET, BUDGET_MENSUEL_EUR_PAR_DEFAUT, 0.0, 1000.0),
        session_factory,
    )
    llm.garde_budget = garde
    return garde
