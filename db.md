# Documentation des Tables PostgreSQL — Pipeline EDF MSPR3

Ce document détaille l'ensemble des tables créées et transformées tout au long du pipeline, depuis l'ingestion des données brutes jusqu'au feature store d'entraînement et de prédiction.

---

## Sommaire des Tables (ordre chronologique du pipeline)

| # | Table | Pipeline | Objectif |
|---|-------|----------|----------|
| 1 | `eco2mix_files` | Data Ingestion | Log de déduplication (fichiers nationaux) |
| 2 | `eco2mix_raw` | Data Ingestion | Données brutes de consommation nationale (RTE) |
| 3 | `weather_log` | Data Ingestion | Log d'ingestion météo par année |
| 4 | `weather_data` | Data Ingestion | Données météo horaires (Open-Meteo) |
| 5 | `conso_clean` | Data Ingestion (cleaning) | Consommation nettoyée + features temporelles |
| 6 | `aggregated_conso_weather` | Data Ingestion (aggregation) | Consommation + météo agrégées |
| 7 | `eco2mix_live_files` | Live Ingestion | Log de déduplication (fichiers live) |
| 8 | `eco2mix_live_raw` | Live Ingestion | Données brutes live (temps réel / J-1) |
| 9 | `conso_live_checkpoint` | Live Ingestion | Checkpoint pour ingestion incrémentale live |
| 10 | `eco2mix_region_log` | Régions Ingestion | Log d'ingestion par région + année |
| 11 | `eco2mix_region_raw` | Régions Ingestion | Données brutes de consommation par région |
| 12 | `conso_clean_region` | Régions Ingestion (cleaning) | Consommation régionale nettoyée + features |
| 13 | `city_region_mapping` | Régions Feature Store | Mapping ville ↔ région administrative |
| 14 | `agg_conso_meteo_features` | Feature Store (national) | Features prêtes pour l'entraînement / prédiction |
| 15 | `agg_conso_meteo_features_{region}` | Feature Store (régions) | Features par région (13 tables) |
| 16 | `batch_predictions` | Batch Prediction | Prédictions nationales (nom dynamique) |
| 17 | `batch_predictions_{params}_{cities}` | Batch Prediction (régions) | Prédictions par région |

---

## Phase 1 : Data Ingestion DAG
### Tables créées dans `ingestion_job`

---

### 1. `eco2mix_files` — Table de log (déduplication)

**Créée par** : [`dags/src/db/ingestion_postgre.py`](dags/src/db/ingestion_postgre.py) — `create_tables()`

**Objectif** : Éviter la ré-ingestion des fichiers déjà traités via checksum MD5.

| Colonne | Type | Contraintes | Description |
|---------|------|------------|-------------|
| `filename` | `TEXT` | `PRIMARY KEY` | Nom du fichier XLS/XLSX/CSV ingéré |
| `checksum` | `TEXT` | | Empreinte MD5 du fichier |
| `ingested_at` | `TIMESTAMP` | `DEFAULT NOW()` | Horodatage de l'ingestion |

---

### 2. `eco2mix_raw` — Table brute de consommation nationale

**Créée par** : [`dags/src/db/ingestion_postgre.py`](dags/src/db/ingestion_postgre.py) — `create_tables()`

**Objectif** : Stocker les données de consommation électrique nationale issues des fichiers RTE éCO2mix (format XLS/CSV), depuis 2012.

**Transformation appliquée** :
1. Téléchargement et extraction via `download_and_extract(start_year=2012)`
2. Chargement via `_load_single_file()` — détection automatique du séparateur CSV, nettoyage des noms de colonnes
3. Normalisation des colonnes (`clean_dataframe()`) :
   - Remplacement des valeurs `"ND"`, `"None"`, `"nan"` → `pd.NA`
   - Renommage `hydraulique_fil_de_leeau_eclusee` → `hydraulique_fil_de_leau_eclusee`
   - Réindexation sur 43 colonnes attendues
   - Typage automatique : si >30% de valeurs numériques → cast numérique, sinon `TEXT`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `perimetre` | `TEXT` | Périmètre géographique |
