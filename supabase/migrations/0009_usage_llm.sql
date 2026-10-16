-- Budget LLM mensuel (cf. src/fakenews/budget_llm.py) : une ligne par mois civil
-- (UTC), incrémentée après chaque appel Claude. Sert de coupe-circuit : le
-- pipeline cesse d'appeler l'API une fois le plafond mensuel atteint (2 € par
-- défaut). Table hors fakenews.models volontairement : le frontend ne la lit pas,
-- et un code déployé en avance sur cette migration ne doit pas faire échouer
-- verifier_schema — seuls les appels LLM s'arrêtent (fail-closed) tant qu'elle
-- manque.

create table if not exists usage_llm (
    mois text primary key,
    tokens_entree bigint not null default 0,
    tokens_sortie bigint not null default 0,
    nb_appels integer not null default 0,
    cout_eur numeric(12, 6) not null default 0,
    maj_le timestamptz not null default now(),

    constraint ck_usage_llm_mois check (mois ~ '^[0-9]{4}-[0-9]{2}$')
);

-- Même précaution que salle_messages : pas lisible par l'API REST publique.
alter table usage_llm enable row level security;
