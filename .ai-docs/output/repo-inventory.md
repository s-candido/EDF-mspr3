# Inventaire du repository

## Résumé
Le projet **EDF-MSPR3** est une plateforme MLOps dédiée à l'analyse et à la prédiction de la consommation énergétique. Il automatise l'ingestion de données (RTE éCO2mix), l'entraînement de modèles (Scikit-Learn), leur suivi (MLflow) et l'orchestration de pipelines. Le système s'appuie sur une stack Dockerisée incluant PostgreSQL et Airflow.

## Technologies détectées

| Technologie | Rôle | Source | Niveau de confiance |
|---|---|---|---|
| Python 3 | Langage principal | `src/`, `docker/` | Confirmé |
| Docker Compose | Orchestration de conteneurs | `docker-compose.yml` | Confirmé |
| PostgreSQL | Base de données (Backends & Data) | `docker-compose.yml` | Confirmé |
| MLflow | Registry & Tracking modèles | `src/mlflow/` | Confirmé |
| Airflow | Orchestration de pipelines | `docker-compose.yml` | Confirmé |
| Pandas / Scikit-Learn | Data manipulation & ML | `src/modeling/` | Confirmé |
| Open-Meteo | API météo | `src/data/weather_loader.py` | Confirmé |

## Services détectés

| Service | Rôle | Port | Source | Niveau de confiance |
|---|---|---|---|---|
| airflow | Orchestrateur de tâches | 8080 | `docker-compose.yml` | Confirmé |
| mlflow | Suivi et Registry ML | 5000 | `docker-compose.yml` | Confirmé |
| db_mlflow | DB Backend MLflow | 5432 (exp) | `docker-compose.yml` | Confirmé |
| edf_postgresl | DB données de production | 5441 | `docker-compose.yml` | Confirmé |

## Fichiers importants

| Fichier | Rôle probable | Source |
|---|---|---|
| `docker-compose.yml` | Orchestration infrastructure | Root |
| `src/main.py` | Pipeline d'exécution principal | `src/` |
| `src/db/ingestion_pg.py` | Script d'ingestion données vers Postgres | `src/db/` |
| `src/mlflow/push_model_to_mlflow.py` | Déploiement modèle vers MLflow | `src/mlflow/` |
| `src/data/weather_loader.py` | Ingestion données météo | `src/data/` |

## Pipelines ou traitements détectés
Le flux principal identifié dans `src/main.py` et le README :
1. Téléchargement des données annuelles éCO2mix (`downloader.py`).
2. Chargement et nettoyage des données (`data_loader.py`).
3. Enrichissement avec des données météo (`weather_loader.py`).
4. Création de features (`features.py`).
5. Entraînement (`train.py`) et évaluation (`evaluate.py`).
6. Enregistrement du meilleur modèle via `joblib` et `MLflow`.

## Données et stockage
- **Data Source** : Archives annuelles RTE (format .xls/.csv).
- **Stockage** : PostgreSQL (table `meteo_all_cities` et potentiellement `conso_features`).
- **Volumes Docker** : `airflowdata`, `mlflow`, `dbs_mlflow`, `postgresql_data`.

## MLflow
- **Usage** : Tracking d'expériences et Registry de modèles.
- **Accès** : `http://localhost:5000`.
- **Scripts associés** : `push_model_to_mlflow.py` et `pull_model_from_mlflow.py`.

## Airflow et DAGs
- **DAGs** : Le `docker-compose.yml` monte le dossier `./dags` dans `/opt/airflow/dags`.
- **Remarque** : Aucun fichier `.py` de DAG n'est présent dans le repository fourni, seulement la structure.

## Notebooks
- Aucun notebook `.ipynb` n'est présent dans les fichiers analysés, bien que mentionné dans le contexte.

## Commandes utiles
- `docker-compose up -d` : Démarrage de l'infrastructure.
- `python src/mlflow/push_model_to_mlflow.py` : Pusher un modèle vers MLflow.
- `chmod -R 777 mlflow` : Correction permission stockage local (README).

## Informations confirmées par le code
- Architecture basée sur micro-services Docker.
- Utilisation de `scikit-learn` pour le ML.
- Scripts de nettoyage de colonnes robustes (unicodes, regex).
- `postgresql` utilisé comme backend MLflow et DB de stockage données.

## Informations documentées seulement dans le README
- Identifiants de connexion Airflow par défaut (admin/admin).
- Diagramme de flux (Mermaid) présent dans le README.
- État des contributions par membre de l'équipe.

## Informations déduites
- Le projet est en phase de développement actif.
- Le pipeline `main.py` semble être une exécution manuelle locale, potentiellement à migrer vers un DAG Airflow.

## Zones incertaines
- Contenu réel des fichiers DAG dans `./dags` (non fournis).
- Disponibilité des données d'entraînement dans le dossier `/data`.
- Configuration exacte des secrets dans `env_files/secrets.env` (non fournis).

## Pages de documentation recommandées
1. **Architecture Globale** : Présentation des services et flux.
2. **Guide d'Ingestion** : Processus d'alimentation de la base Postgres.
3. **Pipeline ML** : Détails sur l'entraînement et l'enregistrement MLflow.
4. **Manuel Opérationnel** : Commandes de déploiement et gestion des erreurs (permissions).

## Sources utilisées
- `README.md`, `docker-compose.yml`, `src/main.py`, `src/data/*.py`, `src/db/*.py`, `src/mlflow/*.py`, `src/modeling/*.py`, `src/features/*.py`.