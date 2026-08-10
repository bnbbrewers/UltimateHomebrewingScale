# Déploiement MicroPython compilé en `.mpy`

## Contexte

Le projet déploie actuellement les sources Python runtime dans le filesystem
LittleFS du M5Dial. Le workflow
`.github/workflows/repack-firmware.yml` fabrique un staging, un ZIP de fichiers
applicatifs et un TAR différentiel. L’autoupdater extrait le TAR et applique une
liste de suppressions issue du manifeste.

Le firmware de base indique `V2.4.2`. Le dépôt UIFlow MicroPython fournit une
révision `2.4.2` correspondante, qui servira de provenance au compilateur
`mpy-cross`. Le point d’entrée du runtime est `main.py` et doit rester un
fichier source lisible par le démarrage UIFlow.

## Objectifs

- Déployer le code Python runtime sous forme de bytecode MicroPython `.mpy`.
- Utiliser exactement la même transformation pour le filesystem du firmware
  complet et pour les archives de mise à jour différentielle.
- Conserver `main.py` comme bootstrap.
- Conserver `config.py.example` et protéger `config.py`.
- Lorsqu’un `.mpy` est installé, supprimer uniquement son `.py` homonyme s’il
  existe.
- Supprimer les deux variantes (`.py` et `.mpy`) lorsqu’un fichier applicatif
  est réellement retiré du projet.
- Migrer automatiquement les appareils existants qui contiennent encore les
  sources `.py` lors de la première release compilée.
- Ne pas versionner les artefacts `.mpy` générés.

## Hors périmètre

- Modifier le bootloader ou le firmware natif M5Dial.
- Remplacer `main.py` par un `.mpy`.
- Compiler `config.py`, qui reste une configuration locale non versionnée.
- Supprimer globalement tous les `.py` du filesystem.
- Modifier le protocole GitHub Release ou le canal stable/prerelease.

## Architecture proposée

### Outil de staging

Créer `tools/build_runtime.py`. Cet outil sera la source unique de vérité pour
la préparation des fichiers déployables. Il prendra un répertoire source, un
répertoire staging et la version runtime à écrire dans `uhs-version.txt`.

Les règles de sélection actuelles seront conservées et complétées pour exclure
les outils de build eux-mêmes : `docs/`, `firmware/`, `.github/`, les fichiers
Markdown, `LICENSE`, `.gitignore`, les exemples non autorisés, les fichiers
d’icônes d’origine et `tools/`.

Pour chaque fichier retenu :

- `main.py` est copié tel quel.
- `config.py.example` est copié tel quel.
- Tout autre fichier `.py` est compilé en `.mpy` dans le même dossier relatif.
- `config.py` n’est jamais copié.
- Tout fichier non-Python retenu est copié sans transformation.

Le staging final ne doit contenir aucun `.py` applicatif autre que
`main.py` et `config.py.example`. L’outil échoue si cet invariant n’est pas
respectée ou si la compilation d’un fichier échoue.

### Compilateur

Le workflow construit `mpy-cross` depuis le dépôt officiel
`m5stack/uiflow-micropython`, tag `2.4.2`, correspondant à la version du
firmware de base. La CI ne doit pas installer une version flottante de
`mpy-cross`.

Le compilateur produit du bytecode portable MicroPython adapté au firmware
UIFlow ; aucun backend natif ou optimisation dépendant d’une autre architecture
ne sera activé pour les modules applicatifs.

### ZIP firmware

Le ZIP `UHS-app-files-<tag>.zip` est créé depuis le staging compilé. Il ne doit
contenir que les fichiers effectivement installables, avec les extensions
`.mpy` prévues et les exceptions documentées.

Le filesystem utilisé par `fs_packed.py` est le même staging. Le firmware
complet et le ZIP ne peuvent donc pas diverger sur la transformation Python.

## Construction du diff

Le workflow conserve la comparaison entre le tag courant et le tag de base,
mais traduit les chemins source en chemins d’artefacts :

