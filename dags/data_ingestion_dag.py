import uuid
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy_operator import DummyOperator

import sys
import os

from src.db_ingestion import run_full_pipeline

correlation_id = uuid.uuid4()

MY_LOCAL_ASSETS = "/opt/airflow/dags"

with DAG(
        dag_id="data_ingestion_dag",
        schedule_interval=None,
        start_date=datetime(2022, 3, 3,),
        catchup=False,
        description="DAG for loading weather and consumption data into PostgreSQL",
        tags=["data", "ingestion", "postgresql"]) as dag:

    start = DummyOperator(task_id="start")



    ingestion_job = PythonOperator(
        task_id="full_data_pipeline",
        python_callable=run_full_pipeline,
        op_kwargs={
            "start_date": "2020-01-01",
            "end_date": "2020-12-31", 
            "data_dir": "../data"
        },
        do_xcom_push=False,
        dag=dag
    )

    complete = DummyOperator(task_id="complete")

    start >> ingestion_job >> complete