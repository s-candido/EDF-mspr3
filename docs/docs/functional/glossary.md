# Glossaire

## Résumé

Ce glossaire définit les termes métier, techniques et MLOps utilisés dans le projet **EDF-MSPR3**. Il permet aux nouveaux arrivants de comprendre le vocabulaire spécifique lié à la gestion des données de consommation énergétique et à l'automatisation des modèles.

## Vue d’ensemble

Les termes sont classés par domaine pour faciliter la navigation. Le projet combine des concepts de **Data Engineering** (ingestion, stockage) et de **Machine Learning** (entraînement, suivi de modèles).

## Détails

### Concepts MLOps
*   **Artifacts** : Fichiers générés par le processus de ML (ex: modèles sauvegardés, graphiques, logs).
*   **MLflow** : Outil utilisé pour suivre les expériences (paramètres, métriques) et stocker les modèles finaux.
*   **Experiment** : Regroupement d'exécutions d'entraînement sous un nom commun (`EDF_Model_Experiment`).
*   **Registre de modèles** : Espace centralisé permettant de gérer les versions et le cycle de vie des modèles produits (`MODEL_EDF`).

### Concepts Techniques & Infrastructure
*   **Airflow** : Orchestrateur de tâches qui automatise l'enchaînement des scripts d'ingestion et d'entraînement.
*   **DAG (Directed Acyclic Graph)** : Fichier Python définissant le workflow (séquence d'étapes) dans Airflow.
*   **Docker Compose** : Outil permettant de lancer l'ensemble de l'environnement (bases de données, serveurs) via une configuration unique.
*   **PostgreSQL** : Base de données relationnelle utilisée pour stocker les données brutes et les métadonnées de MLflow.

### Concepts Métier
*   **éCO2mix** : Jeu de données public fourni par RTE, contenant les mesures de consommation électrique.
*   **Feature Engineering** : Transformation des données brutes (ex: météo, date) en variables exploitables par les modèles (ex: moyennes mobiles).

## Tableau de synthèse

| Terme | Domaine | Définition simplifiée | Statut |
|---|---|---|---|
| **DAG** | Airflow | Workflow automatisé. | Confirmé par code |
| **Artifact** | MLOps | Produit final (modèle). | Confirmé par code |
| **éCO2mix** | Métier | Données de consommation RTE. | Déduit du code |
| **Pipeline** | Data | Enchaînement ingestion-traitement. | Confirmé par code |
| **Ingestion** | Data | Importation des données sources. | Confirmé par code |

## Points d’attention

:::warning
La distinction entre les données de test, d'entraînement et de production doit être rigoureusement respectée pour éviter toute fuite de données lors de la modélisation.
:::

## Hypothèses à valider

*   **Format des données** : Nous supposons que les données éCO2mix respectent le format standard annuel fourni par RTE. À confirmer par inspection des fichiers dans le volume `data/`.
*   **Règles métier** : Les seuils ou les critères de performance permettant de valider un modèle dans MLflow ne sont pas explicitement documentés.

## Sources utilisées

*   `README.md` : Concepts globaux.
*   `src/data/data_loader.py` : Scripts d'ingestion éCO2mix.
*   `src/mlflow/push_model_to_mlflow.py` : Termes liés aux artifacts et registre.
*   `docker-compose.yml` : Architecture des services techniques.
*   `dags/` : Répertoire contenant les définitions de workflows.