| `nature` | `TEXT` | Nature de la donnée (Brut, corrigé, etc.) |
| `date` | `TEXT` | Date au format texte |
| `heures` | `TEXT` | Heure au format texte |
| `consommation` | `INTEGER` | Consommation électrique totale (MW) |
| `prevision_j_1` | `INTEGER` | Prévision J-1 |
| `prevision_j` | `INTEGER` | Prévision J |
| `fioul` | `INTEGER` | Production fioul (MW) |
| `charbon` | `INTEGER` | Production charbon (MW) |
| `gaz` | `INTEGER` | Production gaz (MW) |
| `nucleaire` | `INTEGER` | Production nucléaire (MW) |
| `eolien` | `INTEGER` | Production éolienne (MW) |
| `solaire` | `INTEGER` | Production solaire (MW) |
| `hydraulique` | `INTEGER` | Production hydraulique (MW) |
| `pompage` | `INTEGER` | Pompage (MW) |
| `bioenergies` | `INTEGER` | Production bioénergies (MW) |
| `ech_physiques` | `INTEGER` | Échanges physiques (MW) |
| `taux_de_co2` | `INTEGER` | Taux de CO2 (g/kWh) |
| `ech_comm_angleterre` | `INTEGER` | Échange commercial Angleterre |
| `ech_comm_espagne` | `INTEGER` | Échange commercial Espagne |
| `ech_comm_italie` | `INTEGER` | Échange commercial Italie |
| `ech_comm_suisse` | `INTEGER` | Échange commercial Suisse |
| `ech_comm_allemagne_belgique` | `INTEGER` | Échange commercial Allemagne/Belgique |
| `fioul_tac` | `INTEGER` | Fioul TAC |
| `fioul_cogen` | `INTEGER` | Fioul cogénération |
| `fioul_autres` | `INTEGER` | Autres fioul |
| `gaz_tac` | `INTEGER` | Gaz TAC |
| `gaz_cogen` | `INTEGER` | Gaz cogénération |
| `gaz_ccg` | `INTEGER` | Gaz CCG (Cycle Combiné) |
| `gaz_autres` | `INTEGER` | Autres gaz |
| `hydraulique_fil_de_leau_eclusee` | `INTEGER` | Hydraulique fil de l'eau + éclusée |
| `hydraulique_lacs` | `INTEGER` | Hydraulique lacs |
| `hydraulique_step_turbinage` | `INTEGER` | Hydraulique STEP turbinage |
| `bioenergies_dechets` | `INTEGER` | Bioénergies déchets |
| `bioenergies_biomasse` | `INTEGER` | Bioénergies biomasse |
| `bioenergies_biogaz` | `INTEGER` | Bioénergies biogaz |
| `stockage_batterie` | `TEXT` | Stockage batterie |
| `destockage_batterie` | `INTEGER` | Déstockage batterie |
| `eolien_terrestre` | `INTEGER` | Éolien terrestre |
| `eolien_offshore` | `INTEGER` | Éolien offshore |
| `source_file` | `TEXT` | Nom du fichier source |

---

### 3. `weather_log` — Table de log météo

**Créée par** : [`dags/src/db/ingestion_weather.py`](dags/src/db/ingestion_weather.py) — `create_table()`

**Objectif** : Tracker les années déjà ingérées pour la météo.

| Colonne | Type | Contraintes | Description |
|---------|------|------------|-------------|
| `year` | `INTEGER` | `PRIMARY KEY` | Année ingérée |
| `ingested_at` | `TIMESTAMP` | `DEFAULT NOW()` | Horodatage |

---

### 4. `weather_data` — Données météo

**Créée par** : [`dags/src/db/ingestion_weather.py`](dags/src/db/ingestion_weather.py) — `create_table()`

**Objectif** : Données météo horaires par ville provenant de l'API Open-Meteo (2012-2023).

**Source** : API Open-Meteo, récupérée via `fetch_weather(start_date, end_date)` qui interroge plusieurs villes françaises.

**Transformation** :
- Conversion `date` → `datetime` (`pd.to_datetime`)
- Suppression de la colonne `date` d'origine
- Sélection des colonnes météo pertinentes

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `city` | `TEXT` | Ville de la mesure météo |
| `datetime` | `TIMESTAMP` | Date/heure de la mesure |
| `temperature_2m` | `FLOAT` | Température à 2m (°C) |
| `relative_humidity_2m` | `FLOAT` | Humidité relative à 2m (%) |
| `snowfall` | `FLOAT` | Chutes de neige (mm) |
| `precipitation` | `FLOAT` | Précipitations (mm) |
| `weather_code` | `INTEGER` | Code météo WMO |

---

### Table créée dans `cleanning_job`

---

### 5. `conso_clean` — Consommation nettoyée avec features temporelles

**Créée par** : [`dags/src/db/ingestion_clean_data.py`](dags/src/db/ingestion_clean_data.py) — `create_table()`

