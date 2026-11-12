---
type: Project Rules
title: Règles de f5-bug-tracker
description: Règles communes aux bug trackers et particularités de F5 BIG-IP et F5OS.
resource: https://github.com/frc-fr/f5-bug-tracker
tags: [rules, f5, big-ip, f5os, bug-tracker]
timestamp: 2026-11-12T19:00:00+01:00
product: F5 BIG-IP, F5OS-A, F5OS-C
site: https://frc-fr.github.io/f5-bug-tracker/
---

# Critères communs

Section identique dans forti-, juni-, palo-, cisco- et f5-bug-tracker. Toute modification se reporte dans les cinq.

## Architecture

- Site statique : pas de serveur, pas de base de données.
- Python côté collecte, JavaScript sans framework côté navigateur.
- Paquet Python `<fournisseur>bugs`, une commande par étape :
  - `collect` : met à jour l'état des sources et télécharge ce qui a changé.
  - `extract` : lit les documents en cache ; échoue au moindre avertissement.
  - `build` : croise les données et génère `dist/`.
- Modules : `collect`, `parser`, `extract`, `normalize` (matériel), `lifecycle` (dates de support), `build`, `feed`, `cli`.

### Répertoires

- `sources/` : état des sources (adresses, ETag, lastmod, dates de support). Commité.
- `.cache/` : documents bruts. Non versionné, gardé par le cache de la CI.
- `data/extracted/` : un JSON par document, une ligne par bug pour des diffs lisibles. Commité.
- `data/changes.json` : journal des nouveautés. Absent au départ : la première extraction sert de référence.
- `site/` : `index.html`, `app.js` (affichage), `logic.js` (règles de statut, testables), `i18n.js`, `theme.js`, `style.css`, mentions légales FR/EN.
- `dist/` : site généré, avec `data/*.json` compacts et `feed.xml`. Non versionné.

### Modèle de données

- Un bug = identifiant, description, contournement, matériel cité, événements.
- Un événement = version, statut (`r` corrigé, `k` connu, `l` limitation…), page officielle.
- Les statuts par version sont calculés dans le navigateur, à partir des notes de la branche.

### Tests

- `pytest` : tests unitaires, plus tests sur les vrais documents en cache.
- `node --test tests/site/logic.test.js` : règles de statut et de comparaison.
- Test des clés de traduction et de la CSP.

## Sources et collecte

- Sources officielles et publiques du fournisseur en priorité.
- Source communautaire (ex. endoflife.date) seulement à défaut d'équivalent officiel, citée comme telle dans les mentions légales.
- robots.txt respecté : un chemin interdit n'est jamais interrogé.
- 2 secondes minimum entre deux requêtes, User-Agent du projet.
- Ne recharger que ce qui a changé (ETag, Last-Modified, lastmod du sitemap).
- Résultats d'extraction commités dans `data/` : vider le cache CI ne relance pas tout.
- Un avertissement d'extraction arrête la mise à jour : le site garde ses dernières données valides.
- Une source annexe (dates de support…) en échec garde ses dernières valeurs.
- Le navigateur ne contacte jamais de service tiers.

## Contenu

- Objet : bugs connus et bugs corrigés. Jamais la sécurité.
- Entrées de sécurité écartées, références CVE retirées des descriptions.
- Chaque fait renvoie à la page officielle exacte qui le porte.
- Textes des bugs laissés en anglais, tels que publiés.
- Statuts déduits des notes, jamais inventés ; « Inconnu » expliqué et masqué par défaut.
- Un modèle cité ne veut pas dire « seul ce modèle est touché ». Filtre matériel inclusif.
- Un bug à la fois correction et changement de comportement n'est compté qu'une fois.
- Une version annoncée mais pas encore publiée est marquée « non publiée ».
- Toutes les branches restent consultables ; les branches supportées sont mises en avant.
- Pas d'affirmation générale ou trop assurée dans les textes.

## Interface

- Français et anglais, sans page /en/ séparée.
- Bandeau visible : « vos sélections ne sont ni enregistrées ni transmises ».
- Onglets : Rechercher, Comparer, Matériel, puis Quoi de neuf à droite de Matériel.
- Comparaison : pastilles triées par ordre alphabétique, « Tous » en premier.
- Libellé court « Correction » ; risques (nouveaux, toujours présents) mis en valeur.
- Panneau « À lire » replié par défaut, il ne s'ouvre que si l'utilisateur le déplie.
- Listes déroulantes filtrables à la frappe ; bouton Réinitialiser.
- Tableau sélectionnable en entier et bouton « Copier le tableau ».
- Bouton de retour en haut de page.
- Logos RSS puis GitHub, minimalistes et presque transparents, à gauche de « EN ».
- Thème clair et sombre ; pas de noir trop profond.
- Textes longs justifiés, sur toute la largeur.
- Cron et date de dernière mise à jour affichés.
- Placeholders neutres : ne jamais révéler le matériel de l'utilisateur.
- Même forme dans tous les sites, quelle que soit la façon de présenter du fournisseur : on cherche au même endroit.
- Données uniformes entre fournisseurs : pas d'information propre à un seul fournisseur si elle n'aide pas l'exploitation (ex. date de mise en vente).
- Plusieurs systèmes : sélecteur de logiciel, libellé visible « Logiciel », jamais un choix de matériel.

