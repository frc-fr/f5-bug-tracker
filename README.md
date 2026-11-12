# f5-bug-tracker

Site statique de suivi des bugs de F5 BIG-IP et F5OS et de leurs corrections, construit à partir des
notes publiques « Fixes and Known Issues » de F5, de son Bug Tracker public et de ses articles de cycle de vie.

Ce projet est indépendant. Il n'est pas affilié à F5, Inc.
Les informations sont fournies à titre indicatif : vérifiez toujours la documentation officielle.

## Fonctionnalités

- Trois logiciels, au choix en haut de page : BIG-IP (TMOS), F5OS-A, le système des appliances rSeries, et
  F5OS-C, celui des châssis VELOS. F5OS héberge les instances BIG-IP : ses bugs ne sont pas dans les notes
  de BIG-IP. Depuis 2.0, F5OS publie une seule note pour rSeries et VELOS : elle figure dans les deux.
- Recherche par numéro de bug (2201813, 2201813-3, BT2201813) ou mots-clés, par version, point release,
  plateforme et composant (Local Traffic Manager, TMOS, Access Policy Manager…)
- Toutes les branches publiées depuis BIG-IP 11.5, avec mise en avant des branches supportées, sans masquer les autres
- Comparaison de deux versions : bugs corrigés, nouveaux problèmes connus, problèmes toujours présents et
  changements de comportement (« Behavior Change ») des corrections traversées
- Onglet Matériel : dernière branche qui supporte chaque plateforme et fin du support logiciel
- Suivi des nouveautés, avec un flux RSS/Atom
- Interface en français et en anglais

Vos recherches et vos filtres restent dans votre navigateur : ils ne sont ni enregistrés ni transmis.

## Ce que disent les notes, et ce qu'elles ne disent pas

- F5 publie une page « Fixes and Known Issues » par version de maintenance (17.1.3) et par point release
  (17.1.3.7). Chaque page reprend les corrections des versions précédentes de sa ligne, puis les problèmes
  connus de la branche (« Known Issues in BIG-IP v17.1.x »).
- Depuis 16.1, chaque correction indique les versions qui la portent sur toutes les branches
  (« Fixed Versions »). Une correction en 17.1.3.6 vaut pour 17.1.3.7 et suivantes, pas pour 17.1.2.x ; elle
  ne vaut pour 17.1.4 que si F5 le dit. Les anciens hotfixes (« 12.1.2 Hotfix 2 ») sont les point releases
  d'aujourd'hui (12.1.2.2).
- Chaque bug est détaillé : composant, symptômes, conditions, impact, contournement, correctif, et
  changement de comportement quand la correction modifie le fonctionnement. Une étoile ★ signale, selon F5,
  un problème qui peut empêcher le chargement de la configuration ou dégrader les performances après une
  mise à niveau.
- Les notes ne rangent pas les bugs par plateforme. La plateforme n'est connue que lorsque le texte la cite
  (i5800, r5900, VIPRION B2250). Le filtre matériel est donc inclusif : avec une plateforme choisie, il garde
  les bugs qui la citent, ceux qui ne citent que sa famille et ceux qui ne citent aucun matériel.
- F5OS numérote ses versions 1.8.4, puis 1.8.4-HR-1 et 1.8.4-HR-2 (Hardened Releases), puis 1.8.4-CR
  (Critical Release), qui reprend les HR : ce sont les point releases de 1.8.4, dans cet ordre. Les notes
  F5OS ne donnent pas de « Fixed Versions » : une correction vaut pour sa version et les suivantes de sa
  branche, comme dans les anciennes notes BIG-IP.
- Les correctifs de sécurité sont écartés (tableaux « Vulnerability Fixes », titres de vulnérabilités) et les
  références CVE retirées des textes.

## Sources

- Pages « Fixes and Known Issues » sur `techdocs.f5.com`, dont le robots.txt autorise les robots, à une
  adresse prévisible, en quatre séries : `.../big-ip_ltm/.../relnote-supplement-bigip-17-1-3-7.html`,
  `.../f5os-a/.../relnote-supplement-f5os-a-1-8-4-hr-1.html`, `.../f5os-c/.../relnote-supplement-f5os-c-1-8-3.html`
  et, pour F5OS 2.x, `.../f5os/.../relnote-supplement-f5os-2-0-0.html`. Les versions viennent du sitemap de
  la base de connaissances (incomplet), des articles K9412 et K9502 pour BIG-IP et K21501912 pour F5OS, et
  d'une requête HEAD sur les numéros suivants des branches supportées. Le site répond 200 avec une page « Page not found »
  pour une version absente : elle est reconnue à sa taille. Les ETag changent à chaque déploiement du site :
  une page n'est téléchargée à nouveau que si sa taille change. Les pages des branches supportées sont
  vérifiées à chaque passage, les autres une fois par semaine. Deux secondes séparent deux requêtes.
