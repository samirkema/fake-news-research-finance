-- Section « Sujets » : regrouper les fake news par thème, en débattre, et
-- publier des analyses de fond (évolution d'un sujet dans le temps).
--
-- Tables écrites par le frontend, comme `commentaires`. Aucune n'entre dans un
-- calcul de score. Les pseudos sont stockés en texte (pas de clé étrangère vers
-- `comptes`) : la trace doit survivre à la suppression d'un compte.

create table if not exists sujets (
    id uuid primary key default gen_random_uuid(),
    titre text not null,
    description text not null,
    cree_par text not null,
    date_creation timestamptz not null default now(),
    -- Retrait = masquage, comme pour les commentaires.
    retire_le timestamptz,
    retire_par text,
    constraint ck_sujets_titre_non_vide check (length(trim(titre)) > 0),
    constraint ck_sujets_description_non_vide check (length(trim(description)) > 0),
    constraint ck_sujets_retrait_trace check (
        (retire_le is null and retire_par is null)
        or (retire_le is not null and retire_par is not null)
    )
);
-- Un titre vivant par sujet, insensible à la casse.
create unique index if not exists uq_sujets_titre_lower
    on sujets (lower(titre)) where retire_le is null;

create table if not exists sujet_articles (
    sujet_id uuid not null references sujets (id) on delete cascade,
    article_id uuid not null references articles (id) on delete cascade,
    ajoute_par text not null,
    date_ajout timestamptz not null default now(),
    primary key (sujet_id, article_id)
);
create index if not exists idx_sujet_articles_article on sujet_articles (article_id);

-- Débat (tout compte connecté) et analyses de fond (contributeurs).
create table if not exists sujet_messages (
    id uuid primary key default gen_random_uuid(),
    sujet_id uuid not null references sujets (id) on delete cascade,
    genre text not null default 'debat',
    pseudo text not null,
    texte text not null,
    date_creation timestamptz not null default now(),
    retire_le timestamptz,
    retire_par text,
    constraint ck_sujet_messages_genre check (genre in ('debat', 'analyse')),
    constraint ck_sujet_messages_texte_non_vide check (length(trim(texte)) > 0),
    constraint ck_sujet_messages_retrait_trace check (
        (retire_le is null and retire_par is null)
        or (retire_le is not null and retire_par is not null)
    )
);
create index if not exists idx_sujet_messages_sujet on sujet_messages (sujet_id, date_creation);
create index if not exists idx_sujet_messages_pseudo on sujet_messages (pseudo, date_creation);