**Objectif** : Données de consommation nettoyées et enrichies de features temporelles, prêtes pour l'agrégation.

**Transformation appliquée** (via `create_features()` → `features.py`) :

1. **Aggrégation horaire** (`aggregate_hourly`) :
   - Création d'un `datetime` à partir de `date + heures`
   - Regroupement par heure (`hour_ts`)
   - Moyenne des colonnes numériques
   - `first()` pour les colonnes non-numériques
   - Suppression des lignes en double temporellement

2. **Feature engineering temporel** :
   - `year` : année extraite du datetime
   - `hour` : heure extraite
   - `day` : jour du mois
   - `month` : mois
   - `dayofweek` : jour de la semaine (0=lundi, 6=dimanche)
   - `weekend` : indicateur binaire (1 si samedi/dimanche)

3. **Nettoyage** :
   - Suppression des colonnes `perimetre`, `nature`, `source_file`, `date`, `heures`, `datetime`
   - Remplissage des valeurs nulles par 0 (`fillna(0)`)

**Note** : La table est vidée (`TRUNCATE`) puis ré-insérée à chaque exécution.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `consommation` | `FLOAT` | Consommation moyenne horaire (MW) |
| `prevision_j_1` | `FLOAT` | Prévision J-1 moyenne |
| `prevision_j` | `FLOAT` | Prévision J moyenne |
| `fioul` | `FLOAT` | Production fioul moyenne horaire |
| `charbon` | `FLOAT` | Production charbon moyenne horaire |
| `gaz` | `FLOAT` | Production gaz moyenne horaire |
| `nucleaire` | `FLOAT` | Production nucléaire moyenne horaire |
| `eolien` | `FLOAT` | Production éolienne moyenne horaire |
| `solaire` | `FLOAT` | Production solaire moyenne horaire |
| `hydraulique` | `FLOAT` | Production hydraulique moyenne horaire |
| `pompage` | `FLOAT` | Pompage moyen horaire |
| `bioenergies` | `FLOAT` | Production bioénergies moyenne horaire |
| `ech_physiques` | `FLOAT` | Échanges physiques moyens horaires |
| `taux_de_co2` | `FLOAT` | Taux de CO2 moyen (g/kWh) |
| `ech_comm_angleterre` | `FLOAT` | Échange commercial Angleterre moyen |
| `ech_comm_espagne` | `FLOAT` | Échange commercial Espagne moyen |
| `ech_comm_italie` | `FLOAT` | Échange commercial Italie moyen |
| `ech_comm_suisse` | `FLOAT` | Échange commercial Suisse moyen |
| `ech_comm_allemagne_belgique` | `FLOAT` | Échange commercial Allemagne/Belgique moyen |
| `fioul_tac` | `FLOAT` | Fioul TAC moyen |
| `fioul_cogen` | `FLOAT` | Fioul cogénération moyen |
| `fioul_autres` | `FLOAT` | Autres fioul moyen |
| `gaz_tac` | `FLOAT` | Gaz TAC moyen |
| `gaz_cogen` | `FLOAT` | Gaz cogénération moyen |
| `gaz_ccg` | `FLOAT` | Gaz CCG moyen |
| `gaz_autres` | `FLOAT` | Autres gaz moyen |
| `hydraulique_fil_de_leau_eclusee` | `FLOAT` | Hydraulique fil de l'eau moyen |
| `hydraulique_lacs` | `FLOAT` | Hydraulique lacs moyen |
| `hydraulique_step_turbinage` | `FLOAT` | Hydraulique STEP moyen |
| `bioenergies_dechets` | `FLOAT` | Bioénergies déchets moyen |
| `bioenergies_biomasse` | `FLOAT` | Bioénergies biomasse moyen |
| `bioenergies_biogaz` | `FLOAT` | Bioénergies biogaz moyen |
| `destockage_batterie` | `FLOAT` | Déstockage batterie moyen |
| `eolien_terrestre` | `FLOAT` | Éolien terrestre moyen |
| `eolien_offshore` | `FLOAT` | Éolien offshore moyen |
| `stockage_batterie` | `TEXT` | Stockage batterie |
| `year` | `INTEGER` | Année (feature temporelle) |
| `hour` | `INTEGER` | Heure (feature temporelle) |
| `day` | `INTEGER` | Jour du mois (feature temporelle) |
| `month` | `INTEGER` | Mois (feature temporelle) |
| `dayofweek` | `INTEGER` | Jour de la semaine 0-6 (feature temporelle) |
| `weekend` | `INTEGER` | 1 si weekend, 0 sinon (feature temporelle) |