## Matériel et nouveautés

- Onglet Matériel : pastilles de statut (« Tous » en premier, puis « Plus dans la dernière branche » ou son équivalent).
- Colonnes : Modèle, Première version, Dernière version, Statut <logiciel>, Version recommandée, Fin de support.
- Statut tiré d'une source officielle du fournisseur : il dit, sans le deviner, si le matériel est encore maintenu.
- Fin de vie annoncée par référence : variantes affichées séparément, pièces détachées et modules écartés.
- Pas de source : « Aucune fin annoncée », jamais « supporté ».
- Version recommandée seulement si le fournisseur la publie sans compte ; sinon la colonne est absente, et la note dit pourquoi.
- Rechercher : un modèle choisi affiche ce que le fournisseur dit de lui (statut, version recommandée, fin de support).
- Quoi de neuf : cartes « Dernière version publiée », « Dernier document mis à jour », puis « Recommandée par <fournisseur> » si elle existe.

## Design

- Même structure et mêmes jetons de couleur dans les trois sites.
- Couleur du fournisseur en touche seulement : bordure haute et nom du produit.
- Contraste professionnel, rien qui « pique les yeux ».
- Cohérence entre pages : mêmes pastilles partout, pas de tuiles géantes.

## Publication

- Cron du lundi au vendredi : 9 h 15, 14 h 15, 19 h 00, Europe/Paris.
- Horaire décrit dans `sources/schedule.yml` et affiché sur le site, qui le lit au build.
- Workflow GitHub sans déclencheur `schedule` (retardé ou oublié par GitHub) : lancé par `workflow_dispatch`.
- Ordre : tests, collecte, extraction, tests sur le corpus réel, commit des données, build, GitHub Pages.
- Flux RSS/Atom des nouveautés.
- CSP stricte : aucun script, style ou service tiers.

## Mentions et licence

- Outil créé et maintenu par FR Consulting ; contact@fr-consulting.fr ; lien vers fr-consulting.fr.
- Site indépendant, non affilié au fournisseur. Jamais « approuvé par ».
- Mentions légales FR et EN, avec la liste des services et composants tiers.
- Code sous AGPL 3.0 ou ultérieure ; contenus du fournisseur exclus.
- README générique : rien de sensible ni de personnel.

# Particularités BIG-IP et F5OS

## Trois logiciels

- BIG-IP (TMOS), F5OS-A (rSeries), F5OS-C (VELOS) : sélecteur « Logiciel », données séparées.
- F5OS héberge les instances BIG-IP ; ses bugs sont dans ses propres notes.
- F5OS 2.x : une seule série de notes pour rSeries et VELOS, montrée dans F5OS-A et dans F5OS-C.
- Quatre séries de pages : `bigip`, `f5os-a`, `f5os-c`, `f5os` ; cache et extraction par série.
- F5OS : 1.8.4, puis 1.8.4-HR-1, 1.8.4-HR-2 (Hardened), puis 1.8.4-CR (Critical, reprend les HR). Affichés comme F5 les écrit.
- Notes F5OS sans « Fixed Versions » : une correction vaut pour sa version et les suivantes de sa branche.
- Dates F5OS : K21501912 (LTS trois ans, STS un an) ; la ligne « 2.x.x » vaut pour toutes les branches 2.y.
- Matériel F5OS : K86001294 (versions F5OS par plateforme rSeries ou VELOS) et K4309.
- Candidats F5OS : patch suivante, HR suivante et CR de la dernière patch des branches supportées.

## Versions

- Version de maintenance : `17.1.3`. Point release : `17.1.3.7`. Branche : `17.1`.
- Point release : même logique que les -h de PAN-OS et les -S de Junos.
- Une correction en `17.1.3.6` vaut pour `17.1.3.7`, pas pour `17.1.2.2` ; pour `17.1.4` seulement si F5 le dit.
- Anciens hotfixes « v12.1.2 Hotfix 2 » : point release `12.1.2.2`, comme K9502.
- Engineering Hotfixes (`17.1.1.4-0.100.9`) écartés : builds pour quelques clients.
- Branches couvertes depuis 11.5.

## Sources

- Pages « Fixes and Known Issues » de techdocs.f5.com, une par version : adresse prévisible.
- Versions : sitemap de la KB (incomplet, lu le lundi), K9412, K9502, puis HEAD sur les numéros suivants des branches supportées.
- Version absente : réponse 200 avec une page « Page not found » de taille fixe, reconnue à sa taille.
- ETag et Last-Modified changent à chaque déploiement du site : page retéléchargée seulement si sa taille change.
- Branches supportées vérifiées à chaque passage, les autres une fois par semaine.
- Bug Tracker public (cdn.f5.com) : une page par bug, lue une fois, relue si les notes ajoutent une version corrigée.
- Bug Tracker lu par lots à chaque passage, les plus récents d'abord ; résultat commité.
- Articles my.f5.com rendus par Lightpanda, seulement si leur lastmod change dans le sitemap du portail.
- K5903 : dates de support des branches. K9412 : plateformes et date de chaque version de maintenance (17.x et plus).
- K9502 : dernière point release de chaque version. K4309 : cycle de vie des plateformes. K2200 : versions actuelles.
- K9476 et K8986 : bloqués par un reCAPTCHA, non lus ; K9412 et K4309 donnent les mêmes faits.

