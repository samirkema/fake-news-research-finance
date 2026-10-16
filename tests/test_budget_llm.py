import pytest

from fakenews import llm
from fakenews.budget_llm import BudgetLLMEpuise, GardeBudget, cout_eur, usage_llm
from fakenews.llm import appeler_structure
from tests._llm_factice import BlocFactice, ClientFactice, ReponseFactice

SCHEMA = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}


class _Usage:
    def __init__(self, entree, sortie):
        self.input_tokens = entree
        self.output_tokens = sortie


class _ClientAvecUsage(ClientFactice):
    @property
    def messages(self):
        parent = self

        class _M:
            def create(self, **kwargs):
                parent.dernier_appel = kwargs
                r = ReponseFactice([BlocFactice("tool_use", {"x": 1})])
                r.usage = _Usage(1000, 500)
                return r

        return _M()


class _GardeEspion:
    def __init__(self, epuise=False):
        self.epuise = epuise
        self.enregistres = []

    def verifier(self):
        if self.epuise:
            raise BudgetLLMEpuise("épuisé")

    def enregistrer(self, modele, entree, sortie):
        self.enregistres.append((modele, entree, sortie))


@pytest.fixture
def garde_llm(monkeypatch):
    def _poser(garde):
        monkeypatch.setattr(llm, "garde_budget", garde)
        return garde

    return _poser


def test_cout_haiku():
    # 1 M tokens entrée à 1 $ + 1 M tokens sortie à 5 $
    assert cout_eur("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == pytest.approx(6.0)


def test_modele_inconnu_est_compte_au_tarif_haut():
    assert cout_eur("modele-futur", 1_000_000, 0) > cout_eur("claude-haiku-4-5", 1_000_000, 0)


def test_appel_enregistre_apres_succes(garde_llm):
    garde = garde_llm(_GardeEspion())
    appeler_structure(_ClientAvecUsage(), "s", "p", SCHEMA, model="claude-haiku-4-5")
    assert garde.enregistres == [("claude-haiku-4-5", 1000, 500)]


def test_budget_epuise_bloque_avant_l_appel(garde_llm):
    garde_llm(_GardeEspion(epuise=True))
    client = _ClientAvecUsage()
    with pytest.raises(BudgetLLMEpuise):
        appeler_structure(client, "s", "p", SCHEMA)
    assert client.dernier_appel is None  # l'API n'a pas été appelée


def test_sans_garde_comportement_inchange():
    assert llm.garde_budget is None
    assert appeler_structure(ClientFactice(reponse_input={"x": 3}), "s", "p", SCHEMA) == {"x": 3}


def test_compteur_illisible_bloque_par_precaution():
    def _casse():
        raise RuntimeError("base injoignable")

    with pytest.raises(BudgetLLMEpuise):
        GardeBudget(2.0, _casse).verifier()


@pytest.fixture
def garde_reelle(db_session):
    usage_llm.create(db_session.get_bind(), checkfirst=True)
    return lambda plafond: GardeBudget(plafond, lambda: db_session)


def test_cumul_puis_blocage_au_plafond(garde_reelle, db_session):
    garde = garde_reelle(0.01)
    garde.verifier()  # rien de dépensé
    garde.enregistrer("claude-haiku-4-5", 1_000_000, 0)  # 1 €
    garde.enregistrer("claude-haiku-4-5", 1_000_000, 0)
    ligne = db_session.execute(usage_llm.select()).one()
    assert ligne.nb_appels == 2 and ligne.tokens_entree == 2_000_000
    assert float(ligne.cout_eur) == pytest.approx(2.0)
    with pytest.raises(BudgetLLMEpuise):
        garde.verifier()


def test_sous_le_plafond_laisse_passer(garde_reelle):
    garde = garde_reelle(2.0)
    garde.enregistrer("claude-haiku-4-5", 1000, 500)
    garde.verifier()
