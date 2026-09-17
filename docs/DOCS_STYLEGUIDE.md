# DOCS_STYLEGUIDE.md — charte graphique du site de documentation UHS

Référence visuelle pour toutes les pages publiées sous `docs/` sur
`https://bnbbrewers.github.io/UltimateHomebrewingScale/` : guides d'installation
logicielle et matérielle, versions `en/` et `fr/`, et toute page ajoutée plus tard.

Ce document est la source de vérité. En cas de doute entre ce fichier et le code
existant, c'est ce fichier qui gagne.

---

## 1. Principes

- **Technique, pas artisanal.** Le projet est un objet électronique. Le ton visuel
  est celui d'une doc d'outil dev : sobre, dense, lisible, sans imagerie de
  brasserie artisanale.
- **Une seule feuille de style partagée.** Pas de framework, pas d'étape de build.
  GitHub Pages sert du statique.
- **Zéro JavaScript ajouté.** Le thème sombre passe par `prefers-color-scheme`, la
  navigation par ancres natives. Si une page a déjà du JS, on n'en ajoute pas.
- **Parité EN/FR stricte.** Les deux versions partagent exactement le même balisage
  et les mêmes classes ; seules les chaînes changent.

---

## 2. Jetons

À placer dans `docs/assets/css/uhs-docs.css`, en tête de fichier.

```css
:root {
  /* marque */
  --uhs-ink:        #0D0F12;
  --uhs-green:      #13A923;   /* houblon — aplats et graphiques */
  --uhs-amber:      #FBB500;   /* malt   — aplats et graphiques */
  --uhs-steel:      #C9CED6;   /* fût    — aplats et graphiques */

  /* déclinaisons lisibles en texte sur fond clair */
  --uhs-green-ink:  #0A7A16;
  --uhs-amber-ink:  #8A6200;
  --uhs-steel-ink:  #5A6270;

  /* surfaces */
  --uhs-bg:         #F4F4F2;
  --uhs-surface:    #FFFFFF;
  --uhs-surface-2:  #ECECE8;
  --uhs-border:     #E3E3DF;
  --uhs-border-strong: #CFCFC9;

  /* texte */
  --uhs-text:       #14171B;
  --uhs-text-muted: #5A5E65;
  --uhs-text-faint: #80858C;

  /* teintes de callout */
  --uhs-tint-green: #F1FAF2;
  --uhs-tint-amber: #FFF8E6;
  --uhs-tint-steel: #F2F4F7;

  /* code */
  --uhs-code-bg:    #0D0F12;
  --uhs-code-fg:    #EDEFF2;

  /* bouton primaire — s'inverse en thème sombre */
  --uhs-btn-bg:       #0D0F12;
  --uhs-btn-fg:       #FFFFFF;
  --uhs-btn-bg-hover: #252A32;

  /* typographie */
  --uhs-font-sans: "Space Grotesk", ui-sans-serif, system-ui, "Segoe UI", sans-serif;
  --uhs-font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  /* rythme */
  --uhs-space-1: 4px;   --uhs-space-2: 8px;   --uhs-space-3: 12px;
  --uhs-space-4: 16px;  --uhs-space-5: 24px;  --uhs-space-6: 32px;
  --uhs-space-7: 48px;  --uhs-space-8: 64px;

  --uhs-radius-sm: 8px;
  --uhs-radius:    14px;
  --uhs-radius-lg: 20px;
  --uhs-radius-pill: 999px;

  --uhs-shadow: 0 1px 2px rgba(13, 15, 18, .04), 0 8px 24px rgba(13, 15, 18, .06);

  --uhs-measure: 72ch;   /* largeur de lecture du texte courant */
  --uhs-page:   1120px;  /* largeur max du conteneur */
}

@media (prefers-color-scheme: dark) {
  :root {
    --uhs-bg:         #0D0F12;
    --uhs-surface:    #15181D;
    --uhs-surface-2:  #1D2128;
    --uhs-border:     #262B33;
    --uhs-border-strong: #343A44;

    --uhs-text:       #EDEFF2;
    --uhs-text-muted: #A2A8B2;
    --uhs-text-faint: #7C838D;

    --uhs-green-ink:  #3FD152;
    --uhs-amber-ink:  #FFC633;
    --uhs-steel-ink:  #A8B0BB;

    --uhs-tint-green: #101E13;
    --uhs-tint-amber: #211A08;
    --uhs-tint-steel: #161A20;

    --uhs-code-bg:    #05070A;

    --uhs-btn-bg:       #EDEFF2;
    --uhs-btn-fg:       #0D0F12;
    --uhs-btn-bg-hover: #FFFFFF;

    --uhs-shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  }
}
```