- Chaque page reprend des milliers de bugs déjà publiés : l'extraction écrit un petit fichier par version,
  avec les seuls numéros par section (`data/extracted/releases/`), et un fichier unique des bugs, une ligne
  par bug, avec le texte de la page la plus récente qui le détaille (`data/extracted/bugs.json`).
- [Bug Tracker](https://cdn.f5.com/product/bugtracker/) public de F5, une page par bug : versions affectées
  connues, sévérité, dates d'ouverture et de modification. Une page par bug, lue une fois, puis à nouveau
  seulement si les notes ajoutent une version corrigée. Chaque passage lit un lot : la première collecte
  s'étale sur plusieurs passages. Résultat dans `data/extracted/bugtracker.json`.
- Articles publics de my.f5.com, dessinés en JavaScript et rendus par [Lightpanda](https://lightpanda.io),
  un navigateur sans interface. Un article n'est rendu à nouveau que si sa date de modification change dans
  le sitemap du portail. Résultat dans `sources/articles.json` ; un article illisible garde ses dernières
  valeurs.
  - [K5903](https://my.f5.com/manage/s/article/K5903) : dates de support de chaque branche.
  - [K9412](https://my.f5.com/manage/s/article/K9412) : date de publication et plateformes de chaque
    version de maintenance, pour les branches 17.x et suivantes.
  - [K9502](https://my.f5.com/manage/s/article/K9502) : dernière point release de chaque version.
  - [K4309](https://my.f5.com/manage/s/article/K4309) : cycle de vie de chaque plateforme (fin de vente, fin
    du support logiciel, fin du support technique).
  - [K2200](https://my.f5.com/manage/s/article/K2200) : versions actuelles de BIG-IP et F5OS.
  - [K21501912](https://my.f5.com/manage/s/article/K21501912) : dates de support des branches F5OS (LTS
    trois ans, STS un an).
  - [K86001294](https://my.f5.com/manage/s/article/K86001294) : versions F5OS supportées par chaque
    plateforme rSeries et VELOS, et versions BIG-IP acceptées en instance.

## Mise à jour

Un traitement GitHub Actions s'exécute du lundi au vendredi à 9 h 15, 14 h 15 et 19 h 00, heure de
Paris, et sur lancement manuel. Il collecte, extrait, contrôle, lit un lot du Bug Tracker, puis publie le
site sur GitHub Pages. Si un contrôle échoue, le site garde ses dernières données valides.

## Liens utiles chez F5

- [K13845](https://my.f5.com/manage/s/article/K13845) : chemins de mise à niveau de BIG-IP
- [K9476](https://my.f5.com/manage/s/article/K9476) : matrice matériel / logiciel par plateforme
- [K8986](https://my.f5.com/manage/s/article/K8986) : politiques de support des produits F5
- [Release notes BIG-IP](https://techdocs.f5.com/en-us/bigip-21-1-0/big-ip-release-notes.html) : nouveautés,
  installation et mise à niveau de chaque version majeure

## Développement

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
node --test tests/site/logic.test.js
```

Le rendu des articles de my.f5.com demande [Lightpanda](https://github.com/lightpanda-io/browser/releases)
(glibc 2.35 ou plus récente). La variable `F5BUGS_LIGHTPANDA` donne la commande à lancer si le binaire
n'est pas dans le `PATH`, par exemple un conteneur.

Pour récupérer les pages puis prévisualiser le site :

```sh
.venv/bin/f5bugs collect
.venv/bin/f5bugs extract
.venv/bin/f5bugs tracker
.venv/bin/f5bugs --base-url http://localhost:8040/ build
python3 -m http.server 8040 --directory dist
```

## Licence

Le code est distribué sous licence [GNU AGPL 3.0 ou ultérieure](LICENSE).

Cette licence ne couvre pas les contenus de tiers, notamment les textes issus de la documentation F5.
F5, BIG-IP, F5OS, iSeries, rSeries, VELOS et VIPRION sont des marques de F5, Inc.

## Contact

Outil créé et maintenu par [FR Consulting](https://fr-consulting.fr).
Pour toute demande : contact@fr-consulting.fr
