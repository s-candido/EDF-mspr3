Tu dois rédiger une page de documentation technique.

## Objectif

La page doit aider un développeur, un DevOps ou un mainteneur à comprendre comment fonctionne le projet techniquement.

## Contenu attendu

Selon le sujet de la page, documente :

- composants techniques ;
- fichiers concernés ;
- services Docker ;
- ports ;
- volumes ;
- dépendances ;
- scripts ;
- DAGs Airflow ;
- jobs ou pipelines ;
- base de données ;
- tracking MLflow ;
- commandes utiles ;
- flux techniques ;
- limites ;
- erreurs possibles.

## Format obligatoire

La page doit être très lisible.

Utilise :

- un résumé court ;
- un diagramme Mermaid si pertinent ;
- des tableaux ;
- des listes ;
- des encadrés Docusaurus ;
- une section "À vérifier manuellement" ;
- une section "Sources utilisées".

## Diagrammes recommandés

Pour l’architecture :
- flowchart TD

Pour Airflow :
- flowchart TD
- sequenceDiagram

Pour PostgreSQL :
- erDiagram si les entités sont identifiables
- flowchart TD sinon

Pour Docker Compose :
- flowchart TD des services

Pour les pipelines :
- flowchart TD des étapes

## Contraintes anti-hallucination

- Ne documente que les éléments visibles dans les fichiers fournis.
- Si tu déduis une information, indique clairement qu’elle est déduite.
- Si une information est incertaine, mets-la dans "À vérifier manuellement".
- Ne crée pas de commande si elle n’est pas documentée ou évidente depuis les fichiers.
- Ne crée pas de nom de service, port, table ou variable absent des fichiers analysés.

## Style

Pas de gros pavé.
Une section = une idée.
Un tableau dès qu’il y a plusieurs éléments comparables.