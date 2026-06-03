# Variables d’environnement

## Résumé
Cette page recense les variables d'environnement identifiées dans le projet EDF-MSPR3. Elles assurent la configuration des services (Airflow, MLflow, PostgreSQL) et la connexion entre les différents composants du pipeline MLOps.

## Vue d’ensemble

Les configurations sont majoritairement centralisées dans le fichier `docker-compose.yml`. Ces variables permettent de définir les ports, les accès aux bases de données et les paramètres d'initialisation des services.

:::warning
Ne jamais stocker de mots de passe en clair dans des fichiers versionnés en production. Utilisez un fichier `.env` non versionné pour vos configurations locales.
:::

## Détails

### Configuration des services
Le fichier `docker-compose.yml` définit des variables pour le comportement des conteneurs :

*   **Airflow** : Variables pour initialiser l'instance et le compte administrateur.
*   **PostgreSQL** : Variables pour définir les noms d'utilisateurs, les noms de bases de données et les mots de passe.
*   **MLflow** : Configuration de l'URI du backend de stockage (généralement pointant vers la base de données PostgreSQL dédiée).

### Méthodes d'injection
Le projet utilise deux approches principales :
1.  **Fichiers `docker-compose.yml`** : Variables déclarées directement dans les sections `environment`.
2.  **Scripts Python** : Utilisation de variables d'environnement pour gérer les chaînes de connexion (`DATABASE_URL`, `MLFLOW_TRACKING_URI`).

## Tableau de synthèse

| Service | Variable (exemples) | Rôle | Source |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | `POSTGRES_USER` | Identifiant connexion DB | `docker-compose.yml` |
| **PostgreSQL** | `POSTGRES_PASSWORD` | Secret accès base | `docker-compose.yml` |
| **PostgreSQL** | `POSTGRES_DB` | Nom de la base métier | `docker-compose.yml` |
| **Airflow** | `AIRFLOW__CORE__LOAD_EXAMPLES` | Désactivation exemples Airflow | `docker-compose.yml` |
| **MLflow** | `MLFLOW_TRACKING_URI` | Adresse serveur MLflow | Déduit/Code |

## Points d’attention

*   **Sécurité** : Le fichier `docker-compose.yml` présent dans le dépôt peut contenir des valeurs par défaut. Assurez-vous de les remplacer dans votre environnement local.
*   **Persistance** : Les variables de configuration ne modifient pas le contenu des volumes (données persistées), elles pilotent uniquement l'initialisation des services.
*   **Synchronisation** : Tout changement de nom de base de données dans le `docker-compose.yml` doit être répercuté dans les scripts Python de connexion.

## À vérifier manuellement

*   Vérifier si un fichier `.env.example` existe pour lister les variables nécessaires au lancement du projet.
*   Confirmer si le script `src/mlflow/push_model_to_mlflow.py` lit dynamiquement les variables d'environnement pour l'URI de tracking ou s'il utilise une valeur codée en dur.
*   Vérifier les variables d'environnement spécifiques à l'authentification dans les DAGs Airflow.

## Sources utilisées

*   `docker-compose.yml` : Analyse des services et variables d'environnement déclarées.
*   README : Mentions des identifiants par défaut pour les services.
*   `src/` : Analyse des scripts Python pour détecter la lecture de variables d'environnement (`os.getenv`).