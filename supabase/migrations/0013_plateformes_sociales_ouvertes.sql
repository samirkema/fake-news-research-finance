-- Sources sociales ouvertes : Hacker News, Lemmy, 4chan /biz/ et YouTube
-- (cf. src/fakenews/scraper/sociaux.py). Sans cette migration, rien ne plante :
-- chaque post est refusé par la contrainte et compté « ignoré » par le collecteur.
alter table articles drop constraint if exists ck_articles_plateforme;
alter table articles add constraint ck_articles_plateforme
    check (plateforme in ('rss', 'reddit', 'proposition', 'bluesky', 'mastodon',
                          'hackernews', 'lemmy', '4chan', 'youtube'));
