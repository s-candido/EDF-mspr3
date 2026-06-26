# Pipeline Airflow — Prédiction de consommation électrique

## 1) Ingestion des données brutes — `eco2mix_raw` + `weather_data`

Les données de consommation électrique sont téléchargées depuis l'API éCO2mix de RTE (fichiers ZIP annuels, de 2012 à aujourd'hui), extraites et chargées dans la table **eco2mix_raw**. Parallèlement, les données météorologiques horaires (température, humidité, précipitations, neige) sont récupérées via l'API Open-Meteo pour 21 villes françaises et stockées dans la table **weather_data**. Un système de logs évite les doublons (checksum pour eco2mix, année pour la météo).

## 2) Nettoyage et feature engineering — `conso_clean`

Les données brutes d'eco2mix sont nettoyées : remplacement des valeurs "ND", normalisation des noms de colonnes, typage automatique (numérique vs texte). Les enregistrements sont agrégés à l'heure, et des features temporelles sont calculées :
- `year`, `month`, `day`, `hour`
- `dayofweek`, `weekend` (booléen)

Le résultat est stocké dans la table **conso_clean**.

| Feature      | Description                          |
|-------------|--------------------------------------|
| consommation | Consommation électrique (cible)      |
| prevision_j_1 | Prévision J-1                      |
| fioul, gaz, nucleaire, eolien… | Mix de production |
| year, month, day, hour, dayofweek, weekend | Features temporelles |

## 3) Agrégation conso + météo — `aggregated_conso_weather`

Les données de consommation nettoyées sont jointes aux données météorologiques via une requête SQL qui agrège la météo au niveau national (moyenne des 21 villes). Cette jointure produit la table **aggregated_conso_weather**, table de référence contenant pour chaque heure : la consommation, le détail du mix électrique, les prévisions J et J-1, et les variables météo nationales (température, humidité, neige, pluie).

| Colonne       | Source     |
|---------------|------------|
| consommation, fioul, gaz, nucleaire… | conso_clean |
| temp_fr, hum_fr, snow_fr, rain_fr   | weather_data (moyenne France) |
| year, month, day, hour, dayofweek, weekend | Features temporelles |

## 4) Sélection des features — `agg_conso_meteo_features`

Les colonnes utiles à la modélisation sont extraites de `aggregated_conso_weather` et préparées dans une table dédiée **agg_conso_meteo_features**. Seules les features les plus pertinentes sont conservées pour l'entraînement :

| Feature   | Type     | Rôle |
|-----------|----------|------|
| temp_fr   | float    | Température moyenne France |
| snow_fr   | float    | Enneigement moyen France |
| hour      | int      | Heure de la journée (0–23) |
| month     | int      | Mois (1–12) |
| dayofweek | int      | Jour de la semaine (0–6) |
| weekend   | bool     | 1 si samedi/dimanche |

## 5) Entraînement des modèles — MLflow Registry

Trois algorithmes de régression sont entraînés sur les données de plusieurs années (configurable, ex. 2020–2022) :

- **LinearRegression** — Régression linéaire classique
- **RandomForest** — Forêt aléatoire (200 arbres)
- **KNN** — K plus proches voisins (k=7)

Chaque modèle est évalué sur un jeu de test (20%) avec trois métriques :

| Métrique      | Rôle |
|---------------|------|
| **R²**        | Qualité globale de la prédiction |
| **RMSE**      | Erreur quadratique moyenne |
| **MAPE**      | Erreur absolue moyenne en % |

Le meilleur modèle (meilleur R²) est enregistré dans le **MLflow Model Registry** sous le nom `MODEL_EDF` avec ses hyperparamètres, ses métriques et la liste des features utilisées.

## 6) Prédiction par lots — `batch_predictions`

Le meilleur modèle est chargé depuis MLflow et exécute des prédictions sur les données préparées (`agg_conso_meteo_features`). Les prédictions sont stockées dans une table **batch_predictions** horodatée, permettant la comparaison entre consommation réelle et consommation prédite.

## 7) Pipeline par région (variante) — Modèles régionaux

Une variante du pipeline entraîne un modèle **par région administrative** (12 régions). Les villes sont regroupées par région via une table de correspondance, et chaque région dispose de son propre modèle enregistré dans MLflow (`MODEL_EDF_REGION_{region}`). Les prédictions régionales sont ensuite agrégées au niveau national (somme des moyennes régionales) pour obtenir une prédiction nationale.

Les features utilisées par région incluent en plus les données météo locales (température, humidité, précipitations, neige, code météo) non agrégées au niveau national.

---

**Diagramme de flux :**

```
eco2mix (RTE)  ──►  eco2mix_raw  ──►  conso_clean ──┐
                                                      ├──► aggregated_conso_weather ──► agg_conso_meteo_features ──► Modèle (MLflow)
Open-Meteo API ──►  weather_data ─────────────────────┘                                                                    │
                                                                                                                    ┌─────┘
                                                                                                                    ▼
                                                                                                          batch_predictions
```
