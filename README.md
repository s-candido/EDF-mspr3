

## Lancer la Base PostgreSQL

```bash
docker build -t postgres_db .
```

```bash
docker run -d -p 5441:5432 --name postgres_db postgres_db
```

## Infrastructure

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

Pour 26 Janvier :

- Modèle à monter qui tourne avec bon score
- Dockeriser si possible

Sebastien : 
- 

Cyril :
- 

Hugo :
- Analyse exploratoire + Matrice de corrélation