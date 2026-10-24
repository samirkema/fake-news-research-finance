-- Posts de réseaux sociaux : Bluesky (recherche publique) et Mastodon (flux RSS
-- par hashtag), cf. src/fakenews/scraper/bluesky.py et sources_rss.py.
-- Sans cette migration, le code ne plante pas : chaque post est refusé par la
-- contrainte puis compté « ignoré » par le collecteur.
alter table articles drop constraint if exists ck_articles_plateforme;
alter table articles add constraint ck_articles_plateforme
    check (plateforme in ('rss', 'reddit', 'proposition', 'bluesky', 'mastodon'));