**Règle d'emploi des trois couleurs.** Vert, ambre et gris inox sont des couleurs
d'aplat, pas des couleurs de texte. Pour du texte ou une icône fine, utiliser la
variante `-ink`. Leur usage décoratif est limité aux emplacements décrits en §5.0.

---

## 3. Typographie

Deux familles, aucune autre.

- **Space Grotesk** — titres, texte courant, boutons, libellés d'interface.
- **JetBrains Mono** — code, valeurs techniques, surtitres, légendes, libellés de
  tableau, numéros d'étape.

Auto-hébergement dans `docs/assets/fonts/` en `woff2` (variable si disponible),
chargé par `@font-face` avec `font-display: swap`. Pas d'appel à `fonts.googleapis.com` :
la doc doit rester consultable hors ligne depuis un clone du dépôt.

| Rôle | Famille | Taille | Graisse | Interlignage | Interlettrage |
|---|---|---|---|---|---|
| `h1` | sans | `clamp(2rem, 4.4vw, 2.9rem)` | 700 | 1.05 | -0.035em |
| `h2` | sans | `clamp(1.5rem, 3vw, 1.9rem)` | 700 | 1.15 | -0.03em |
| `h3` | sans | 1.2rem | 700 | 1.25 | -0.02em |
| Surtitre (`.uhs-eyebrow`) | mono | 0.75rem | 700 | 1.2 | 0.22em, majuscules |
| Chapô (`.uhs-lede`) | sans | 1.15rem | 400 | 1.6 | normal, couleur `--uhs-text-muted` |
| Texte courant | sans | 1.0625rem (17px) | 400 | 1.65 | normal |
| Légende de figure | mono | 0.8rem | 400 | 1.5 | 0.02em, couleur `--uhs-text-muted` |
| Code | mono | 0.9em relatif | 400 | 1.55 | normal |

Le texte courant ne dépasse jamais `--uhs-measure`. Les figures, tableaux et blocs
de code peuvent aller jusqu'à `--uhs-page`.

---

## 4. Logo

Fichiers à déposer dans `docs/assets/logo/` :

```
uhs-logo-dark.svg          version complète, viewBox 120×120
uhs-logo-dark-small.svg    version simplifiée, ≤ 40 px
uhs-logo-dark-1024.png     og:image, README
uhs-logo-dark-512.png
uhs-logo-dark-256.png
uhs-logo-dark-192.png      manifest Android
uhs-logo-dark-180.png      apple-touch-icon
uhs-logo-dark-64.png
uhs-logo-dark-48.png
uhs-logo-dark-32.png       favicon
uhs-logo-dark-16.png       favicon
```

Balises à ajouter dans le `<head>` de chaque page :

```html
<link rel="icon" type="image/png" sizes="32x32" href="/UltimateHomebrewingScale/assets/logo/uhs-logo-dark-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/UltimateHomebrewingScale/assets/logo/uhs-logo-dark-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/UltimateHomebrewingScale/assets/logo/uhs-logo-dark-180.png">
<meta property="og:image" content="https://bnbbrewers.github.io/UltimateHomebrewingScale/assets/logo/uhs-logo-dark-1024.png">
```

**Deux emplacements dans la page, et deux seulement.**

1. **Le grand logo, à gauche du `h1`** dans le hero (§5.2). 132 px en desktop,
   84 px sous 720 px de large. C'est la présence principale de la marque sur la
   page ; il porte l'`aria-label` « Ultimate Homebrewing Scale » et n'est pas un
   lien.