---

### Table créée dans `aggregation_job`

---

### 6. `aggregated_conso_weather` — Table agrégée conso + météo

**Créée par** : [`dags/src/db/ingestion_conso_meteo_sql.py`](dags/src/db/ingestion_conso_meteo_sql.py) — `ingest_conso_meteo()`

**Objectif** : Joindre les données de consommation nettoyées avec les données météo nationales moyennes. C'est la table source pour l'entraînement et la prédiction.

**Transformation SQL** :
```sql
WITH conso AS (
    SELECT ... FROM conso_clean
),
weather_fr AS (
    SELECT
        datetime,
        AVG(temperature_2m)   AS temp_fr,
        AVG(relative_humidity_2m) AS hum_fr,
        AVG(snowfall)          AS snow_fr,
        AVG(precipitation)     AS rain_fr
    FROM weather_data
    GROUP BY datetime
)
SELECT ... FROM conso c
LEFT JOIN weather_fr w ON c.datetime = w.datetime
```

**Caractéristiques** :
- Créée via `CREATE TABLE ... AS SELECT` (donc supprimée puis recréée à chaque exécution via `DROP TABLE IF EXISTS`)
- Jointure LEFT JOIN sur `datetime` entre `conso_clean` et `weather_data` (moyennée au niveau national)
- Ajout d'un `id` via `ROW_NUMBER() OVER (ORDER BY c.datetime)` et d'une colonne `datetime` reconstruite via `make_timestamp(year, month, day, hour, 0, 0)`

| Colonne | Type | Provenance |
|---------|------|------------|
| `id` | `INTEGER` | `ROW_NUMBER()` (nouvel identifiant) |
| `conso_id` | `BIGINT` | `id` de `conso_clean` |
| `consommation` | `FLOAT` | `conso_clean` |
| `prevision_j_1` | `FLOAT` | `conso_clean` |
| `prevision_j` | `FLOAT` | `conso_clean` |
| `fioul` | `FLOAT` | `conso_clean` |
| `charbon` | `FLOAT` | `conso_clean` |
| `gaz` | `FLOAT` | `conso_clean` |
| `nucleaire` | `FLOAT` | `conso_clean` |
| `eolien` | `FLOAT` | `conso_clean` |
| `solaire` | `FLOAT` | `conso_clean` |
| `hydraulique` | `FLOAT` | `conso_clean` |
| `pompage` | `FLOAT` | `conso_clean` |
| `bioenergies` | `FLOAT` | `conso_clean` |
| `ech_physiques` | `FLOAT` | `conso_clean` |
| `taux_de_co2` | `FLOAT` | `conso_clean` |
| `ech_comm_angleterre` | `FLOAT` | `conso_clean` |
| `ech_comm_espagne` | `FLOAT` | `conso_clean` |
| `ech_comm_italie` | `FLOAT` | `conso_clean` |
| `ech_comm_suisse` | `FLOAT` | `conso_clean` |
| `ech_comm_allemagne_belgique` | `FLOAT` | `conso_clean` |
| `fioul_tac` | `FLOAT` | `conso_clean` |
| `fioul_cogen` | `FLOAT` | `conso_clean` |
| `fioul_autres` | `FLOAT` | `conso_clean` |
| `gaz_tac` | `FLOAT` | `conso_clean` |
| `gaz_cogen` | `FLOAT` | `conso_clean` |
| `gaz_ccg` | `FLOAT` | `conso_clean` |
| `gaz_autres` | `FLOAT` | `conso_clean` |
| `hydraulique_fil_de_leau_eclusee` | `FLOAT` | `conso_clean` |
| `hydraulique_lacs` | `FLOAT` | `conso_clean` |
| `hydraulique_step_turbinage` | `FLOAT` | `conso_clean` |
| `bioenergies_dechets` | `FLOAT` | `conso_clean` |
| `bioenergies_biomasse` | `FLOAT` | `conso_clean` |
| `bioenergies_biogaz` | `FLOAT` | `conso_clean` |
| `destockage_batterie` | `FLOAT` | `conso_clean` |
| `eolien_terrestre` | `FLOAT` | `conso_clean` |
| `eolien_offshore` | `FLOAT` | `conso_clean` |
| `stockage_batterie` | `TEXT` | `conso_clean` |
| `year` | `INTEGER` | `conso_clean` |
| `month` | `INTEGER` | `conso_clean` |
| `day` | `INTEGER` | `conso_clean` |
| `hour` | `INTEGER` | `conso_clean` |
| `dayofweek` | `INTEGER` | `conso_clean` |
| `weekend` | `INTEGER` | `conso_clean` |
| `datetime` | `TIMESTAMP` | Reconstruit via `make_timestamp()` |
| `temp_fr` | `FLOAT` | Moyenne nationale température (°C) — depuis `weather_data` |
| `hum_fr` | `FLOAT` | Moyenne nationale humidité (%) — depuis `weather_data` |
| `snow_fr` | `FLOAT` | Moyenne nationale neige (mm) — depuis `weather_data` |
| `rain_fr` | `FLOAT` | Moyenne nationale précipitations (mm) — depuis `weather_data` |

