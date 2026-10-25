"""Sources sociales ouvertes (cf. scraper/sociaux.py). Modifiable sans toucher
au code de collecte. Volumes volontairement modestes : le pipeline tourne deux
fois par semaine et l'évaluateur note au plus EVALUATEUR_PLAFOND_ARTICLES
articles par run.
"""

# Hacker News (API Algolia, publique, sans clé) : recherches parmi les « stories ».
HACKERNEWS_RECHERCHES = ["stock market", "crypto", "SEC"]
HACKERNEWS_PAR_RECHERCHE = 15

# Lemmy (API ouverte de l'instance lemmy.world) : posts récents par communauté.
LEMMY_INSTANCE = "https://lemmy.world"
LEMMY_COMMUNAUTES = ["world", "news", "stocks", "cryptocurrency", "finance", "wallstreetbets"]
LEMMY_PAR_COMMUNAUTE = 15

# 4chan (API JSON en lecture seule, sans clé) : fils du catalogue de /biz/.
# Très bruité, mais riche en rumeurs crypto et finance.
QUATRECHAN_PLANCHE = "biz"
QUATRECHAN_NB_FILS = 25

# YouTube (Data API v3) : actif seulement si YOUTUBE_API_KEY est définie.
# Une recherche coûte 100 unités sur un quota gratuit de 10 000 par jour.
YOUTUBE_RECHERCHES = ["stock market news", "crypto news"]
YOUTUBE_PAR_RECHERCHE = 15