## Extraction

- Une page reprend toutes les corrections de sa ligne et les Known Issues de sa branche.
- Stockage : un fichier par version avec les seuls numéros, un fichier unique des bugs, une ligne par bug.
- Texte d'un bug : celui de la page la plus récente qui le détaille ; versions corrigées : union de toutes les pages.
- Mise en page variable selon les années : lecture par titres de section et noms de colonnes, pas par balisage.
- Tableaux « Vulnerability Fixes », colonne CVE, titres de vulnérabilité : écartés. Références CVE retirées.
- Numéro de bug sans le suffixe de portage : `2201813-3` est le bug `2201813`.
- Extraction incrémentale : une page n'est relue que si sa copie en cache est plus récente que son extraction.

## Matériel

- Aucun chapitre par plateforme : plateforme connue seulement quand le texte la cite.
- Familles F5 : rSeries, VELOS, iSeries, VIPRION, appliances v/s, Virtual Edition.
- Une plateforme citée n'est retenue que si K4309, K9412 ou K86001294 la nomme (« 1000s of… », « i2000 », « r5000 Series » écartés).
- F5OS-A : filtre matériel limité aux rSeries ; F5OS-C : limité à VELOS, même si un texte cite l'autre famille.
- Noms harmonisés entre articles : « VELOS BX110 » = « BX110 Blade », « 10350v-N » = « 10350v NEBS ».
- « Arrêt après » : dernière branche dont K9412 liste la plateforme, avant la plus récente (21.x n'a plus d'iSeries ni de VIPRION).
- Fin de support : End of Software Support de K4309, après laquelle F5 ne publie plus de correctif.
- Première / dernière version : celles où la matrice liste la plateforme (K9412 BIG-IP, K86001294 F5OS), comme forti ; à défaut, versions citées, marquées « * ».
- Sous le statut : versions F5OS de la plateforme (K86001294), révision matérielle et version F5OS minimale (note de K86001294, article lié).
- Pas de date de mise en vente : aucun autre fournisseur ne la donne, et elle n'aide pas l'exploitation.
- « Fin de vie annoncée » seulement sur une vraie date de fin (fin de vente ou de support logiciel), jamais sur la seule date de mise en vente.
- Codes de plateforme K4309/K9412 de toute lettre (C129, F101, R100, S100/101).
- Pas de version recommandée par plateforme : carte « Versions actuelles selon F5 » tirée de K2200.

## Affichage

- Identifiants numériques ; recherche aussi par `2201813-3`, `BT2201813`, `ID2201813`.
- Filtre Composant (Local Traffic Manager, TMOS…), équivalent du filtre Catégorie de forti et juni.
- Sévérité F5 reprise telle quelle (Bug Tracker, ou colonne Severity des anciennes notes) ; définitions K19001479 en pied de page.
- Étoile ★ de F5 (« peut empêcher le chargement de la configuration ou dégrader les performances après mise à niveau ») : badge et filtre « Signalement F5 ».
- Le filtre ★ ne garde que des bugs : les Behavior Change de la comparaison sont masqués.
- Symptômes, conditions, impact et changement de comportement chargés à l'ouverture du bug (`data/details/`).
- Chaque bug renvoie à sa page Fixes and Known Issues, à son article K et à sa fiche du Bug Tracker.
- Comparaison : « Behavior Change » des corrections rattachés aux versions qui les apportent.
- Couleur de marque : cramoisi, distinct du rouge de FortiOS.
- Titre du site « F5 Bug Tracker » : il couvre BIG-IP et F5OS.

# Citations

[1] [K5903: BIG-IP software support policy](https://my.f5.com/manage/s/article/K5903)
[2] [K9412: The BIG-IP release matrix](https://my.f5.com/manage/s/article/K9412)
[3] [K9502: BIG-IP hotfix and point release matrix](https://my.f5.com/manage/s/article/K9502)
[4] [K4309: F5 hardware product lifecycle support policy](https://my.f5.com/manage/s/article/K4309)
[5] [K2200: Most recent versions of F5 software](https://my.f5.com/manage/s/article/K2200)
[6] [F5 Bug Tracker](https://cdn.f5.com/product/bugtracker/)
[7] [Lightpanda](https://lightpanda.io)
[8] [K21501912: Software lifecycle policy for F5OS](https://my.f5.com/manage/s/article/K21501912)
[9] [K86001294: F5OS hardware/software support matrix](https://my.f5.com/manage/s/article/K86001294)
