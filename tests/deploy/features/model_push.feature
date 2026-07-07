Feature: MLflow Model Push
  As a data scientist
  I want Airflow DAGs to log trained models into MLflow
  So that models are tracked and available for batch prediction

  Scenario: Log a dummy model to MLflow
    Given MLflow is running and accessible
    When I create an experiment and log a dummy model with a metric
    Then the experiment and run should appear in MLflow
    And the logged metric value should be readable
