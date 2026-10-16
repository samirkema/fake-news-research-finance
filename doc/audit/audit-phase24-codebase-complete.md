# Audit phase 24 — Codebase complète (focus : salle des agents, triage, pipeline réactivé)

Date : 2026-10-15 · Scope : dépôt entier à `HEAD` (`b26e680`), arbre de travail.
Accent mis sur ce qui n'a **jamais été audité** : la salle des agents (`salle/`,
migration `0008`, `agent_salle.yml`), l'extraction des mails (`fakenews.product`),
le triage quotidien, la réactivation du pipeline (2026-10-14) et les agents
GitHub. Le frontend et le cœur du pipeline, audités aux phases 14 à 23, ont été
revérifiés par échantillonnage et par la suite de tests.

Base d'exigences : `README.md`, `doc/V0/architecture.md`, `doc/V3/`,
`doc/organisation_agents.md`, `.claude/agents/*.md`, audits 14 à 23.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Le triage quotidien relit huit jours de forum et trente jours de mails : chaque retour sera publié jusqu'à trente fois. Et le frontend se dit toujours « en lecture seule ». |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Un seul mail au charset exotique et la boîte entière disparaît — remplacée par « Aucun retour », exit 0. Les tests ne touchent jamais ce chemin. |
| Architecture (Steve Jobs) | 🔴 Bloquant | Le workflow ordonne aux agents de pousser et d'ouvrir une PR ; les fichiers d'agents qu'il leur dit d'appliquer « exactement » le leur interdisent. Deux règles, une seule exécution. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant (sous réserve) | « Ne pousse jamais sur main » est une phrase dans un prompt, pas un contrôle. Le runner a `contents: write` et un shell. |

**Verdict global : AUDIT_FAIL.** 0 Critique · 2 High · 5 Medium · 9 Low
(dédupliqués). Un High est confirmé (F24-01), l'autre est un **[RISQUE]** dont la
levée dépend de réglages GitHub/Vercel invisibles depuis le dépôt (F24-02).

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | triage, salle, collecte | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Requirements Compliance Auditor | plan V3 (collecte), organisation agents | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| Doc-Sync Auditor | README, docstrings, workflows | 0 | 0 | 1 | 2 | AUDIT_FAIL |
| A11y/UX Checker | page salle | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `salle/`, `product/` | 0 | 0 | 0 | 1 | AUDIT_PASS |
| Fail-Loud Auditor | extraction des mails | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Test Quality Auditor | `test_salle`, `test_extraire_mails` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | `salle/app.py`, `extraire_mails.py` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Layer Enforcer | salle ↔ produit, steps de workflow | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | workflows | 0 | 0 | 0 | 1 | AUDIT_PASS |
| SRE/Performance Auditor | cron, concurrence | 0 | 0 | 0 | 2 | AUDIT_PASS |
| Architecture Consistency Auditor | agents GitHub vs `.claude/agents/` | 0 | 1 | 0 | 1 | AUDIT_FAIL |
| Contextual Threat Analyst | salle, agents, triage | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| SAST Scanner | `salle/`, collecte, frontend | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Supply Chain & Artifact Auditor | actions, dépendances | 0 | 0 | 0 | 1 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | mails, Vercel preview | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |

Les colonnes comptent chaque finding dans **chaque** sous-audit qui l'a relevé ;
le décompte global ci-dessus est dédupliqué par cause racine.

---

## Matrice Des Contrats Principaux

