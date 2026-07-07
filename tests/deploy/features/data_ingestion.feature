Feature: Data Ingestion into PostgreSQL
  As a data engineer
  I want the ingestion pipeline to write data into PostgreSQL
  So that downstream consumers can query it

  Scenario: Insert dummy eco2mix data into the database
    Given a PostgreSQL database is running and accessible
    When I run the data ingestion pipeline with a dummy CSV row
    Then the row should be persisted in the eco2mix_raw table
