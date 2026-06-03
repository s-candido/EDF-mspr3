---
id: initial-architecture
title: Architecture initiale
---

# Architecture initiale

Cette page documente les premières décisions d’architecture du projet.

## Décision

Le projet utilise une architecture MLOps basée sur Docker Compose, Airflow, MLflow, PostgreSQL et des scripts Python.

## Contexte

Le projet vise à gérer un pipeline de données et de machine learning autour de la consommation énergétique.

## Conséquences

- La documentation doit couvrir l’infrastructure Docker.
- La documentation doit couvrir les pipelines Airflow.
- La documentation doit couvrir le cycle de vie des modèles MLflow.
- Les choix d’architecture doivent être versionnés dans les ADR.