| Contrat | Source | Implémentation | Test | Statut |
| --- | --- | --- | --- | --- |
| Aucun agent ne push / n'ouvre de PR seul | `doc/organisation_agents.md:9`, `.claude/agents/*-dev.md:22-23`, `release-captain.md:18` | `agent_salle.yml:79-81` l'ordonne | — | ❌ F24-01 |
| Les agents ne poussent jamais sur `main` | `agent_salle.yml:81` (prompt) | aucun contrôle technique visible | — | ⚠️ F24-02 |
| Collecte : schéma http(s) revalidé, redirections limitées | `doc/V3/plan_implementation_crowdsourcing.md:197-200` | `propositions.py:167` (URL initiale seulement), `rss.py:80-83` | `test_collecte_propositions.py` (URL initiale) | ❌ F24-05 |
| Triage : retours de la période courante | `triage_hebdomadaire.yml:79`, `extraire_mails.py:34-35` | fenêtres 8 j / 30 j sur un cron quotidien | — | ❌ F24-03 |
| Boîte non lue ⇒ signalée, pas maquillée | `extraire_mails.py:11-12` (« dégradation propre ») | `[]` + exit 0 sur **toute** erreur | — | ❌ F24-04 |
| Salle : seul le CEO et les agents écrivent | `salle/app.py:3-6` | `_auteur` + 401 | `test_salle.py:36-58` | ✅ |
| Salle : un agent ne parle pas au nom du CEO | `salle/app.py:165-167` | auteur forcé dans `AGENTS` | `test_salle.py:56-58` | ✅ |
| Salle : plafond de lancements par tâche | `0008_salle.sql:10-12` | `salle/app.py:139-153` | `test_salle.py:76-83` | ✅ (race : F24-12) |
| Secrets isolés de Claude dans le triage | `triage_hebdomadaire.yml:32-33,60-63` | steps séparés, Claude sans Bash | — | ✅ |
| Suite complète sans skip | `ci.yml:47-50` | — | **441 passed, 0 skip** (base jetable) | ✅ |
| Le frontend se décrit tel qu'il est | F23-01 | `app.py:1-4`, `README.md:26,135` | — | ❌ (hérité) |

---

## Top Findings

- **[High] F24-01 · `.github/workflows/agent_salle.yml:56,79-81`** — le prompt
  ordonne « applique exactement `.claude/agents/<agent>.md` » puis « commit, push
  cette branche et ouvre une PR avec `gh pr create` ». Or ces fichiers l'interdisent
  en toutes lettres : `pipeline-dev.md:23`, `frontend-forum-dev.md:22`,
  `release-captain.md:18` (« `git push`, `git merge`, `gh pr create` … jamais »),
  et `product-triage` est « lecture seule, ne code jamais ». La doctrine de
  gouvernance se contredit elle-même : `doc/organisation_agents.md:9` (« Aucun
  agent ne push […] seul ») contre `:66` (« Il pousse une branche et propose une
  PR »). **Type : Corroboré.** Impact : le comportement d'un agent lancé depuis la
  salle n'est pas défini — soit il refuse (la salle ne livre rien), soit le prompt
  l'emporte et la règle « le CEO valide avant toute action visible » est
  silencieusement abrogée pour tout ce qui passe par la salle. Correction
  attendue : trancher une règle et l'écrire **à un seul endroit** — par ex. une
  section « Mode GitHub (salle) » dans chaque fichier d'agent, autorisant
  explicitement push sur `salle/tache-*` + PR, et `organisation_agents.md:9`
  amendé en conséquence.

