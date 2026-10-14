# Organisation de l'équipe d'agents

But : faire tourner le développement de ce projet comme une petite startup — le CEO (toi) pose les priorités et valide ce qui part en production, une équipe d'agents Claude Code fait le travail, et les retours des utilisateurs/clients (forum V3 : commentaires + propositions) nourrissent le backlog.

Ce document décrit qui fait quoi, comment un agent est déclenché, et où se trouve la limite entre "l'agent peut le faire seul" et "il faut ton feu vert".

## Principe non négociable

**Aucun agent ne push, ne merge, n'ouvre de PR ou n'écrit en base de production seul.** Un agent prépare (diff, branche locale, résumé) et s'arrête ; le passage à l'action irréversible attend ta validation explicite dans la conversation. C'est le rôle du CEO qui relit avant de signer — pas une limitation technique qu'on contournera plus tard.

## Rôles déjà en place (agents globaux, valables sur tous tes projets)

Définis dans `~/.claude/agents/`, donc pas dupliqués ici :

| Agent | Rôle |
|---|---|
| `reviewer` | Relit un diff, cherche bugs/régressions/sécurité/tests manquants |
| `architecture-critic` | Audit brutal de cohérence architecture/user stories/requirements (lecture seule, ne corrige rien) |
| `documentation-plan-p0-auditor` | Audit des docs/plans/user stories/preuves P0 |

Plus le skill `audit-agent` (cycle déjà noté dans ta mémoire : implémenter → audit-agent → corriger → re-auditer, sur base jetable) et le skill `ponytail-review` (chasse l'over-engineering).

## Nouveaux rôles, spécifiques à ce projet

Définis dans `.claude/agents/` (ce repo) — fichiers à relire et ajuster toi-même :

| Agent | Mandat | Déclenché par |
|---|---|---|
| [`product-triage`](../.claude/agents/product-triage.md) | Lit les propositions/commentaires non traités du forum (crowdsourcing V3), les reformule en items de backlog actionnables, sans jamais coder ni décider à ta place | Toi, ou un cron périodique (à activer plus tard si volume le justifie) |
| [`pipeline-dev`](../.claude/agents/pipeline-dev.md) | Développe/corrige le bloc Scraper → Évaluateur → Contextualiseur | Toi, sur un item de backlog précis |
| [`frontend-forum-dev`](../.claude/agents/frontend-forum-dev.md) | Développe/corrige le Frontend (FastAPI+Jinja2), les comptes/rôles, et le forum (commentaires + propositions) | Toi, sur un item de backlog précis |
| [`release-captain`](../.claude/agents/release-captain.md) | Rassemble un diff prêt, le fait relire par `reviewer`/`architecture-critic`/`audit-agent`, rédige le résumé de PR, et s'arrête avant tout push | Toi, quand un item de backlog est "terminé" côté dev |

## Le flux complet

```
Forum (commentaires / propositions, V3)
        │
        ▼
 product-triage  →  backlog (liste proposée, tu valides les priorités)
        │
        ▼
 pipeline-dev  ou  frontend-forum-dev   (le dev réel, sur un item)
        │
        ▼
 reviewer + architecture-critic + audit-agent   (revue croisée)
        │
        ▼
 release-captain  →  résumé de diff + description de PR
        │
        ▼
      TOI (CEO)  →  valide → push / merge / déploiement
```

## Comment déclencher un agent

- **Ponctuel** : `Agent({ subagent_type: "pipeline-dev", prompt: "..." })` — tu le demandes dans la conversation, comme aujourd'hui.
- **Pipeline multi-agents coordonné** (ex: triage puis dev puis revue en une fois) : outil `Workflow`, mais seulement si tu le demandes explicitement — ce n'est pas automatique.
- **Récurrent, ordinateur éteint** (activé le 2026-10-14, via GitHub Actions) :
  - lundi 06:00 UTC, `pipeline_hebdomadaire.yml` : collecte → notation → contextualisation ;
  - lundi 08:00 UTC, `triage_hebdomadaire.yml` : `product-triage` lit les retours forum de la semaine et publie une issue « Backlog » (la boîte mail n'est pas lisible depuis GitHub : la trier ici, dans la conversation) ;
  - à tout moment, `claude.yml` : commenter `@claude ...` dans une issue ou une PR (par ex. « @claude fais l'item 3 ») lance Claude Code sur GitHub, qui pousse une branche et propose une PR. Le merge reste ta décision.

## La salle des agents (remplace Slack)

Site séparé (`salle/`, projet Vercel distinct) : tu écris « @pipeline-dev fais X », l'agent est lancé sur GitHub (`agent_salle.yml`) et raconte chaque étape dans le fil de la tâche — plan, fichiers touchés, tests, bilan, lien de PR. Un agent peut en mentionner un autre, ce qui le lance aussi (10 lancements max par tâche). Il pousse une branche et propose une PR, jamais de merge.

Mise en service (une fois) :
1. Supabase, éditeur SQL : appliquer `supabase/migrations/0008_salle.sql`, puis `alter role salle password '<long mot de passe>';`.
2. Vercel : nouveau projet sur ce dépôt, *Root Directory* = `salle`. Variables : `SALLE_DATABASE_URL` (chaîne du pooler Supabase avec l'utilisateur `salle.<ref-projet>`), `SALLE_CODE` (ton code d'entrée, long), `SALLE_JETON` (aléatoire, pour les agents), `GITHUB_DISPATCH_TOKEN` (token fine-grained, ce seul dépôt, permission *Actions: Read and write*).
3. GitHub, secrets Actions : `SALLE_URL` (l'URL du projet Vercel) et `SALLE_JETON` (même valeur).

## Ce qu'on ne met pas en place maintenant

- Agents qui push/déploient sans validation — contraire au principe non négociable ci-dessus.
- Merge ou déploiement automatique d'une PR ouverte par `@claude` — contraire au principe non négociable ci-dessus.
- Un agent séparé par bloc (scraper / évaluateur / contextualiseur) — ils partagent assez de code et de patterns pour rester un seul agent `pipeline-dev` ; à splitter seulement si ça devient le goulot d'étranglement.
- Vote/notifications/karma côté forum — pas demandé, pas construit.

## Pour aller plus loin

Modifie directement les fichiers `.md` dans `.claude/agents/` : changer la `description` change quand Claude Code choisit l'agent automatiquement, changer le corps change son comportement. Pas besoin de redémarrer quoi que ce soit.