2. **Le petit logo accompagné de `uhs`**, à gauche de la barre d'ancres collante
   (§5.3). 28 px, version `uhs-logo-dark-small.svg`, lié à la racine de la doc.
   C'est la marque qui reste visible au défilement. Le mot `uhs` disparaît sous
   720 px, le logo reste.

L'en-tête de page ne porte **pas** de logo : il ne contient que le sélecteur de
langue. Le pied de page reprend le petit logo à 24 px.

**Règles.** La tuile sombre est la seule version autorisée sur le site. Zone de
protection égale au quart du côté de la tuile sur les quatre bords. Taille minimale
32 px ; en dessous de 40 px, servir `uhs-logo-dark-small.svg`. Ne jamais recolorer
les trois barres, ne jamais retirer la tuile, ne jamais poser le logo sur un aplat
vert, ambre ou photographique.

---

## 5. Composants

Les pages actuelles contiennent déjà tous ces blocs. Il s'agit de leur donner des
classes stables et de les styler une fois pour toutes.

### 5.0 Marque tricolore (`.uhs-rule`)

Trois barres arrondies reprenant le motif du logo, dans l'ordre vert / ambre /
inox, de largeurs 14 / 24 / 18 px et de hauteur 6 px, gouttière 5 px.

```html
<span class="uhs-rule" aria-hidden="true"><i></i><i></i><i></i></span>
```

Placée juste avant chaque `h2`, et en tête du bloc de texte du hero, au-dessus du
surtitre. Toujours `aria-hidden` : elle ne porte aucune information.

Les trois couleurs se retrouvent ensuite, et uniquement, sur : les puces de la
bande de faits (§5.2), les pilules de la barre d'ancres (§5.3), le liseré haut des
cartes (§5.5), l'anneau des pastilles d'étape (§5.6) et la règle gauche des
callouts (§5.8). Partout ailleurs, l'interface reste en encre et gris.

Le surtitre du hero est la seule exception à la règle « pas de couleur en texte » :
il passe en `--uhs-green-ink`, dont le contraste est vérifié dans les deux thèmes.

### 5.1 En-tête (`.uhs-header`)

Barre haute fine, fond `--uhs-surface`, bordure basse 1px, contenu aligné à
droite. Elle ne contient que le sélecteur de langue — aucun logo, aucun titre.

**Sélecteur de langue (`.uhs-lang`)** — les drapeaux SVG existants
(`assets/flags/en.svg`, `fr.svg`) à 24×24, `border-radius: 4px`, opacité 0.55 au
repos, 1 au survol. La langue active porte `aria-current="true"`, opacité 1 et un
anneau `2px solid var(--uhs-green)` avec `outline-offset: 2px`. Ajouter un `title`
et un `aria-label` textuels : un drapeau seul n'est pas un nom de langue.

### 5.2 Hero (`.uhs-hero`)

Deux colonnes : le grand logo à gauche, le bloc de texte à droite.

```html
<div class="uhs-hero__head">
  <svg class="uhs-hero__logo" viewBox="0 0 120 120" role="img" aria-label="Ultimate Homebrewing Scale">…</svg>
  <div class="uhs-hero__text">
    <span class="uhs-rule" aria-hidden="true"><i></i><i></i><i></i></span>
    <p class="uhs-eyebrow">…</p>
    <h1>…</h1>
    <p class="uhs-lede">…</p>
    <div class="uhs-actions">…</div>
  </div>
</div>
```

`display: flex; align-items: flex-start; gap: var(--uhs-space-6)`. Le logo est en
`flex: none`, 132×132. Sous 720 px, la colonne passe en `flex-direction: column`
et le logo descend à 84 px, au-dessus du surtitre. Le bloc de texte reste borné à
`--uhs-measure`.

Viennent ensuite l'image d'illustration, puis la bande de faits.

**Boutons.** Les deux boutons sont des `inline-flex` avec une icône SVG en trait
de 2 px héritant de `currentColor`, `gap: 10px`, `padding: 13px 22px`,
`border-radius: --uhs-radius-pill`, `font-size: .975rem`, 600, bordure 1.5 px.

