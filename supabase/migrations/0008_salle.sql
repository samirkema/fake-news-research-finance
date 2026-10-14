-- Salle des agents : le fil où le CEO donne ses ordres et où les agents racontent
-- leur travail (site séparé, dossier salle/). Rien ici n'est lu par le produit.

create table if not exists salle_messages (
    id bigint generated always as identity primary key,
    -- Fil de la tâche : l'id du premier message (l'ordre initial du CEO).
    tache bigint references salle_messages (id),
    auteur text not null,
    texte text not null,
    -- Nombre d'agents réellement lancés par ce message : leur somme par tâche est
    -- plafonnée (cf. salle/app.py), sinon deux agents qui se mentionnent
    -- mutuellement se relanceraient sans fin, à nos frais.
    ordres smallint not null default 0,
    cree_le timestamptz not null default now(),

    constraint ck_salle_texte check (length(trim(texte)) > 0 and length(texte) <= 20000)
);

create index if not exists idx_salle_tache on salle_messages (tache, id);

-- Le site de la salle se connecte avec ce rôle, pas avec celui du produit : une
-- fuite de ses identifiants n'ouvre que cette table. Mot de passe à poser à la
-- main, jamais dans le dépôt :  alter role salle password '...';
do $$
begin
    if not exists (select from pg_roles where rolname = 'salle') then
        create role salle login;
    end if;
end $$;

grant usage on schema public to salle;
grant select, insert, update on salle_messages to salle;

-- RLS sans politique pour les autres rôles : la table n'est pas lisible par l'API
-- REST publique de Supabase (anon / authenticated).
alter table salle_messages enable row level security;
drop policy if exists salle_acces on salle_messages;
create policy salle_acces on salle_messages for all to salle using (true) with check (true);
