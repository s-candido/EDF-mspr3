# EDF MSPR3 - Gestion de la consommation énergétique avec MLFlow et AirFlow

<img src="assets/img/image.png" alt="alt text" width="50%">


## Démarrage

```bash
docker-compose build
```

```bash
docker-compose up -d
```

### Gestion et Versionning des Modèles : MLFlow

MLFlow est accessible sur : 

```sh
http://localhost:5000
```

### Base de Données : PostgreSQL

La Base de Données est accessible sur : 

```py
HOST="localhost"
DB="postgres"
USER="postgres"
PASSWORD="postgres"
PORT=5441
```


### Orchestration de Pipelines : AirFlow

AirFlow est accessible sur : 

```sh
http://localhost:8080
```
Avec ces identifiants :

Username :
```
admin
```

Mot de passe :
```
admin
```


## Détails MLFlow


Ne jamais toucher le dossier `mlflow/`

Pour Tester, essayer de pusher un modèle avec : 

```bash
python src/mlflow/push_model_to_mlflow.py
```

Si Vous avez ce message : 

```
PermissionError: [Errno 13] Permission denied: ./mlflow/artifacts/
```

Faites cette commande à la racine et réessayez : 

```bash
chmod -R 777 mlflow
```

### Pour Upgrade la version de Airflow (en python 3.7 actuellement) :

https://medium.com/@opcfrance/setting-up-apache-airflow-with-docker-a-comprehensive-guide-with-examples-c041fed1c3f5



## Infrastructure

![alt text](assets/img/infrastructure.png)




## Diagramme de flux


```mermaid
flowchart TD
    subgraph MLFlow
        G[MLFlow Registery]
    end
    subgraph Airflow DAG
        T[API - Open météo] -->|API Call| E(table meteo_data)
        A[Data - xls] -->|Download| B(Local Folder)
        B -->|Ingestion| C[table conso_features]
        C -->|Aggregation| D
        E -->|Aggregation| D[table final_features - PARTITION per YEAR]
        D -->|Train / Evaluate| F[Train / Test Models]
        F -->|Save Models| G
    end
```


## 


Pour 26 Janvier :

- Modèle à monter qui tourne avec bon score
- Dockeriser si possible

Sebastien : 
- 

Cyril :
- 

Hugo :
- Analyse exploratoire + Matrice de corrélation