- Primaire `.uhs-btn` : fond `--uhs-btn-bg`, texte `--uhs-btn-fg`, ombre portée
  douce, flèche vers la droite. Au survol, le bouton monte d'1 px, l'ombre
  s'ouvre, la flèche avance de 3 px. Les jetons s'inversent en thème sombre :
  l'encre y serait invisible sur le fond de page, le bouton devient donc clair à
  texte encre.
- Secondaire `.uhs-btn--ghost` : fond `--uhs-surface`, texte `--uhs-text`, bordure
  `--uhs-border-strong`, aucune ombre, chevron vers le bas — il renvoie plus loin
  dans la même page, pas ailleurs. Au survol, la flèche descend de 2 px.

Toutes les transitions sont en `.15s ease` sur `transform`, `box-shadow` et
`background`, et tombent avec `prefers-reduced-motion`. Jamais plus de deux
boutons côte à côte.

**Bande de faits (`.uhs-facts`)** — grille de 3 colonnes (1 sur mobile), chaque
item avec un libellé mono `0.72rem` majuscule tracké en `--uhs-text-faint` et une
valeur en sans 1.05rem 600. Chaque libellé est précédé d'une puce ronde de 7 px :
vert, ambre, inox dans l'ordre des colonnes. Les valeurs techniques (`UHS-Setup`,
`http://192.168.4.1:8080/`) passent en mono. Séparateurs verticaux 1px en desktop,
aucun en mobile.

### 5.3 Barre d'ancres collante (`.uhs-toc`)

`position: sticky; top: 0; z-index: 20`, fond `--uhs-surface`, bordure haute et
basse 1px. Trois éléments sur une ligne :

```html
<nav class="uhs-toc" aria-label="On this page">
  <div class="wrap">
    <a class="uhs-toc__brand" href="/UltimateHomebrewingScale/" aria-label="Ultimate Homebrewing Scale — documentation home">
      <svg width="28" height="28">…</svg><span>uhs</span>
    </a>
    <div class="uhs-toc__sep" aria-hidden="true"></div>
    <ul>…</ul>
  </div>
</nav>
```

La marque est en `flex: none`, le mot `uhs` en Space Grotesk 700 bas de casse
(`letter-spacing: -0.05em`, 1.15rem), masqué sous 720 px. Le séparateur est un
filet vertical 1px en `align-self: stretch`.

Liens en pilules : mono `0.8rem`, `padding: 6px 12px`,
`border-radius: --uhs-radius-pill`, bordure **1.5 px colorée** cyclant vert /
ambre / inox sur les `li` via `:nth-child(3n+1)`, `(3n+2)`, `(3n)`. Le texte de
chaque pilule prend la variante `-ink` de sa bordure ; au survol, le fond prend la
teinte correspondante (`--uhs-tint-*`). Avec six ancres, le cycle se joue deux
fois et la barre reste lisible comme un ensemble.

En mobile, la liste défile horizontalement
(`overflow-x: auto; scrollbar-width: none`) pendant que la marque reste fixe à
gauche.

Ajouter `scroll-margin-top: 84px` sur toutes les cibles d'ancre pour que le titre
ne passe pas sous la barre collante.

### 5.4 Sections (`.uhs-section`)

`padding-block: var(--uhs-space-8)`, séparées par une règle 1px `--uhs-border`.
Chaque section commence par la marque tricolore (§5.0), puis un `h2` en
`--uhs-text`, puis une ligne d'intro en `--uhs-text-muted`.

### 5.5 Cartes de prérequis (`.uhs-cards` / `.uhs-card`)

Grille responsive `repeat(auto-fit, minmax(240px, 1fr))`, gouttière
`--uhs-space-5`. Carte : fond `--uhs-surface`, bordure 1px `--uhs-border`,
`border-radius: --uhs-radius`, `padding: var(--uhs-space-5)`, titre `h3`, corps
`0.95rem` en `--uhs-text-muted`. Liseré haut de 3 px cyclant vert / ambre / inox
via `:nth-child(3n+1)`, `(3n+2)`, `(3n)`. Pas d'ombre au repos ; `--uhs-shadow` au
survol uniquement si la carte est cliquable.

