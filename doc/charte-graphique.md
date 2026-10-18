# Charte graphique

Inspirée de la presse économique (The Economist, Financial Times) : sobre, typographique, une seule couleur d'accent. Le site analyse des informations, il doit inspirer le sérieux — pas la décoration.

## Principes

1. **Peu de couleurs** : un fond, une encre, des gris, **un seul accent** (rouge éditorial). Pas de bleu de lien générique.
2. **La typographie porte la hiérarchie** : titres en serif, texte d'interface en sans-serif, filets fins plutôt que cadres et ombres.
3. **La couleur signifie quelque chose** : le rouge d'accent marque la marque, les liens et l'action principale. Les couleurs d'état (erreur, succès) restent discrètes et réservées aux messages.
4. **Lisibilité** : contraste AA minimum, largeur de lecture ≤ 960 px, interligne 1,55.

## Palette (variables CSS dans `base.html`)

| Variable | Valeur | Usage |
|---|---|---|
| `--papier` | `#fbf8f3` | fond de page (crème) |
| `--encre` | `#1b1b1b` | texte principal, titres |
| `--gris` | `#5c5c5c` | texte secondaire, aides, métadonnées |
| `--filet` | `#d9d4ca` | filets, bordures de tableaux et champs |
| `--accent` | `#b0121b` | marque, liens, bouton principal |
| `--accent-fonce` | `#7e0d14` | survol de l'accent |
| `--alerte-fond` | `#f3ecd9` | bandeau d'avertissement |
| `--erreur` / `--succes` | `#9b1c1c` / `#1f5130` | messages d'état uniquement |

## Typographie

- Titres, nom du site, titres d'articles : `Georgia, "Times New Roman", serif`.
- Interface, tableaux, formulaires, métadonnées : `system-ui, sans-serif`.
- Métadonnées (dates, domaines, en-têtes de tableau) : petites capitales espacées (`text-transform: uppercase`, `letter-spacing`), taille 0,75 rem.

## Composants

- **En-tête** : nom du site en serif centré, filet épais encre au-dessus, filet fin en dessous, puis la navigation.
- **Tableaux** : pas de fond, uniquement des filets horizontaux ; en-têtes en petites capitales grises.
- **Score** : affiché en chiffres serif gras ; l'accent rouge n'est pas utilisé pour le score (il ne doit pas suggérer un jugement au-delà de la valeur).
- **Boutons** : fond accent, texte blanc, angles à peine arrondis (2 px).
- **Avertissement** : fond `--alerte-fond`, filet gauche accent, texte sobre.
- **Commentaires des lecteurs** : séparés du contenu système par un filet et une aide explicite (US-08) ; un commentaire retiré reste atténué.

## Règles de maintenance

- Toute nouvelle couleur doit d'abord être ajoutée ici et en variable CSS ; pas de nouvelle valeur hexadécimale en dur en dehors du bloc `:root` (les teintes de fond des messages d'état et le blanc des champs sont les seules exceptions actuelles).
- Le CSP autorise `style-src 'self' 'unsafe-inline'` : le CSS reste dans la balise `<style>` de `base.html` (et de `login.html`, page autonome).
