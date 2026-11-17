"""Les sources « buzz / réseaux » sont déclarées et bien formées (tâche salle #190)."""
from fakenews.scraper.sources_reddit import SUBREDDITS
from fakenews.scraper.sources_rss import RSS_SOURCES


def test_sources_rss_bien_formees_et_sans_doublon():
    urls = [s["url"] for s in RSS_SOURCES]
    assert len(urls) == len(set(urls))
    for s in RSS_SOURCES:
        assert s["nom"] and s["domaine_source"] and s["url"].startswith("http")


def test_sources_buzz_presentes():
    domaines = {s["domaine_source"] for s in RSS_SOURCES}
    assert {"knowyourmeme.com", "snopes.com"} <= domaines
    assert {"nottheonion", "OutOfTheLoop"} <= set(SUBREDDITS)