### 5.6 Étapes numérotées (`.uhs-steps` / `.uhs-step`)

Liste ordonnée, compteur masqué et remplacé par une pastille : 40×40, fond
`--uhs-ink`, texte blanc, mono 700, `border-radius: 50%`, bordure 3 px cyclant
vert / ambre / inox d'une étape à l'autre. Une règle verticale 2px `--uhs-border`
relie les pastilles entre elles ; elle s'arrête au dernier élément. Contenu décalé
de 64px à gauche, et en mobile la pastille passe au-dessus du titre, sans règle de
liaison.

### 5.7 Figures (`figure.uhs-figure`)

Image en `border-radius: --uhs-radius`, bordure 1px `--uhs-border`,
`max-width: 100%`, `height: auto`. Légende `figcaption` en mono, sous l'image.
**Tout `<img>` porte un `alt` descriptif et des attributs `width`/`height`** pour
éviter le décalage de mise en page — les captures du Dial sont lourdes.

Ne pas retoucher `img/PortalPage.png` : elle est régénérée par
`tools/render_portal_screenshot.py`. Si son cadrage change, corriger le script,
pas le fichier.

### 5.8 Callouts (`.uhs-note`)

Fond teinté, bordure 1px `--uhs-border`, règle gauche 3px en couleur pleine,
`border-radius: --uhs-radius-sm`, `padding: var(--uhs-space-4)`. Le libellé
(`Tip`, `Important`, `Browser support`…) est en gras dans le flux, coloré en
variante `-ink`, suivi du texte.

| Variante | Teinte | Règle et libellé | Usage |
|---|---|---|---|
| `.uhs-note--tip` | `--uhs-tint-green` | `--uhs-green` / `--uhs-green-ink` | astuce, raccourci |
| `.uhs-note--warn` | `--uhs-tint-amber` | `--uhs-amber` / `--uhs-amber-ink` | avertissement, risque de perte de données |
| `.uhs-note--info` | `--uhs-tint-steel` | `--uhs-steel-ink` | contexte, compatibilité navigateur |

Trois variantes, pas plus. La couleur ne porte jamais seule le sens : le libellé
textuel est obligatoire.

### 5.9 Tableaux (`.uhs-table`)

`width: 100%`, `border-collapse: collapse`. En-tête en mono `0.75rem` majuscule
tracké, couleur `--uhs-text-muted`, bordure basse 2px `--uhs-border-strong`.
Lignes séparées par 1px `--uhs-border`, aucune bordure verticale, pas de zébrage.
`padding: var(--uhs-space-3) var(--uhs-space-4)`, alignement en haut. Première
colonne à 34 % en desktop. Enrober chaque tableau dans
`<div class="uhs-table-wrap">` avec `overflow-x: auto` — le tableau du portail
déborde sur téléphone.

### 5.10 Code

Inline : `padding: 2px 6px`, fond `--uhs-surface-2`, bordure 1px `--uhs-border`,
`border-radius: 6px`, mono `0.9em`. Utilisé pour les SSID, chemins, clés de
configuration, adresses.

Bloc : fond `--uhs-code-bg`, texte `--uhs-code-fg`,
`border-radius: --uhs-radius`, `padding: var(--uhs-space-5)`, `overflow-x: auto`,
`font-size: 0.875rem`. Pas de coloration syntaxique : pas de dépendance JS pour ça.

### 5.11 Dépannage (`.uhs-troubleshoot`)

Liste de définitions : symptôme en `dt` sans 600, remède en `dd` en
`--uhs-text-muted`, séparés par 1px `--uhs-border`. Pas d'accordéon, pas de JS.

### 5.12 Pied de page (`.uhs-footer`)

Bordure haute 1px, fond `--uhs-surface-2`, mono `0.8rem`. Petit logo 24 px, lien
vers le dépôt, mention GPL-3.0, lien vers l'autre langue.

