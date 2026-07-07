"""
Tests for dags/src/db/city_region_mapping.py.

Covers: all_regions, all_cities, get_cities_for_region, get_region_for_city, normalize_region_name
Used by the batch_prediction_dag_by_region.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.db.city_region_mapping import (
    all_regions,
    all_cities,
    get_cities_for_region,
    get_region_for_city,
    normalize_region_name,
    REGION_CITIES,
)


class TestRegionListing:
    def test_all_regions_returns_sorted_list(self):
        regions = all_regions()
        assert isinstance(regions, list)
        assert len(regions) > 0
        assert regions == sorted(regions)

    def test_all_regions_contains_expected_regions(self):
        regions = all_regions()
        for expected in [
            "Île-de-France",
            "Auvergne-Rhône-Alpes",
            "PACA",
            "Bretagne",
            "Nouvelle-Aquitaine",
        ]:
            assert expected in regions

    def test_all_regions_count(self):
        regions = all_regions()
        assert len(regions) == 12


class TestCityListing:
    def test_all_cities_returns_sorted_list(self):
        cities = all_cities()
        assert isinstance(cities, list)
        assert len(cities) > 0

    def test_all_cities_contains_expected_cities(self):
        cities = all_cities()
        for expected in ["Paris", "Marseille", "Nice", "Bordeaux", "Lille"]:
            assert expected in cities

    def test_all_cities_no_duplicates(self):
        cities = all_cities()
        assert len(cities) == len(set(cities))


class TestGetCitiesForRegion:
    def test_get_cities_for_known_region(self):
        cities = get_cities_for_region("Île-de-France")
        assert cities == ["Paris"]

    def test_get_cities_for_paca_returns_two(self):
        cities = get_cities_for_region("PACA")
        assert cities == ["Marseille", "Nice"]

    def test_get_cities_for_unknown_region(self):
        cities = get_cities_for_region("UnknownRegion")
        assert cities == []

    def test_get_cities_every_region_has_at_least_one(self):
        for region in all_regions():
            cities = get_cities_for_region(region)
            assert len(cities) >= 1, f"{region} has no cities"


class TestGetRegionForCity:
    def test_get_region_for_paris(self):
        assert get_region_for_city("Paris") == "Île-de-France"

    def test_get_region_for_marseille(self):
        assert get_region_for_city("Marseille") == "PACA"

    def test_get_region_for_unknown_city(self):
        assert get_region_for_city("Nowhere") is None

    def test_every_city_has_region(self):
        for city in all_cities():
            region = get_region_for_city(city)
            assert region is not None, f"{city} has no region"


class TestNormalizeRegionName:
    def test_ile_de_france(self):
        assert normalize_region_name("Île-de-France") == "ile_de_france"

    def test_auvergne_rhone_alpes(self):
        assert (
            normalize_region_name("Auvergne-Rhône-Alpes") == "auvergne_rhone_alpes"
        )

    def test_paca(self):
        assert normalize_region_name("PACA") == "paca"

    def test_pays_de_la_loire(self):
        assert normalize_region_name("Pays-de-la-Loire") == "pays_de_la_loire"

    def test_bretagne_no_accent(self):
        assert normalize_region_name("Bretagne") == "bretagne"

    def test_normalize_strips_whitespace(self):
        assert normalize_region_name("  Normandie  ") == "normandie"

    def test_inverse_mapping_consistency(self):
        """normalize_region_name should be idempotent for already-normalized names."""
        normalized = normalize_region_name("Île-de-France")
        assert normalize_region_name(normalized) == normalized


class TestMappingConsistency:
    def test_all_cities_mapped_to_existing_region(self):
        for city in all_cities():
            region = get_region_for_city(city)
            assert region in REGION_CITIES
            assert city in REGION_CITIES[region]

    def test_no_extra_keys_in_region_cities(self):
        known_regions = set(all_regions())
        for region in REGION_CITIES:
            assert region in known_regions

    def test_consistent_region_names(self):
        """Every region name in REGION_CITIES keys should match its own normalized form
        when processed through the inverse lookup."""
        for region in REGION_CITIES:
            cities = REGION_CITIES[region]
            for city in cities:
                assert get_region_for_city(city) == region