---

## Phase 1B : Live Data Ingestion (temps réel)

Ces tables sont créées par un pipeline séparé pour les données live (situé dans [`src/`](src/)).

---

### 7. `eco2mix_live_files` — Table de log live

**Créée par** : [`src/db/ingestion_live.py`](src/db/ingestion_live.py) — `create_tables()`

**Objectif** : Déduplication des fichiers live déjà ingérés.

| Colonne | Type | Contraintes | Description |
|---------|------|------------|-------------|
| `filename` | `TEXT` | `PRIMARY KEY` | Nom du fichier live |
| `checksum` | `TEXT` | | Empreinte MD5 |
| `ingested_at` | `TIMESTAMP` | `DEFAULT NOW()` | Horodatage |

---

### 8. `eco2mix_live_raw` — Données brutes live

**Créée par** : [`src/db/ingestion_live.py`](src/db/ingestion_live.py) — `create_tables()`

**Objectif** : Stocker les données de consommation en temps réel (J-1) avec le même schéma que `eco2mix_raw`.

**Schéma** : Identique à `eco2mix_raw` (43 colonnes + `id BIGSERIAL PRIMARY KEY`).

**Spécificités** :
- Filtre les lignes où `consommation` est NULL
- Ingestion incrémentale : ne garde que les lignes plus récentes que le dernier timestamp en base
- Téléchargement via `download_and_extract_live()`

---

### 9. `conso_live_checkpoint` — Checkpoint d'ingestion live

**Créée par** : [`src/db/ingestion_aggregated_live.py`](src/db/ingestion_aggregated_live.py) — `create_checkpoint_table()`

**Objectif** : Tracker le dernier horodatage traité pour l'ingestion incrémentale live vers `conso_clean`.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `last_datetime` | `TIMESTAMP` | Dernier horodatage traité |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Date de création |

---

## Phase 2 : Régions — Pipeline d'ingestion régionale

---

### 10. `eco2mix_region_log` — Table de log régionale

**Créée par** : [`src/db/regions_log.py`](src/db/regions_log.py) — `create_region_log_table()`

**Objectif** : Tracker l'ingestion par couple (région, année).

| Colonne | Type | Contraintes | Description |
|---------|------|------------|-------------|
| `region` | `TEXT` | `PRIMARY KEY` (composite) | Nom de la région |
| `year` | `INTEGER` | `PRIMARY KEY` (composite) | Année ingérée |
| `ingested_at` | `TIMESTAMP` | `DEFAULT NOW()` | Horodatage |

---

### 11. `eco2mix_region_raw` — Données brutes par région

**Créée par** : [`src/db/ingestion_regions_ecodata.py`](src/db/ingestion_regions_ecodata.py) — `create_region_table()`

**Objectif** : Données de consommation électrique par région administrative française, issues des fichiers RTE régionaux.

**Transformation** :
- Téléchargement via `download_all_regions()`
- Extraction du nom de région depuis le nom de fichier (pattern `RTE_{Region}_Annuel_XXXX`)
- Nettoyage : suppression colonnes `Unnamed`, remplacement `"ND"` → `pd.NA`
- Réindexation sur 15 colonnes attendues
- Cast numérique des colonnes de production

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `region` | `TEXT` | Nom de la région administrative |
| `perimetre` | `TEXT` | Périmètre géographique |
| `nature` | `TEXT` | Nature de la donnée |
| `date` | `DATE` | Date |
| `heures` | `TIME` | Heure |
| `consommation` | `FLOAT` | Consommation régionale (MW) |
| `thermique` | `FLOAT` | Production thermique (MW) |
| `nucleaire` | `FLOAT` | Production nucléaire (MW) |
| `eolien` | `FLOAT` | Production éolienne (MW) |
| `solaire` | `FLOAT` | Production solaire (MW) |
| `hydraulique` | `FLOAT` | Production hydraulique (MW) |
| `pompage` | `FLOAT` | Pompage (MW) |
| `bioenergies` | `FLOAT` | Production bioénergies (MW) |
| `ech_physiques` | `FLOAT` | Échanges physiques (MW) |
| `source_file` | `TEXT` | Nom du fichier source |