---

## 6. Responsive

Approche mobile d'abord, trois paliers.

| Palier | Largeur | Effet |
|---|---|---|
| base | < 640px | une colonne, pastilles d'étape au-dessus du titre, faits empilés |
| `sm` | ≥ 640px | faits sur une ligne avec séparateurs, cartes en 2 colonnes |
| `md` | ≥ 720px | hero en deux colonnes avec le logo 132 px, `uhs` visible dans la barre d'ancres |

Conteneur : `width: min(100% - 2 * var(--uhs-space-5), var(--uhs-page)); margin-inline: auto;`.

---

## 7. Accessibilité

- Contraste minimal 4.5:1 pour le texte, 3:1 pour les éléments d'interface, dans
  les deux thèmes. Les jetons `-ink` sont calculés pour ça ; ne pas utiliser
  `--uhs-green` ou `--uhs-amber` bruts sur fond clair.
- `:focus-visible { outline: 2px solid var(--uhs-green); outline-offset: 2px; }`
  sur tout élément interactif. Ne jamais supprimer l'outline sans remplacement.
- Lien d'évitement `.uhs-skip` en tête de `<body>`, visible au focus, pointant vers
  `#main`.
- Hiérarchie de titres continue : un seul `h1`, pas de saut de niveau.
- `@media (prefers-reduced-motion: reduce)` : transitions et `scroll-behavior:
  smooth` désactivés.
- `<html lang="en">` ou `lang="fr"` selon la version ; les liens de langue portent
  `hreflang`.

---

## 8. Structure des fichiers

```
docs/
  assets/
    css/uhs-docs.css          feuille unique, importée par toutes les pages
    fonts/                    Space Grotesk + JetBrains Mono en woff2
    logo/                     fichiers listés en §4
    flags/                    en.svg, fr.svg (existants)
  SoftwareInstallationGuide/
    index.html                redirection vers en/
    en/index.html
    fr/index.html
    img/
  HardwareInstallationGuide/
    ...même structure
  index.html                  page d'accueil de la doc
```

---

## 9. Consignes d'implémentation

À l'attention de l'agent qui applique cette charte :

1. Écrire `docs/assets/css/uhs-docs.css` en premier, avec le bloc de jetons de la
   §2, puis les composants de la §5 dans cet ordre.
2. Reprendre le balisage existant des guides et lui appliquer les classes ci-dessus
   **sans réécrire le contenu rédactionnel** : aucun texte de la doc ne change.
3. Traiter les deux langues dans la même passe et vérifier que les deux fichiers
   ont un balisage identique à la chaîne près.
4. Appliquer ensuite la même charte au guide matériel et créer la page d'accueil
   `docs/index.html` qui pointe vers les deux guides.
5. Ne pas introduire de dépendance externe : pas de CDN, pas de Google Fonts, pas
   de bibliothèque JS, pas de Jekyll.
6. Vérifier en fin de passe : chaque page valide en HTML, chaque image a un `alt`,
   chaque ancre a son `scroll-margin-top`, le rendu tient en thème clair et sombre,
   et la page reste lisible à 320px de large.

---

## 10. À éviter

- Dégradés, ombres portées marquées, effets de verre.
- Le trio vert / ambre / inox en dehors des emplacements prévus en §5.0. Il ne
  colore ni les titres, ni les fonds de section, ni les boutons.
- Les couleurs pures `--uhs-green` et `--uhs-amber` en texte : elles ne servent
  qu'en aplat. Tout ce qui est lu passe par les variantes `-ink`.
- Un logo dans l'en-tête de page : il vit dans le hero et dans la barre d'ancres.
- Emoji en guise d'icône dans les callouts ou les titres.
- Icônes de bière, houblon, tonneau ou épi de blé en illustration : le vocabulaire
  brassicole vit dans les trois couleurs et dans le logo, nulle part ailleurs.
- Toute police autre que Space Grotesk et JetBrains Mono.
- Largeur de ligne au-delà de 72 caractères pour le texte courant.
