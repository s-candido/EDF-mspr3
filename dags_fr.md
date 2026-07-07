# Documentation des DAGs - Gestion de la consommation énergétique EDF MSPR3

Ce document fournit une vue d'ensemble complète de tous les DAGs présents dans le répertoire `dags/`, incluant leurs transformations, leurs tâches et les flux de données.

## Table des matières

1. [Vue d'ensemble des DAGs](#vue-densemble-des-dags)
2. [Transformations détaillées des DAGs](#transformations-detaillées-des-dags)
   - [data_ingestion_dag](#data_ingestion_dag)
   - [ml_pipeline_dag](#ml_pipeline_dag)
   - [performance_test_dag](#performance_test_dag)
   - [test_dag](#test_dag)
3. [Scripts de support](#scripts-de-support)
4. [Architecture des flux de données](#architecture-des-flux-de-données)

## Vue d'ensemble des DAGs

| Nom du DAG | Objectif | Planification | Transformations principales |
|------------|----------|---------------|-----------------------------|
| `data_ingestion_dag` | Charger les données météo et de consommation dans PostgreSQL | Manuel | Téléchargement des données → Ingestion BDD → Nettoyage des features → Agrégation des données |
| `ml_pipeline_dag` | Pipeline complet d'entraînement et d'évaluation ML | Manuel | Chargement des données → Ingénierie des features → Entraînement modèle → Enregistrement MLflow |
| `performance_test_dag` | Test de robustesse du modèle avec injection de bruit | Manuel | Chargement modèle → Test de performance → Journalisation des résultats |
| `test_dag` | DAG de test simple pour validation | Manuel | Tâches factices pour tester |

---

## Transformations détaillées des DAGs

### data_ingestion_dag

**Fichier**: `dags/data_ingestion_dag.py`

**Objectif**: Orchestrer le pipeline complet d'ingestion de données depuis des sources externes vers la base de données PostgreSQL.

**Planification**: Déclenchement manuel uniquement (`schedule_interval=None`)

**Flux des tâches**:
```
start → ingestion_job → cleanning_job → aggregation_job → complete
```

#### Transformations:

#### 1. ingestion_job
- **Fonction**: `run_full_pipeline` depuis `src.data_ingestion`
- **Transformations**:
  - **Téléchargement des données**: Télécharge et extrait les données de consommation énergétique à partir de 2012 via `download_and_extract(start_year=2012)`
  - **Ingestion PostgreSQL**: Charge les données de consommation dans PostgreSQL via `ingest_postgres()`
    - 📬 Création - Table *conso_logs* 
    - 📬 Création - Table *conso_raw* 
  - **Ingestion Données Météo**: Récupère les données météo de 2012 à 2023 via `ingest_weather(2012, 2023)`
    - 📬 Création - Table *weather_data*
    - 📬 Création - Table *weather_log*
  - **Création de Features**: Crée les features initiales via `create_features(df)` sur les données chargées
  - **Nettoyage des Données**: Supprime les fichiers téléchargés après une ingestion réussie (`cleanup=True`)
  
#### 2. cleanning_job
- **Fonction**: `ingest_features` depuis `src.db.ingestion_clean_data`
- **Transformations**:
  - **Nettoyage des Données**: Traite et nettoie les features brutes de consommation
  - **Ingénierie des Features**: Applique des transformations de nettoyage pour préparer les données à l'analyse
  - **Stockage en Base de Données**: Stocke les features nettoyées dans la base de données PostgreSQL
    - 📬 Création - Table *conso_clean*


#### 3. aggregation_job
- **Fonction**: `ingest_conso_meteo` depuis `src.db.ingestion_conso_meteo_sql`
- **Transformations**:
  - **Agrégation des Données**: Combine les données de consommation et les données météo
  - **Agrégation Temporelle**: Crée des features agrégées avec des dimensions temporelles
  - **Stockage Final des Features**: Stocke les données agrégées dans une structure de table partitionnée
    - 📬 Création - Table *aggregated_conso_weather*
---

### ml_pipeline_dag

**Fichier**: `dags/ml_pipeline_dag.py`

**Objectif**: Pipeline complet de machine learning, du chargement des données à l'enregistrement du modèle dans MLflow.

**Planification**: Déclenchement manuel uniquement (`schedule_interval=None`)

**Flux des tâches**:
```
start → preprocessing_task → complete
```

#### Transformations:

#### preprocessing_task
- **Fonction**: `run_ml_pipeline` depuis `src.main`
- **Transformations**:
  - **Chargement des Données**: Charge toutes les données depuis le répertoire local via `load_all_data(data_dir)`
  - **Ingénierie des Features**: Applique une création complète de features via `create_features(df)`
    - Features temporelles (heure, jour, mois, année)
    - Features liées à la météo
    - Modèles de consommation
  - **Prétraitement des Données**:
    - Conversion de la variable cible en numérique: `pd.to_numeric(df[target], errors="coerce")`
    - Gestion des valeurs manquantes: `X.fillna(0)`, `y.fillna(0)`
    - Séparation Train-test: `train_test_split(X, y, test_size=0.2, random_state=42)`
  - **Entraînement du Modèle**: Entraîne plusieurs modèles via `train_models(X_train, y_train)`
  - **Évaluation du Modèle**: Évalue tous les modèles via `evaluate_model(model, X_test, y_test)`
    - Métriques: R², RMSE, MAPE
    - Sélection du meilleur modèle basée sur le score R²
  - **Intégration MLflow**:
    - Suivi de l'expérience: `mlflow.set_experiment("EDF_Model_Experiment")`
    - Journalisation des paramètres: fichiers sources, type de modèle
    - Journalisation des métriques: score R²
    - Enregistrement du modèle: `mlflow.register_model(model_uri, "MODEL_EDF")`
  - **Récupération Données Météo**: Récupère les données météo via `fetch_weather("2020-01-01", "2020-12-31")`

---

### performance_test_dag

**Fichier**: `dags/performance_test_dag.py`

**Objectif**: Test de robustesse du dernier modèle ML avec injection progressive de bruit.

**Planification**: Déclenchement manuel uniquement (`schedule_interval=None`)

**Flux des tâches**:
```
start → run_performance_test → complete
```

#### Transformations:

#### run_performance_test
- **Fonction**: `run_performance_test_task` (enveloppe) appelant `run_performance_test` depuis `srcperformance_test.performance_test`
- **Transformations**:
  - **Chargement du Modèle**:
    - Récupère la dernière version du modèle depuis le registre MLflow: `get_latest_model_version("MODEL_EDF")`
    - Charge le modèle: `load_model(model_uri)` où `model_uri = f"models:/{MODEL_NAME}/{model_version}"`
  - **Préparation des Données de Test**:
    - Charge les données via `load_all_data(DATA_DIR)`
    - Applique l'ingénierie des features: `create_features(df)`
    - Utilise les 1000 premiers échantillons pour le test: `X_test = X.head(1000)`
  - **Test d'Injection de Bruit**:
    - Teste 14 niveaux de bruit: `[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`
    - Pour chaque niveau de bruit:
      - Ajoute un bruit gaussien: `noise = np.random.normal(0, noise_level * col_std, size=X_noisy[col].shape)`
      - Évalue la performance du modèle: `evaluate_model(model, X_noisy, y_test)`
  - **Calcul des Métriques**:
    - **Métriques Primaires**: R², RMSE, MAPE à chaque niveau de bruit
    - **Métriques de Dégradation**: Changement en pourcentage par rapport à la référence (bruit=0.0)
    - Formule: `((metric_noisy - metric_baseline) / abs(metric_baseline)) * 100`
  - **Journalisation des Résultats dans MLflow**:
    - Expérience: "Performance_Test"
    - Paramètres: model_version, noise_levels
    - Métriques: Toutes les métriques de performance et valeurs de dégradation à chaque niveau de bruit
    - Artefacts:
      - Graphiques de performance (résumé en 4 panneaux)
      - Graphiques d'analyse de dégradation avec marqueurs de seuil
      - Résultats CSV: `performance_results.csv`
  - **Analyse des Seuils**:
    - **Seuil d'avertissement**: -10% de dégradation
    - **Seuil critique**: -20% de dégradation
    - Annotation automatique des points critiques sur les graphiques
      - 🔬 Pull la dernière version du modèle *MODEL_EDF*
---

### test_dag

**Fichier**: `dags/test_dag.py`

**Objectif**: DAG de test simple pour la validation et le débogage d'Airflow.

**Planification**: Déclenchement manuel uniquement

**Flux des tâches**:
```
dummy_task_run_1 → dummy_task_run_2
```

#### Transformations:
- **Validation Basique**: Utilise des tâches `DummyOperator` pour vérifier le fonctionnement d'Airflow
- **Pas de Traitement de Données**: Uniquement pour tester l'infrastructure

---

## Scripts de support

### Scripts de Traitement de Données (Core)

#### src/data_ingestion.py
- **run_full_pipeline()**: Fonction principale d'orchestration
  - Télécharge les données de consommation (2012+)
  - Ingère dans PostgreSQL
  - Récupère les données météo (2012-2023)
  - Crée les features initiales
  - Nettoie les fichiers temporaires

#### src/main.py
- **run_ml_pipeline()**: Pipeline ML complet
  - Chargement des données et ingénierie des features
  - Entraînement et évaluation multi-modèles
  - Enregistrement du modèle dans MLflow
  - Intégration des données météo

### Scripts d'Ingestion Base de Données

#### src/db/ingestion_postgre.py
- Charge les données de consommation dans les tables PostgreSQL

#### src/db/ingestion_weather.py
- Récupère et stocke les données météo depuis des APIs externes

#### src/db/ingestion_clean_data.py
- **ingest_features()**: Nettoyage des données et prétraitement des features

#### src/db/ingestion_conso_meteo_sql.py
- **ingest_conso_meteo()**: Agrège les données de consommation et météo

### Scripts de Chargement de Données

#### src/data/data_loader.py
- **load_all_data()**: Charge les données de consommation depuis des fichiers locaux
- **load_from_postgres()**: Récupère les données depuis PostgreSQL

#### src/data/weather_loader.py
- **fetch_weather()**: Récupère les données météo pour des plages de dates spécifiques

### Scripts d'Ingénierie des Features

#### src/features/features.py
- **create_features()**: Crée des features temporelles et basées sur la consommation

#### src/features/weather_features.py
- Fonctions d'ingénierie de features spécifiques à la météo

### Scripts de Modélisation

#### src/modeling/train.py
- **train_models()**: Entraîne plusieurs modèles ML (probablement des modèles de régression)

#### src/modeling/evaluate.py
- **evaluate_model()**: Calcule les métriques R², RMSE, MAPE

### Scripts d'Intégration MLflow

#### src/mlflow/pull_model_from_mlflow.py
- Récupère les dernières versions de modèles depuis le registre MLflow

#### src/mlflow/push_model_to_mlflow.py
- Enregistre les modèles entraînés dans MLflow

### Scripts de Test

#### src/test/performance_test.py
- **run_performance_test()**: Test complet avec injection de bruit
- **add_noise_to_features()**: Ajoute un bruit gaussien contrôlé aux features
- **get_latest_model_version()**: Récupère le dernier modèle depuis le registre

---

## Architecture des flux de données

### Sources de Données
1. **Données de Consommation Énergétique**: Fichiers de données externes (format XLS/CSV)
2. **Données Météo**: Récupération de données météo via API
3. **Données Historiques**: Stockage base de données PostgreSQL

### Pipeline de Transformation

#### 1. Phase d'Ingestion de Données
```
Fichiers Externes → Téléchargement → PostgreSQL → API Météo → Création Features → Features Nettoyées
```

#### 2. Phase d'Entraînement ML
```
Base de Données → Chargement Données → Ingénierie Features → Entraînement Modèles → Évaluation → Enregistrement Meilleur Modèle
```

#### 3. Phase de Test
```
Registre MLflow → Chargement Modèle → Injection Bruit → Évaluation Performance → Journalisation Résultats
```

### Tables de Base de Données
- **Données Brutes**: `weather_data`, tables de consommation
- **Données Traitées**: `features_data`
- **Données Agrégées**: Tables partitionnées par année/mois

### Intégration MLflow
- **Expérience**: "EDF_Model_Experiment" pour l'entraînement
- **Expérience**: "Performance_Test" pour les tests de robustesse
- **Registre de Modèles**: "MODEL_EDF" pour le versionnage des modèles

### Fonctionnalités Clés Créées
- **Features Temporelles**: Heure, jour, mois, année, jour de la semaine
- **Features Météo**: Température, humidité, précipitations, vent
- **Features de Consommation**: Modèles de consommation historiques, features de décalage (lag)
- **Features Agrégées**: Agrégations temporelles, statistiques glissantes

---

## Configuration

### Variables d'Environnement
- `MLFLOW_URL`: "http://mlflow:5000"
- `DATA_DIR`: "/opt/airflow/dags/src/data_folder"
- `MODEL_NAME`: "MODEL_EDF"

### Configuration Base de Données
- **Hôte**: "edf_postgresql"
- **Base de données**: "postgres"
- **Utilisateur/Mot de passe**: "postgres"
- **Port**: 5432

### Paramètres de Données
- **Période d'Entraînement**: 2012-2023 (météo), variable (consommation)
- **Taille du Test**: 20% des données
- **Variable Cible**: "consommation"
- **État Aléatoire (Random State)**: 42 (pour la reproductibilité)

Cette documentation fournit une vue d'ensemble complète de toutes les transformations et flux de données au sein des DAGs, permettant de comprendre l'intégralité du pipeline de gestion de la consommation énergétique EDF.
