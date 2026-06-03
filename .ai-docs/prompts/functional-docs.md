Tu dois rédiger une page de documentation fonctionnelle.

## Objectif

La page doit aider un lecteur non technique ou semi-technique à comprendre ce que fait le projet, pourquoi il existe et comment les traitements s’enchaînent.

## Contenu attendu

Selon le sujet de la page, documente :

- objectif métier ;
- problème traité ;
- données utilisées ;
- utilisateurs ou profils concernés ;
- fonctionnalités ;
- parcours d’utilisation ;
- flux de données ;
- règles métier visibles ;
- résultats produits ;
- limites fonctionnelles ;
- hypothèses à valider.

## Format obligatoire

La page doit être claire et non technique autant que possible.

Utilise :

- un résumé court ;
- un diagramme Mermaid si pertinent ;
- des tableaux ;
- des listes ;
- des encadrés Docusaurus ;
- une section "Hypothèses à valider" ;
- une section "Sources utilisées".

## Diagrammes recommandés

Pour la vue d’ensemble :
- mindmap
- flowchart TD

Pour les parcours :
- journey
- flowchart TD

Pour les flux de données :
- flowchart TD

Pour les fonctionnalités :
- flowchart TD
- tableau de synthèse

## Contraintes anti-hallucination

- Ne pas inventer d’utilisateur final si le repository ne le montre pas.
- Ne pas inventer d’interface web si elle n’est pas présente.
- Ne pas inventer de règle métier absente du code ou de la documentation.
- Si le comportement est déduit, l’indiquer.
- Si l’intention produit n’est pas certaine, l’ajouter dans "Hypothèses à valider".

## Style

Évite le jargon.
Explique simplement.
Structure en petites sections.
Ne fais pas de gros blocs de texte.