- **[High] [RISQUE] F24-02 · `.github/workflows/agent_salle.yml:24-26,36,54,81`**
  — Élémentaire, et pourtant… le job donne à Claude `Bash`, un `GH_TOKEN` avec
  `contents: write` et `pull-requests: write`, alors que le workflow reconnaît
  lui-même que la consigne « peut venir d'un autre agent, c'est une entrée non
  fiable » (`:28-29`). La seule barrière vers `main` est la phrase « ne pousse
  jamais sur main » (`:81`). Scénario : un agent lit un contenu piégé (page
  scrapée pendant un test, texte d'issue, fil de la salle) puis exécute
  `git push origin HEAD:main` ; si Vercel déploie `main`, le code part en
  production avec `DATABASE_URL`. Second chemin, plus discret : chaque branche
  `salle/tache-*` poussée déclenche probablement un **déploiement preview**
  Vercel — si `DATABASE_URL` / `FRONTEND_PASSWORD` sont définies pour
  « All Environments », du code écrit par un agent tourne avec les secrets de
  production, ce que le commentaire `:28-29` prétend exclure. Rien dans le dépôt
  ne prouve ni n'infirme une protection de branche ou le périmètre des variables
  Vercel. Correction attendue : (1) règle de protection / ruleset sur `main`
  (PR obligatoire, pas de bypass pour `github-actions[bot]`) ; (2) variables
  sensibles Vercel restreintes à *Production* ou *Ignored Build Step* pour
  `salle/*` ; (3) consigner ces deux réglages dans `organisation_agents.md`
  comme préconditions vérifiées.

- **[Medium] F24-04 · `src/fakenews/product/extraire_mails.py:54,88,214-217`** —
  sonde : un mail `Content-Type: text/plain; charset=x-inconnu` lève
  `LookupError: unknown encoding` dans `message_vers_dict`. L'exception n'est pas
  rattrapée par mail ; elle remonte jusqu'au `except Exception` de `main`, qui
  écrit `[]` et sort en 0. **Un seul mail malformé efface toute la boîte** et le
  backlog affiche « Aucun retour ». Même sortie pour un mot de passe révoqué :
  le triage ne distingue pas « boîte vide » de « boîte illisible ». Vecteur
  d'abus : n'importe quel visiteur peut rendre la boîte de contact muette en
  envoyant un mail. Correction : `try/except` par message (mail ignoré et
  compté), `errors="replace"` sur un codec connu en repli (`LookupError` →
  `utf-8`), et écrire dans `mails.json` un marqueur d'échec que le prompt doit
  reporter dans le backlog.

- **[Medium] F24-03 · `.github/workflows/triage_hebdomadaire.yml:11,45` +
  `extraire_mails.py:36`** — le cron est quotidien, la fenêtre forum est de
  **8 jours** et celle des mails de **30 jours**, sans mémoire de ce qui a déjà
  été trié. Chaque commentaire réapparaît dans 8 issues « Backlog » successives,
  chaque mail dans 30. Le prompt parle encore des « retours de la semaine »
  (`:79`). **Type : Confirmé.** Correction : fenêtre alignée sur la cadence
  (25 h), ou dernier horodatage traité.

- **[Medium] F24-05 · `src/fakenews/scraper/propositions.py:167,180` +
  `scraper/rss.py:80-83`** — le plan exige pour la collecte des URL fournies par
  les utilisateurs « schéma http/https uniquement […] à revalider ici,
  redirections limitées » (`doc/V3/plan_implementation_crowdsourcing.md:197-200`).
  Le schéma n'est revalidé que sur l'URL **initiale** ; `urlopen` suit ensuite
  jusqu'à 10 redirections vers `http`, `https` **ou `ftp`** (sonde sur
  `HTTPRedirectHandler`). Aucun filtrage des adresses privées / lien-local.
  **Type : Écart documentaire + [RISQUE]** (impact borné : le fetch tourne sur un
  runner GitHub éphémère, et une proposition doit être acceptée par un
  contributeur). Correction : opener sans redirection automatique, ou handler
  qui revalide schéma et hôte à chaque saut.

- **[Medium] [RISQUE] F24-06 · `salle/app.py:81-89`** — le seul frein au
  bruteforce de `SALLE_CODE` est `time.sleep(1)` par requête : il ne borne pas le
  parallélisme (instances Vercel multiples), aucune longueur minimale n'est
  imposée (la doc dit seulement « long », `organisation_agents.md:70`). Or ce
  code ouvre le lancement d'agents qui écrivent dans le dépôt (cf. F24-02).
  Correction : refuser de démarrer si `len(SALLE_CODE) < 32` — une ligne, et
  l'entropie fait le reste.

- **[Medium] F23-01 (hérité, toujours ouvert) · `src/fakenews/frontend/app.py:1-4`,
  `README.md:26,135`** — « aucune route d'écriture » ; le module en compte dix
  (login/logout compris). Corroboré par le README qui répète « lecture seule ».

---

## Thèmes Transverses

- **Une règle par prompt, pas par contrôle.** F24-01, F24-02, F24-11 : les
  garde-fous des agents GitHub (« ne pousse jamais sur main », « ne recopie
  jamais l'adresse ») vivent dans du texte qu'un modèle lit, pas dans des
  permissions. Le projet a appliqué l'inverse partout ailleurs (secrets isolés
  par step, Claude sans Bash dans le triage) — la salle est l'exception.
- **« Dégradation propre » qui devient silence.** F24-04 reproduit un défaut que
  les audits 7 et 10 avaient déjà chassé dans le pipeline : un échec total
  présenté comme un résultat vide.
- **La cadence a changé, pas les fenêtres.** F24-03, F24-08 : le passage
  hebdomadaire → quotidien a renommé les workflows mais pas les durées ni les
  commentaires qui en dépendent.

---

## Détails Par Division

### Division Métier (Anton Ego)

On m'avait promis un triage ; on me sert le même plat huit soirs de suite,
réchauffé, et trente pour les mails.

