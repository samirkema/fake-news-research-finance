# Audit phase 25 — Relecture des correctifs de la phase 24

Date : 2026-10-15 · Scope : les correctifs de F24-01, F24-03, F24-04, F24-05,
F24-06 et F23-01, non commités, sur `b26e680`. Fichiers touchés :
`.claude/agents/{pipeline-dev,frontend-forum-dev,release-captain}.md`,
`.github/workflows/{agent_salle,triage_hebdomadaire}.yml`, `README.md`,
`doc/organisation_agents.md`, `salle/app.py`, `src/fakenews/frontend/app.py`
(docstring), `src/fakenews/product/extraire_mails.py`,
`src/fakenews/scraper/rss.py`, et les tests `test_salle.py`,
`test_extraire_mails.py`, `test_collecte_propositions.py`.
Base d'exigences : le rapport de la phase 24 et les sources qu'il cite.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟢 OK | Une seule règle de gouvernance, écrite au même endroit dans les quatre sources. Le triage ne republie plus le même retour. |
| Qualité (Gordon Ramsay) | 🟢 OK | Chaque correctif a son test, et chaque test tue sa mutation (8 sur 8). Un test qui passait pour une mauvaise raison a été renforcé. |
| Architecture (Steve Jobs) | 🟡 Avertissement | L'exception « salle » est désormais écrite noir sur blanc. Elle rend plus urgente la protection de `main` (F24-02), qui reste ouverte. |
| Cybersécurité offensive (Sherlock Holmes) | 🟡 Avertissement | Redirections et code de la salle sont fermés. Deux résidus mineurs, et une précondition de déploiement à vérifier avant de pousser. |

**Verdict global : AUDIT_PASS avec réserves.** Les six findings visés sont
**fermés**. 0 Critique · 0 High · 0 Medium · 3 Low nouveaux (résiduels), plus
F24-02 (High [RISQUE]) et les Low de la phase 24 non traités, qui n'étaient pas
dans le périmètre de la correction.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | fenêtre du triage | 0 | 0 | 0 | 1 | AUDIT_PASS |
| Requirements Compliance Auditor | plan V3 collecte, gouvernance | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | README, docstring, organisation | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | non touché | — | — | — | — | n/a |
| Clean Code Auditor | correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | extraction des mails | 0 | 0 | 0 | 1 | AUDIT_PASS |
| Test Quality Auditor | nouveaux tests | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Mutation/Saboteur Auditor | 8 mutations | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | ouvreur HTTP partagé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | redirections bornées à 5 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Architecture Consistency Auditor | agents vs workflow | 0 | 0 | 0 | 0 | AUDIT_PASS (F24-02 ouvert) |
| Contextual Threat Analyst | salle, collecte, mails | 0 | 0 | 0 | 1 | AUDIT_PASS |
| SAST Scanner | `rss.py`, `salle/app.py` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | non touché | — | — | — | — | n/a |
| Privacy/Exfiltration Auditor | marqueur d'erreur publié en issue | 0 | 0 | 0 | 0 | AUDIT_PASS |

---

## Matrice De Fermeture

| Finding | Correctif | Preuve | Test | Mutation | Statut |
| --- | --- | --- | --- | --- | --- |
| F24-01 | Exception « salle » écrite dans la règle et dans chaque fichier d'agent ; le workflow ne demande de pousser qu'aux deux agents de dev | `organisation_agents.md:11`, `pipeline-dev.md:24`, `frontend-forum-dev.md:23`, `release-captain.md:18`, `agent_salle.yml:79-84` | — (texte) | — | ✅ Fermé |
| F24-03 | Fenêtre de 25 h pour le forum et les mails, filtre à l'heure près après `SEARCH SINCE` | `triage_hebdomadaire.yml:45-47`, `extraire_mails.py:34-38,185,211-212` | `test_fenetre_d_un_jour` | `if False:` → tué | ✅ Fermé |
| F24-04 | Charset inconnu → utf-8 ; mail illisible ignoré seul ; échec IMAP → marqueur `erreur_extraction` que le prompt reporte | `extraire_mails.py:46-57,206-213,244-251`, `triage_hebdomadaire.yml:81-84` | 4 tests | 4 mutations tuées | ✅ Fermé |
| F24-05 | Ouvreur dédié : schéma revalidé à chaque saut, 5 redirections max | `rss.py:73-91,104` | serveur HTTP local réel + appel direct du gestionnaire | 2 mutations tuées | ✅ Fermé (voir R25-03) |
| F24-06 | `SALLE_CODE` < 32 caractères ⇒ 500, à la connexion ET pour les cookies déjà émis | `salle/app.py:34-37,69-76` | `test_un_code_trop_court_ferme_la_salle` | `if not code:` → tué | ✅ Fermé |
| F23-01 | Docstring et README décrivent les écritures réelles | `frontend/app.py:1-9`, `README.md:26,135` | — | — | ✅ Fermé |

Vérification de la nouvelle docstring : les seules écritures du module visent
`Compte` (`app.py:659,1153` et promotion/rétrogradation), `Proposition`
(`:1371,1442`) et `Commentaire` (`:1551,1576`). « Aucune écriture dans les
tables du pipeline » est exact.

---

## Findings Résiduels

### R25-01 [Low] — Un run de triage manqué perd ses retours
- Preuve : `triage_hebdomadaire.yml:45-47`, `extraire_mails.py:34-38`
- Type : Confirmé (par construction)
- Impact : l'ancienne fenêtre de 8 jours, redondante, rattrapait un jour
  d'échec. Avec 25 h, si le run d'un jour échoue (quota, panne GitHub), ses
  retours ne seront jamais triés.
