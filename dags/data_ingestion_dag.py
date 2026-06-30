import uuid
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy_operator import DummyOperator

import sys
import os

from src.data_ingestion import run_full_pipeline

from src.db.ingestion_conso_meteo_sql import ingest_conso_meteo
from src.db.ingestion_clean_data import ingest_features


correlation_id = uuid.uuid4()

MY_LOCAL_ASSETS = "/opt/airflow/dags"
DATA_DIR = "/opt/airflow/dags/src/data_folder"


with DAG(
        dag_id="data_ingestion_dag",
        schedule_interval=None,
        start_date=datetime(2022, 3, 3,),
        catchup=False,
        description="DAG for loading weather and consumption data into PostgreSQL",
        tags=["data", "ingestion", "postgresql"]) as dag:

    start = DummyOperator(task_id="start")



    ingestion_job = PythonOperator(
        task_id="ingestion_job",
        python_callable=run_full_pipeline,
        op_kwargs={
            "start_date": "2020-01-01",
            "end_date": "2022-12-31", 
            "data_dir": DATA_DIR,
            "cleanup": True
        },
        do_xcom_push=False,
        dag=dag
    )

    cleanning_job = PythonOperator(
        task_id="cleanning_job",
        python_callable=ingest_features,
        do_xcom_push=False,
        dag=dag
    )

    aggregation_job = PythonOperator(
        task_id="aggregation_job",
        python_callable=ingest_conso_meteo,
        do_xcom_push=False,
        dag=dag
    )


    complete = DummyOperator(task_id="complete")

    start >> ingestion_job >> cleanning_job >> aggregation_job >> complete