- **[Medium]** `triage_hebdomadaire.yml:45` : F24-03, doublons quotidiens.
- **[High]** `agent_salle.yml:79-81` : F24-01 — le contrat de gouvernance
  promet que le CEO valide avant toute action visible ; la salle l'abroge sans
  le dire.
- **[Medium]** `app.py:1-4` : F23-01, toujours là, toujours faux.
- **[Low]** `README.md:108` : F23-02, toujours ouvert — « `+ 0002, 0003` » alors
  que la CI applique huit migrations ; et la liste `README.md:88-95` s'arrête à
  `0007` (la `0008` n'est documentée que dans `organisation_agents.md:69`).

### Division Qualité (Gordon Ramsay)

Un mail. UN mail avec un charset inventé, et toute la boîte part à la poubelle
avec un sourire et un exit 0. C'est pas de la dégradation propre, c'est du
camouflage.

- **[Medium]** `extraire_mails.py:214-217` : F24-04.
- **[Low]** `extraire_mails.py:66-78` : `_strip_html` garde le contenu des
  balises `<style>` et `<script>` (sonde : `.a{color:red}alert(1)vrai texte`).
  Bruit dans le backlog, et texte arbitraire d'un expéditeur mélangé au corps.
- **[Low]** `tests/test_extraire_mails.py` : trois tests, tous sur la fonction
  pure. Aucun sur `main()` (secret absent, IMAP en échec, charset invalide),
  aucun sur `readonly=True`.

### Division Architecture (Steve Jobs)

Quatre fichiers d'agents disent non. Un workflow dit oui. Ce n'est pas une
architecture, c'est un malentendu avec un cron.

- **[High]** `agent_salle.yml:56` vs `.claude/agents/*.md` : F24-01.
- **[Low]** F24-07 · `.claude/agents/pipeline-dev.md:11`,
  `frontend-forum-dev.md:11`, `product-triage.md:12` ordonnent `graphify query`
  « avant de lire du code brut » ; sur GitHub, `graphify-out/` est ignoré
  (`.gitignore:20`) et `graphify` n'est pas installé (`agent_salle.yml:44-47`).
  `release-captain.md` délègue à `reviewer`, `architecture-critic` et au skill
  `audit-agent`, absents de `.claude/agents/` et inaccessibles (`Task` hors de
  `--allowedTools`, `agent_salle.yml:54`). Lancé depuis la salle, release-captain
  ne peut pas faire son métier.
- **[Low]** F24-08 · `keepalive_supabase.yml:4` justifie le job par « le pipeline
  hebdomadaire étant en pause » : le pipeline tourne chaque jour depuis le
  2026-10-14 (`pipeline_hebdomadaire.yml:6-9`) et touche la base. Le job n'est
  pas faux, son pourquoi l'est — garder, mais réécrire le commentaire (« utile
  quand le pipeline est remis en pause »).

### Division Cybersécurité Offensive (Sherlock Holmes)

- **[High] [RISQUE]** `agent_salle.yml:24-26,54,81` : F24-02 — push sur `main`
  et preview Vercel avec secrets de production.
- **[Medium] [RISQUE]** `salle/app.py:88` : F24-06 — bruteforce de
  `SALLE_CODE`.
- **[Medium]** `propositions.py:167` / `rss.py:82` : F24-05 — redirections
  non revalidées.
- **[Medium]** `extraire_mails.py:88` : F24-04 — n'importe qui peut rendre la
  boîte de contact muette.
- **[Low]** F24-11 · `extraire_mails.py:139` : l'adresse de l'expéditeur est
  écrite dans `mails.json` et remise à Claude ; seul le prompt
  (`triage_hebdomadaire.yml:83-84`) l'empêche de finir dans une issue GitHub.
  Minimisation à la source : ne pas l'extraire (le prompt n'en a pas besoin).

---

## Détails Par Sous-Audit

### Business Logic Auditor
- Verdict : AUDIT_FAIL
- Findings : F24-03 (doublons du triage).
- Points conformes : `poster` refuse de répondre à un message qui n'est pas la
  racine d'une tâche (`salle/app.py:131`) ; plafond de lancements cumulé par
  tâche (`:139-143`), testé.

### Requirements Compliance Auditor
- Verdict : AUDIT_FAIL
- Findings : F24-01 (gouvernance des agents), F24-05 (redirections, plan V3).
- Points conformes : US-04 crowdsourcing — schéma revalidé côté collecteur sur
  l'URL initiale, taille (`TAILLE_MAX_OCTETS`) et timeout bornés.

