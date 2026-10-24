"""Recherches Bluesky suivies (cf. scraper/bluesky.py).

Liste modifiable sans toucher au code de collecte. Recherche publique de
api.bsky.app : gratuite, sans compte, contrairement à l'API Reddit (accès sur
demande depuis novembre 2025).
"""

RECHERCHES = [
    # -- Finance --
    "stock market",
    "stocks",
    "crypto",
    "earnings",
    # -- Actualité --
    "breaking news",
]

# 25 × 5 recherches ≈ 100 posts/jour : avec Mastodon (~100) et le RSS (~140), on reste
# près du plafond de l'évaluateur (EVALUATEUR_PLAFOND_ARTICLES, 300 par run).
NB_POSTS_PAR_RECHERCHE = 25