---

### 12. `conso_clean_region` — Consommation régionale nettoyée

**Créée par** : [`src/db/ingestion_regions_clean.py`](src/db/ingestion_regions_clean.py) — `create_region_clean_table()`

**Objectif** : Données de consommation régionale nettoyées avec features temporelles.

**Transformation** (via `create_region_features()` → `features.py`) :
1. Agrégation horaire par région : `groupby(["region", "hour_ts"])`
2. Calcul des features temporelles : `year`, `hour`, `day`, `month`, `dayofweek`, `weekend`
3. Suppression des colonnes `perimetre`, `nature`, `source_file`, `date`, `heures`, `datetime`
4. Remplissage des valeurs nulles par 0

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `region` | `TEXT` | Nom de la région |
| `consommation` | `FLOAT` | Consommation régionale moyenne horaire |
| `thermique` | `FLOAT` | Production thermique moyenne horaire |
| `nucleaire` | `FLOAT` | Production nucléaire moyenne horaire |
| `eolien` | `FLOAT` | Production éolienne moyenne horaire |
| `solaire` | `FLOAT` | Production solaire moyenne horaire |
| `hydraulique` | `FLOAT` | Production hydraulique moyenne horaire |
| `pompage` | `FLOAT` | Pompage moyen horaire |
| `bioenergies` | `FLOAT` | Production bioénergies moyenne horaire |
| `ech_physiques` | `FLOAT` | Échanges physiques moyens horaires |
| `year` | `INTEGER` | Année (feature) |
| `month` | `INTEGER` | Mois (feature) |
| `day` | `INTEGER` | Jour (feature) |
| `hour` | `INTEGER` | Heure (feature) |
| `dayofweek` | `INTEGER` | Jour de la semaine (feature) |
| `weekend` | `INTEGER` | Indicateur weekend (feature) |

---

## Phase 3 : Feature Store (préparation pour l'entraînement)

---

### 13. `city_region_mapping` — Mapping villes ↔ régions

**Créée par** : [`dags/src/db/city_region_mapping.py`](dags/src/db/city_region_mapping.py) — `create_city_region_mapping_table()`

**Objectif** : Associer chaque ville suivie par la météo à sa région administrative pour la prédiction par région.

**Mapping** (12 régions, 13 villes) :

| Région | Ville(s) représentative(s) |
|--------|---------------------------|
| Auvergne-Rhône-Alpes | Clermont-Ferrand |
| Bourgogne-Franche-Comté | Dijon |
| Bretagne | Brest |
| Centre-Val de Loire | Orléans |
| Grand-Est | Metz |
| Hauts-de-France | Lille |
| Île-de-France | Paris |
| Normandie | Rouen |
| Nouvelle-Aquitaine | Bordeaux |
| Occitanie | Montpellier |
| PACA | Marseille, Nice |
| Pays-de-la-Loire | Nantes |

| Colonne | Type | Contraintes | Description |
|---------|------|------------|-------------|
| `city` | `TEXT` | `PRIMARY KEY` | Ville |
| `region` | `TEXT` | `NOT NULL` | Région administrative |

---

### 14. `agg_conso_meteo_features` — Table de features nationale (Feature Store)

**Créée par** : [`dags/src/batch_prediction/data_prep.py`](dags/src/batch_prediction/data_prep.py) — `prepare_batch_prediction_data()`

**Sources** : `aggregated_conso_weather` → `training_dag` ou `batch_prediction_dag`

**Objectif** : Table de staging contenant uniquement les colonnes nécessaires à l'entraîrement et à la prédiction, avec les features sélectionnées, nettoyées et normalisées.

**Transformation** :
1. Sélection des colonnes features + colonnes utilitaires + target depuis `aggregated_conso_weather`
2. Remplacement des valeurs `"ND"` → `fillna(0)`
3. Création (si non existante) ou réutilisation de la table existante

**Colonnes** (définies dans [`training_dag.py`](dags/training_dag.py) et [`batch_prediction_dag.py`](dags/batch_prediction_dag.py)) :