### Doc-Sync Auditor
- Verdict : AUDIT_FAIL
- Findings : F23-01 (Medium, hérité), F23-02 (Low, hérité, aggravé par `0008`),
  F24-08 (Low).
- Points conformes : `.env.example` documente toutes les variables lues par le
  code produit ; la salle documente ses quatre variables en tête de module
  (`salle/app.py:12-13`) et dans `organisation_agents.md:69-71`.

### A11y/UX Checker
- Verdict : AUDIT_PASS
- Findings : aucun significatif. Remarque : le champ de saisie de la salle n'a
  qu'un `placeholder` pour libellé (`salle/app.py:214`) — outil à usage unique
  du CEO, pas bloquant.
- Points conformes : thème sombre via `prefers-color-scheme`, `autofocus` sur le
  code. Manque mineur : pas d'attribut `lang` sur la page.

### Clean Code Auditor
- Verdict : AUDIT_PASS
- Findings : `_strip_html` naïf (Low, cf. Qualité).
- Points conformes : `salle/app.py` tient en 259 lignes, stdlib pour l'appel
  GitHub, aucune abstraction gratuite ; `poster.py` 41 lignes.

### Fail-Loud Auditor
- Verdict : AUDIT_FAIL
- Findings : F24-04.
- Points conformes : `salle/app.py:84-86` échoue bruyamment si `SALLE_CODE`
  manque ; le workflow agent poste « Run en échec » même si l'agent plante
  (`agent_salle.yml:83-88`, `if: always()`).

### Test Quality Auditor
- Verdict : AUDIT_PASS (réserves)
- Mesure : **441 passed, 0 skip**, 12 s, sur une base Postgres jetable créée
  puis supprimée, les huit migrations appliquées.
- Findings (Low) : `test_extraire_mails.py` ne couvre pas `main()` ;
  `test_salle.py` ne teste ni le chemin d'échec de `lancer_agent`
  (`salle/app.py:148-149`), ni la pagination `apres`, ni le filtre `tache` de
  `GET /api/messages` (un fil mélangeant deux tâches passerait).
- Points conformes : `test_salle.py` vérifie l'usurpation du CEO, le cookie
  forgé et le plafond avec une vraie base.

### Mutation/Saboteur Auditor
- Verdict : AUDIT_PASS (réserves)
- Mutations tuées (raisonnées) : retirer `nom != auteur` dans `mentions`
  (`test_salle.py:33`) ; retirer `deja +` du plafond (`test_salle.py:76-83`,
  le second agent serait lancé) ; inverser le test d'auteur agent (`:56-58`).
- Mutations survivantes : remplacer `readonly=True` par `False`
  (`extraire_mails.py:160`) ; supprimer le `try/except` de `main` ;
  supprimer `and (cast(:tache as bigint) is null or tache = :tache)`
  (`salle/app.py:180`) — `test_ordre_du_ceo_puis_echange_entre_agents` n'a
  qu'une tâche en base.

### Layer Enforcer
- Verdict : AUDIT_PASS
- Points conformes : la salle n'importe rien de `fakenews`, a son propre rôle
  Postgres limité à une table (`0008_salle.sql:21-32`) et RLS activée ;
  `DATABASE_URL` et `GMAIL_APP_PASSWORD` sont scopés à un step dans le triage.

### YAGNI Auditor
- Verdict : AUDIT_PASS
- Findings : F24-08 (keep-alive redondant tant que le pipeline tourne — garder
  comme filet, corriger le commentaire).

### SRE/Performance Auditor
- Verdict : AUDIT_PASS
- Findings (Low) :
  - F24-09 · `pipeline_hebdomadaire.yml:5-10` : pas de `concurrency` ; un
    déclenchement manuel pendant le run de 06:00 lance deux évaluateurs en
    parallèle — double dépense LLM, courses sur les mêmes articles. **[RISQUE]**
  - F24-12 · `salle/app.py:139,151` : lecture du compteur puis mise à jour, non
    atomiques ; deux messages simultanés peuvent dépasser le plafond de 10.
    **[RISQUE]**, borné par deux.
- Points conformes : `timeout-minutes` posé sur pipeline, triage et agents.

### Architecture Consistency Auditor
- Verdict : AUDIT_FAIL
- Findings : F24-01, F24-07.

