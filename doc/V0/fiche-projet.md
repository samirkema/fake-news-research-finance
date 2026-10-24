# Fiche résumé — Projet Fake News Research for Finance

## Objectif du projet
Projet de recherche non commercial : détecter les fake news, expliquer pourquoi elles sont trompeuses et étudier leur diffusion et leur impact informationnel, en particulier sur les marchés financiers.

> **Recentrage du 2026-10-24.** L'objectif initial prévoyait ensuite des stratégies de trading algorithmique fondées sur ces signaux. Il est abandonné : le projet reste un outil de recherche sur la désinformation, sans conseil d'investissement, sans exécution de trading et sans usage commercial des données collectées.

## Décisions prises

- **Démarrage simple** : un outil hebdomadaire qui scanne des articles et attribue un score de suspicion (0 = fiable, 100 = très suspect), avant d'ajouter du machine learning.
- **Pas de Twitter/X** : coût trop élevé (API officielle en pay-per-use depuis fév. 2026, ~0,005$/lecture, plafond 2M lectures/mois ≈ 10 000$). On se contente de **Reddit** (API officielle, tier gratuit correct) comme source réseau social.
- **Modèle propriétaire, pas seulement des LLM en ligne** : approche hybride retenue —
  1. Utiliser un LLM en ligne au début pour labelliser rapidement un premier corpus.
  2. Fine-tuner un modèle léger (BERT/RoBERTa/DistilBERT) sur ces labels + datasets publics (LIAR, FakeNewsNet, ISOT).
  3. Le modèle "maison" tourne ensuite en production sans coût récurrent par appel ; le LLM externe ne sert que ponctuellement (labellisation, cas ambigus).
- **Pas de trading** (décision du 2026-10-24) : le projet produit un score de suspicion et une mise en contexte, à des fins de recherche. Aucun mécanisme d'exécution de trading n'est prévu, ni maintenant ni plus tard.

## État actuel du code

on part de zéro

## Sources de données retenues

| Source | Statut | Coût |
|---|---|---|
| Flux RSS (Reuters, BBC, Le Monde, etc.) | Intégré | Gratuit |
| GDELT Project | À intégrer | Gratuit |
| Reddit API | À intégrer | Gratuit (tier de base) |
| Alpha Vantage (news sentiment + données marché) | Optionnel, non câblé à un bloc du pipeline actuel (cf. `doc/architecture.md`) | Gratuit en tier de base |
| yfinance (données marché pour étudier l'impact) | Non câblé : seulement envisagé pour la recherche sur l'impact des fake news, jamais pour trader (cf. `doc/architecture.md`) | Gratuit |
| Datasets ML : LIAR, FakeNewsNet, ISOT | À utiliser pour entraînement | Gratuit |

## Budget indicatif estimé

- Phase prototype actuelle : 0 à 20€/mois
- Phase avec Reddit + fine-tuning ML (Colab) : 50 à 150€/mois
- Pas de poste Twitter/X à budgétiser (abandonné)
- Le volume collecté n'étant pas plafonné (cf. `doc/userstories_scraper.md`), le poste de coût variable (appels LLM, US-07 évaluateur) est maîtrisé via un plafond d'appels par run hebdomadaire, pas via une limite de collecte (cf. `doc/userstories_évaluateur.md`).

## Prochaines étapes identifiées

1. Ajouter un module Reddit au script (r/wallstreetbets, r/stocks, r/investing pour la finance ; r/worldnews, r/news pour l'actualité générale) en parallèle du RSS
2. Construire un premier dataset labellisé (LLM en ligne pour bootstrap + datasets publics)
3. Fine-tuner un modèle léger (BERT/RoBERTa) sur ce dataset
4. Étudier, séparément du pipeline de détection, l'impact informationnel des fake news sur un panier restreint d'actifs (corrélation entre diffusion et mouvements de prix, via yfinance) — outil d'analyse a posteriori, jamais de recommandation ni d'exécution (cf. `doc/V1/2.1-liste-actifs-et-annotation.md`)
5. Automatiser le rapport hebdomadaire via GitHub Actions (workflow planifié, cf. `doc/architecture.md` et `doc/plan_implementation.md`)