**Features** (6 colonnes) :
| Colonne | Type | Description |
|---------|------|-------------|
| `temp_fr` | `DOUBLE PRECISION` | Température nationale moyenne |
| `snow_fr` | `DOUBLE PRECISION` | Neige nationale moyenne |
| `hour` | `INTEGER` | Heure du jour |
| `month` | `INTEGER` | Mois |
| `dayofweek` | `INTEGER` | Jour de la semaine |
| `weekend` | `INTEGER` | Indicateur weekend |

**Colonnes utilitaires** (5 colonnes) :
| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `INTEGER` | Identifiant de la ligne source |
| `conso_id` | `BIGINT` | Identifiant conso_clean |
| `datetime` | `TIMESTAMP` | Horodatage complet |
| `year` | `INTEGER` | Année |
| `day` | `INTEGER` | Jour du mois |

**Target** :
| Colonne | Type | Description |
|---------|------|-------------|
| `consommation` | `DOUBLE PRECISION` | Consommation réelle (variable cible) |

---

### 15. `agg_conso_meteo_features_{region}` — Feature store par région

**Créées par** : [`dags/src/db/city_region_mapping.py`](dags/src/db/city_region_mapping.py) — `build_region_feature_table()`

**Objectif** : Une table par région administrative contenant les features météo + consommation pour l'entraînement des modèles régionaux.

**Transformation SQL** :
```sql
CREATE TABLE IF NOT EXISTS agg_conso_meteo_features_{suffix} AS
SELECT
    ROW_NUMBER() OVER (ORDER BY w.datetime) AS id,
    w.city, cr.region, cr.consommation,
    w.temperature_2m, w.relative_humidity_2m,
    w.precipitation, w.snowfall, w.weather_code,
    EXTRACT(YEAR  FROM w.datetime)::INT AS year,
    EXTRACT(MONTH FROM w.datetime)::INT AS month,
    EXTRACT(DAY   FROM w.datetime)::INT AS day,
    EXTRACT(HOUR  FROM w.datetime)::INT AS hour,
    EXTRACT(DOW   FROM w.datetime)::INT AS dayofweek,
    CASE WHEN EXTRACT(DOW FROM w.datetime) IN (0,6) THEN 1 ELSE 0 END AS weekend,
    w.datetime
FROM weather_data w
JOIN city_region_mapping crm ON crm.city = w.city
JOIN conso_clean_region cr
    ON cr.region = crm.region
    AND cr.year = EXTRACT(YEAR  FROM w.datetime)
    AND cr.month = EXTRACT(MONTH FROM w.datetime)
    AND cr.day   = EXTRACT(DAY   FROM w.datetime)
    AND cr.hour  = EXTRACT(HOUR  FROM w.datetime)
WHERE crm.region = '{region}'
  AND w.city IN ({cities})
```

**Tables créées** (13 tables, suffix normalisé sans accents) :
- `agg_conso_meteo_features_auvergne_rhone_alpes`
- `agg_conso_meteo_features_bourgogne_franche_comte`
- `agg_conso_meteo_features_bretagne`
- `agg_conso_meteo_features_centre_val_de_loire`
- `agg_conso_meteo_features_grand_est`
- `agg_conso_meteo_features_hauts_de_france`
- `agg_conso_meteo_features_ile_de_france`
- `agg_conso_meteo_features_normandie`
- `agg_conso_meteo_features_nouvelle_aquitaine`
- `agg_conso_meteo_features_occitanie`
- `agg_conso_meteo_features_paca`
- `agg_conso_meteo_features_pays_de_la_loire`

**Index** : Chaque table a un index sur `(city, datetime)`.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `INTEGER` | Identifiant (ROW_NUMBER) |
| `city` | `TEXT` | Ville de la mesure météo |
| `region` | `TEXT` | Région administrative |
| `consommation` | `FLOAT` | Consommation régionale (MW) |
| `temperature_2m` | `FLOAT` | Température à 2m (°C) |
| `relative_humidity_2m` | `FLOAT` | Humidité relative (%) |
| `precipitation` | `FLOAT` | Précipitations (mm) |
| `snowfall` | `FLOAT` | Neige (mm) |
| `weather_code` | `INTEGER` | Code météo WMO |
| `year` | `INTEGER` | Année |
| `month` | `INTEGER` | Mois |
| `day` | `INTEGER` | Jour |
| `hour` | `INTEGER` | Heure |
| `dayofweek` | `INTEGER` | Jour de la semaine |
| `weekend` | `INTEGER` | Indicateur weekend |
| `datetime` | `TIMESTAMP` | Horodatage complet |

---

## Phase 4 : Prédiction (Batch Prediction)

---

### 16. `batch_predictions` (national) — Table de prédiction