- Pourquoi c'est acceptable aujourd'hui : un échec de workflow se voit dans
  GitHub, et un déclenchement manuel le lendemain ne rattrape qu'une heure.
  C'est le compromis inverse de F24-03.
- Correction si ça devient un problème : mémoriser le dernier horodatage
  traité (ex. dans le corps de la dernière issue « Backlog ») plutôt qu'une
  fenêtre fixe.

### R25-02 [Low] — Un mail ignoré ne se voit que dans le journal Actions
- Preuve : `extraire_mails.py:208-210`
- Type : Confirmé
- Impact : un mail illisible est désormais isolé au lieu d'effacer la boîte
  (F24-04 fermé), mais il n'est signalé que par un `warning` dans le journal,
  que personne ne lit. Le backlog ne dit pas « 1 mail illisible ».
- Correction attendue : ajouter une entrée `{"mail_ignore": ...}` dans
  `mails.json`, reportée par le prompt.

### R25-03 [Low] [RISQUE] — Date du mail choisie par l'expéditeur, adresses internes non filtrées
- Preuve : `extraire_mails.py:211` filtre sur l'en-tête `Date`, écrit par
  l'expéditeur, pas sur la date d'arrivée (`INTERNALDATE` IMAP). Un mail retardé
  de plus de 25 h, ou dont l'horloge d'envoi est fausse, est écarté. Côté
  collecte, `rss.py:73-91` revalide le schéma mais pas l'hôte : une redirection
  vers `http://169.254.169.254/` reste suivie (inchangé depuis la phase 24, où
  cette moitié de F24-05 était déjà classée [RISQUE]).
- Impact : borné. Le runner GitHub est éphémère et les métadonnées Azure exigent
  un en-tête que `urllib` n'envoie pas.
- Correction si besoin : `FETCH (INTERNALDATE RFC822)` ; et refuser dans
  `redirect_request` les hôtes résolus en adresses privées ou lien-local.

---

## Détails Par Division

### Division Métier (Anton Ego)
La règle se contredisait ; elle se nuance désormais, et la nuance est écrite
partout où on la lit. Le principe non négociable admet une exception, la
salle, nommée, bornée, et répétée mot pour mot dans les fichiers d'agents.
`product-triage` et `release-captain` en sont explicitement exclus — l'oubli
qui aurait fait pousser l'agent de lecture seule a été évité.
- **[Low]** R25-01.

### Division Qualité (Gordon Ramsay)
Huit mutations, huit tuées. Et une a failli passer : le test de redirection
renvoyait `None` aussi avec le bug, parce qu'un `ftp://` vers un hôte bidon
échoue de toute façon. Un test qui passe pour la mauvaise raison, c'est un plat
qui sort chaud parce que la cuisine brûle. Corrigé : le test interroge
maintenant le gestionnaire directement.
- **[Low]** R25-02.

### Division Architecture (Steve Jobs)
L'ouvreur HTTP est un seul objet au niveau du module, partagé par le RSS et la
collecte — pas de nouvelle couche. Le RSS hérite de la même protection
gratuitement : ses sources sont codées en dur, il n'en avait pas besoin, il ne
la paie pas.
- **F24-02 reste ouvert.** L'exception formelle « les agents de dev poussent
  leur branche » rend la protection de `main` d'autant plus nécessaire : c'est
  désormais un comportement voulu qui ne repose que sur un prompt.

### Division Cybersécurité Offensive (Sherlock Holmes)
Élémentaire, et pourtant bien fermé : le code de la salle est vérifié aussi sur
les cookies déjà émis, donc raccourcir le code ne laisse pas d'anciennes
sessions vivre sur une clé faible. Les agents, authentifiés par jeton, ne
dépendent pas de `SALLE_CODE` et continuent de poster.
- **[Low] [RISQUE]** R25-03.
- Le marqueur `erreur_extraction` finit dans une issue GitHub : il contient
  le type et le message de l'exception IMAP (`[AUTHENTICATIONFAILED] …`), jamais
  le mot de passe, que `imaplib` n'inclut pas dans ses erreurs.

---

## Précondition De Déploiement (À Vérifier Avant De Pousser)

- **`SALLE_CODE` doit faire au moins 32 caractères sur Vercel.** Sinon, dès le
  déploiement, la salle refuse toute connexion du CEO (erreur 500 explicite).
  Les agents continuent de fonctionner. Je ne peux pas vérifier la longueur
  actuelle d'ici.

---

## Points Conformes

- Suite complète : **448 passed, 0 skip** (441 + 7 nouveaux tests), base Postgres
  jetable, les huit migrations appliquées, base supprimée ensuite.
- Le test historique du plafond de lecture (F19-07) patche désormais
  `rss._OUVREUR.open` : il exerce toujours le vrai `read(taille_max)`.
- Le nouveau test de redirection tourne contre un vrai serveur HTTP sur
  `127.0.0.1`, autorisé par la garde réseau de `conftest.py`.
- YAML des deux workflows modifiés validé (`yaml.safe_load`).

## Limites De Vérification Et Commandes

| Commande | Résultat |
| --- | --- |
| `pytest -q` sur base jetable | ✅ 448 passed, 0 skip |
| Balayage de mutations (8 mutants, script dans le scratchpad) | ✅ 8/8 tués après renforcement du test de redirection (7/8 au premier passage) |
| `yaml.safe_load` sur `agent_salle.yml`, `triage_hebdomadaire.yml` | ✅ |
| `git diff` / `git status` | ⛔ le `git` d'Xcode ne rend pas la main sur cette machine ; le périmètre ci-dessus est celui des fichiers modifiés pendant la correction |

Non vérifiable d'ici : longueur de `SALLE_CODE` en production, comportement
réel du prompt de triage face au marqueur `erreur_extraction` (non testable
sans lancer Claude), protection de branche (F24-02).
