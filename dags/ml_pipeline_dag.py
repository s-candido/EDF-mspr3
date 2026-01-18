import uuid
from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.dummy_operator import DummyOperator


# Correlation id for training job (this can be also found on MLFLow tracking)
correlation_id = uuid.uuid4()


with DAG(
        dag_id="main_dag",
        schedule_interval=None,
        start_date=datetime(2022, 3, 3,),
        catchup=False) as dag:

    start = DummyOperator(task_id="start")

    # Task for running data preprocessing task
    preprocessing_task = BashOperator(
        task_id="main_script_job",
        bash_command="python ${MY_LOCAL_ASSETS}/src/main.py",
        dag=dag
    )

    # Task running our ML training job
    training_task = BashOperator(
        task_id="push_model_to_mlflow_job",
        bash_command="python ${MY_LOCAL_ASSETS}/src/mlflow/push_model_to_mlflow.py --model_path ${MY_LOCAL_ASSETS}/src/models/model.joblib",
        dag=dag
    )

    complete = DummyOperator(task_id="complete")

    # Linear pipeline: start -> preprocessing -> training -> complete
    start >> preprocessing_task >> training_task >> complete