Feature: External API Integration
  As a data engineer
  I want the DAGs to successfully fetch data from external providers
  So that ingestion pipelines can run end-to-end

  Scenario: Fetch data from eco2mix RTE download endpoint
    Given the eco2mix RTE download URL is accessible
    When I request the annual file for a valid year
    Then I should receive a valid zip archive

  Scenario: Fetch weather data from Open-Meteo API
    Given the Open-Meteo archive API is accessible
    When I request hourly weather data for Paris
    Then I should receive valid JSON with weather measurements