**Créée par** : [`dags/src/batch_prediction/batch_prediction.py`](dags/src/batch_prediction/batch_prediction.py) — `batch_prediction()`

**Objectif** : Stocker les prédictions du modèle national (MODEL_EDF) chargé depuis MLflow.

**Nom dynamique** : `batch_predictions_{années}_{date_courante}_{artifact_path}_{run_date}`

**Transformation** :
1. Chargement du modèle depuis MLflow (meilleur modèle ou fallback)
2. Sélection des features depuis `agg_conso_meteo_features` avec filtres optionnels (années, mois, jours)
3. Remplacement `"ND"` → `fillna(0)`
4. Prédiction via `model.predict(X)`
5. Création d'une table avec nom dynamique via `create_table_from_dataframe()` (infère les types SQL depuis pandas)
6. Insertion des résultats

| Colonne | Type (inféré) | Description |
|---------|--------------|-------------|
| `temp_fr` | `DOUBLE PRECISION` | Température feature |
| `snow_fr` | `DOUBLE PRECISION` | Neige feature |
| `hour` | `INTEGER` | Heure feature |
| `month` | `INTEGER` | Mois feature |
| `dayofweek` | `INTEGER` | Jour semaine feature |
| `weekend` | `INTEGER` | Weekend feature |
| `prediction` | `DOUBLE PRECISION` | Consommation prédite (MW) |
| `datetime` | `TIMESTAMP` | Horodatage |

---

### 17. `batch_predictions_{params}_{cities}` (régions) — Prédictions par région

**Créée par** : [`dags/src/pipelines/prediction_consommation_regions.py`](dags/src/pipelines/prediction_consommation_regions.py) — `predict_all_regions()`

**Objectif** : Stocker les prédictions par région pour chaque modèle régional (MODEL_EDF_REGION_{region}).

**Nom dynamique** : `batch_predictions_{années}_{mois}_{jours}_{villes}`

**Schéma fixe** :
| Colonne | Type | Description |
|---------|------|-------------|
| `id` | `BIGSERIAL PK` | Identifiant unique |
| `city` | `TEXT` | Ville prédite |
| `region` | `TEXT` | Région |
| `datetime` | `TIMESTAMP` | Horodatage |
| `prediction` | `DOUBLE PRECISION` | Consommation prédite (MW) |
| `consommation_reelle` | `DOUBLE PRECISION` | Consommation réelle (MW) |
| `temperature_2m` | `DOUBLE PRECISION` | Température feature |
| `relative_humidity_2m` | `DOUBLE PRECISION` | Humidité feature |
| `precipitation` | `DOUBLE PRECISION` | Précipitations feature |
| `snowfall` | `DOUBLE PRECISION` | Neige feature |
| `weather_code` | `INTEGER` | Code météo feature |
| `hour` | `INTEGER` | Heure feature |
| `month` | `INTEGER` | Mois feature |
| `dayofweek` | `INTEGER` | Jour semaine feature |
| `weekend` | `INTEGER` | Weekend feature |

---

## MLflow — Modèles enregistrés

| Modèle | Type | Source d'entraînement |
|--------|------|----------------------|
| `MODEL_EDF` | National (toutes régions confondues) | `aggregated_conso_weather` |
| `MODEL_EDF_REGION_{suffix}` | Par région (13 modèles) | `agg_conso_meteo_features_{region}` |
| `fallback_{model}_{timestamp}` | Modèle de secours (2e meilleur) | `aggregated_conso_weather` |

**Expériences MLflow** :
- `EDF_Model_Experiment` — entraînement modèle national
- `EDF_Region_Model_Experiment` — entraînement modèles régionaux
- `Performance_Test` — tests de robustesse (injection de bruit)

---

## Résumé du flux de données (de l'ingestion au feature store)

```
eco2mix_raw ──► conso_clean ──► aggregated_conso_weather ──► agg_conso_meteo_features ──► [ENTRAÎNEMENT]
                    ▲                                                                    │
                    │                                                                    ▼
eco2mix_live_raw ───┘                                                          [PRÉDICTION → batch_predictions*]

weather_data ────────────────────────► aggregated_conso_weather
                    │
                    ▼
         agg_conso_meteo_features_{region} ──► [ENTRAÎNEMENT RÉGION]
                    │
                    ▼
         [PRÉDICTION RÉGION → batch_predictions*]

eco2mix_region_raw ──► conso_clean_region ──► agg_conso_meteo_features_{region}
                              ▲
                              │
                    city_region_mapping
```