### Contextual Threat Analyst
- Verdict : AUDIT_FAIL
- Scénarios :
  1. *Agent piégé* → push sur `main` ou preview Vercel avec secrets (F24-02).
  2. *Visiteur malveillant* → un mail au charset invalide masque tous les
     autres retours du jour (F24-04).
  3. *Contributeur négligent* → accepte une URL qui redirige vers `ftp://` ou
     une adresse interne du runner (F24-05).
  4. *Boucle d'agents* → bornée à 10 par tâche (✅), à 2 près (F24-12).
- Points conformes : l'issue « Backlog » est créée avec `GITHUB_TOKEN`, ce qui ne
  déclenche pas `claude.yml` même si un mail y fait écrire « @claude » — la
  chaîne mail → agent qui code est coupée par construction.

### SAST Scanner
- Verdict : AUDIT_FAIL
- Findings : F24-05.
- Points conformes : salle — rendu par `textContent`, seuls les liens `https://`
  deviennent des `<a>`, `Number(tache)` avant `innerHTML`
  (`salle/app.py:220-238`) : pas de XSS ; SQL entièrement paramétré ;
  `hmac.compare_digest` sur octets ; cookie `HttpOnly; Secure; SameSite=Strict`.
  `consigne` est injectée dans un `with: prompt`, jamais dans un `run:` : pas
  d'injection shell (`agent_salle.yml:61`).

### Supply Chain & Artifact Auditor
- Verdict : AUDIT_PASS
- Findings (Low) : F24-10 · `claude-code-action` est épinglée par SHA mais
  `actions/checkout@v4` et `actions/setup-python@v5` par tag, y compris dans
  des jobs `contents: write` (`agent_salle.yml:39,44`). Politique incohérente.
- Points conformes : modèle spaCy épinglé ; `pip freeze` archivé en CI ;
  `salle/requirements.txt` borné.

### Privacy/Exfiltration Auditor
- Verdict : AUDIT_PASS (réserves)
- Findings : F24-11 (adresses d'expéditeurs remises à Claude) ; volet preview
  Vercel de F24-02.
- Points conformes : IMAP `readonly=True` ; mot de passe jamais journalisé ;
  `mails.json` ignoré par git (`.gitignore:24`).
- Observation hygiène : trois fichiers non suivis et non ignorés à la racine
  (`images.jpeg`, `Tv-set-bar-…jpg`, `doc/Notice_Fake-News_Tracking_Base.pdf`) —
  à committer ou ignorer avant qu'un `git add .` d'agent ne décide à votre place.

---

## Points Conformes Importants

- Suite verte et complète : 441 tests, 0 skip, contre une vraie base.
- Migrations idempotentes (rejouées sans erreur, `if not exists` partout).
- Frontend : CSRF sur toutes les écritures, CSP et en-têtes de sécurité,
  documentation OpenAPI désactivée — inchangé depuis la phase 23.
- Triage : secrets confinés à leur step, Claude sans shell ni réseau.
- Salle : rôle Postgres dédié, RLS, pas de secret de production dans le job
  agent.

---

## Limites De Vérification Et Commandes

| Commande | Résultat |
| --- | --- |
| `git ls-files` | ✅ 150 fichiers suivis |
| `wc -l` sur sources, gabarits, migrations, workflows | ✅ 6 577 lignes |
| `git log` / `git diff` depuis la phase 23 | ⛔ **bloqué** (le `git` d'Xcode ne rend pas la main) — le delta depuis `8d0c05b` a été reconstitué par lecture, pas par diff |
| `graphify query` | ⛔ bloqué > 120 s, abandonné |
| `createdb` + 8 migrations + `pytest -q` + `dropdb` | ✅ 441 passed, 0 skip ; base jetable supprimée |
| Sonde `message_vers_dict` charset invalide | ✅ `LookupError` reproduit |
| Sonde `HTTPRedirectHandler` | ✅ schémas suivis : `http`, `https`, `ftp` |

Non vérifiable d'ici : protection de branche `main`, périmètre des variables
Vercel (Production / Preview), longueur réelle de `SALLE_CODE`, présence des
secrets `SALLE_*` et `CLAUDE_CODE_OAUTH_TOKEN`. Le frontend et le pipeline cœur
n'ont pas été relus ligne à ligne : leur conformité repose sur les phases 14-23
et sur la suite de tests.
