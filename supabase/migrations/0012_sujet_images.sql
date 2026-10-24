-- Photos des sujets : vignettes sur la page d'un sujet, image en grand au clic.
-- Octets stockés en base (pas d'URL externe). Écrit par le frontend, n'entre
-- dans aucun calcul de score. Retrait = masquage, comme le reste de la section.

create table if not exists sujet_images (
    id uuid primary key default gen_random_uuid(),
    sujet_id uuid not null references sujets (id) on delete cascade,
    type_mime text not null,
    donnees bytea not null,
    legende text not null default '',
    ajoute_par text not null,
    date_creation timestamptz not null default now(),
    retire_le timestamptz,
    retire_par text,
    constraint ck_sujet_images_mime check (type_mime in ('image/jpeg', 'image/png', 'image/webp')),
    constraint ck_sujet_images_retrait_trace check (
        (retire_le is null and retire_par is null)
        or (retire_le is not null and retire_par is not null)
    )
);
create index if not exists idx_sujet_images_sujet on sujet_images (sujet_id, date_creation);