- un `.py` applicatif ajouté ou modifié est ajouté au TAR sous son chemin `.mpy` ;
- `main.py` reste ajouté ou modifié sous `main.py` ;
- `config.py.example` reste un fichier `.py` direct ;
- un fichier non-Python modifié garde son chemin ;
- un fichier applicatif supprimé ajoute `foo.py` et `foo.mpy` aux suppressions
  explicites ;
- les fichiers supprimés qui sont protégés ne peuvent pas être ajoutés aux
  suppressions.

La première release utilisant `.mpy` est marquée comme migration de format et
inclut tous les modules Python compilés, même si leur source n’a pas changé
entre les deux tags. Cela garantit la conversion des appareils provenant d’une
release historique en `.py`. Les releases suivantes reviennent au diff des
seuls fichiers modifiés.

Le manifeste conserve `strategy: "tar-diff"` et ajoute les métadonnées de format
runtime nécessaires, notamment `runtime_format: "mpy"` et un indicateur de
migration initiale. Les suppressions explicites du manifeste concernent les
fichiers réellement retirés du projet ; la suppression du `.py` homonyme après
installation d’un `.mpy` reste automatique et n’est pas dupliquée dans cette
liste.

## Comportement de l’autoupdater

Dans `updater/tar_extract.py`, après le remplacement atomique réussi d’un
fichier dont le chemin se termine par `.mpy`, l’extracteur calcule le chemin
`.py` homonyme et tente de le supprimer.

- L’absence du `.py` est ignorée.
- `config.py` et `config.py.example` ne sont jamais supprimés par cette règle.
- Les chemins restent soumis aux validations de sécurité existantes.
- Le fichier `.mpy` nouvellement installé reste en place même si la suppression
  du `.py` échoue pour une raison autre que l’absence du fichier ; cette erreur
  doit être remontée pour que l’update ne soit pas déclaré silencieusement
  complet.

Dans `updater/workflow.py`, les suppressions explicites du manifeste continuent
de valider les listes et les chemins. Une suppression d’un fichier réellement
retiré peut viser les deux extensions. `config.py` et les données persistantes
protégées restent refusées.

## Compatibilité de démarrage

`main.py` reste présent dans le filesystem et continue à appeler `main()` au
démarrage. Ses imports Python résolvent les modules `.mpy` présents dans les
packages `apps`, `core`, `devices`, `api`, `netcore`, `storage`, `ui`, `i18n`,
`updater` et `webportal`.

Les modules de l’autoupdater sont eux-mêmes compilés, mais ils restent chargés
par `main.py` ou par le chemin de boot existant via leur nom de module habituel.

## Validation

Ajouter des tests hôte dans `tools/test_build_runtime.py` couvrant :

- la conversion `foo.py` → `foo.mpy` avec conservation du dossier ;
- la conservation de `main.py` et `config.py.example` ;
- l’exclusion de `config.py`, `tools/`, documentation et firmware ;
- la copie inchangée des fichiers non-Python ;
- l’échec sur une compilation ou un staging invalide ;
- la génération des chemins de migration et de suppression ;
- la première migration complète et les diffs post-migration.

Ajouter des tests hôte pour l’autoupdater couvrant :

- suppression du `.py` homonyme après installation d’un `.mpy` existant ;
- absence du `.py` homonyme ;
- protection de `config.py` et `config.py.example` ;
- suppression explicite des deux variantes d’un fichier retiré ;
- maintien du comportement atomique et des validations de chemins.

Le workflow doit échouer avant publication si le staging contient un `.py`
applicatif inattendu, si `main.py` ou `config.py.example` manque, ou si
`mpy-cross` n’est pas disponible depuis la révision épinglée.

## Documentation

Mettre à jour `README.md`, `INSTALLATION.MD` et `firmware/CustomFirmware.MD`
pour préciser que :

- le firmware et les updates déploient principalement des `.mpy` ;
- `main.py` reste le point d’entrée source ;
- `config.py.example` reste fourni et `config.py` reste local ;
- les appareils existants sont migrés par la première release `.mpy` ;
- les diffs suivants remplacent les `.mpy` et retirent le `.py` correspondant
  lorsqu’il existe.
