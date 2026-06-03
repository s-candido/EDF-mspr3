# Qualité documentaire

Cette page sert de tableau de bord pour suivre l’état de la documentation technique et fonctionnelle du projet EDF-MSPR3.

:::info
Cette page peut être mise à jour manuellement après relecture, ou améliorée plus tard par l’agent IA.
:::

## Statut global

| Élément | Statut | Commentaire |
|---|---|---|
| Génération initiale | En cours | Les pages sont générées par lots. |
| Relecture humaine | À faire | Relire dans Obsidian avant validation. |
| Build Docusaurus | À vérifier | Exécuter `npm run docs:build`. |
| Diagrammes Mermaid | Activés | Vérifier que chaque diagramme s’affiche correctement. |

## Pages à relire en priorité

| Page | Priorité | Points à vérifier |
|---|---:|---|
| Architecture technique | Haute | Cohérence entre Docker, Airflow, MLflow et PostgreSQL. |
| Airflow et DAGs | Haute | Noms exacts des DAGs, tâches réellement présentes. |
| Pipelines de traitement | Haute | Ordre des étapes, scripts réellement appelés. |
| Base PostgreSQL | Moyenne | Tables et usages réellement confirmés par le code. |
| Déploiement | Moyenne | Commandes, ports, variables d’environnement. |

## Dette documentaire

- Confirmer les éléments seulement documentés dans le README.
- Vérifier que les diagrammes Mermaid restent simples et lisibles.
- Compléter les pages qui ont peu de sources confirmées par le code.
- Éviter les gros pavés : remplacer par tableaux, listes et schémas.

## Règles de validation

Une page est considérée comme validée si :

- elle build correctement avec Docusaurus ;
- elle contient des sources utilisées ;
- elle distingue les faits confirmés des hypothèses ;
- elle ne contient pas de secrets ;
- elle est relue dans Obsidian ;
- ses diagrammes Mermaid s’affichent correctement.

## Commandes utiles

```powershell
npm run docs:generate
npm run docs:improve
npm run docs:update
npm run docs:build
```
