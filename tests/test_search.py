from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def custom_graph_and_locations(tmp_path: Path):
    locations_file = tmp_path / "locations.csv"
    link_file = tmp_path / "link.txt"

    locations_file.write_text(
        "ID,Latitude,Longitude,Category\n"
        "1,0.4,0.0,bank\n"
        "2,0.7,0.0,bank\n"
        "3,0.4,0.0,store\n"
        "4,1.5,1.5,bank\n",
        encoding="utf-8",
    )
    link_file.write_text(
        "0.0 0.0 0.0 1.0\n"
        "0.0 1.0 1.0 1.0\n"
        "0.0 0.0 1.0 0.0\n",
        encoding="utf-8",
    )

    main.DEFAULT_LOCATIONS_PATH = locations_file
    main.LOCATIONS_CACHE.clear()
    main.GRAPH_CACHE.clear()
    return link_file


def test_search_uses_road_distance_for_nearby_grid_mapped_locations(custom_graph_and_locations: Path):
    link_file = custom_graph_and_locations

    result = main.search_core(0.1, 0.1, "bank", 0.8, str(link_file))

    assert result == [1, 2]


def test_road_distance_is_ranked_over_euclidean_distance(tmp_path: Path):
    locations_file = tmp_path / "locations.csv"
    link_file = tmp_path / "link.txt"

    locations_file.write_text(
        "ID,Latitude,Longitude,Category\n"
        "1,0.3,0.0,bank\n"
        "2,0.0,0.2,bank\n",
        encoding="utf-8",
    )
    link_file.write_text(
        "0.0 0.0 0.0 0.1\n"
        "0.0 0.1 0.1 0.1\n"
        "0.1 0.1 0.2 0.1\n"
        "0.2 0.1 0.2 0.0\n"
        "0.0 0.1 0.0 0.2\n"
        "0.0 0.2 0.0 0.3\n",
        encoding="utf-8",
    )

    main.DEFAULT_LOCATIONS_PATH = locations_file
    main.LOCATIONS_CACHE.clear()
    main.GRAPH_CACHE.clear()

    result = main.search_core(0.0, 0.0, "bank", 0.5, str(link_file))

    assert result == [1, 2]


def test_search_api_returns_ids(custom_graph_and_locations: Path):
    app = main.app
    client = TestClient(app)

    response = client.get(
        "/search/",
        params={"lat": 0.1, "long": 0.1, "cat": "bank",
                "rad": 0.8, "link": str(custom_graph_and_locations)},
    )

    assert response.status_code == 200
    assert response.json() == {"ids": [1, 2]}


def test_invalid_radius_returns_400(custom_graph_and_locations: Path):
    client = TestClient(main.app)

    response = client.get(
        "/search/",
        params={"lat": 0.1, "long": 0.1, "cat": "bank", "rad": -
                0.5, "link": str(custom_graph_and_locations)},
    )

    assert response.status_code == 400


def test_search_excludes_candidates_in_unreachable_components(tmp_path: Path):
    locations_file = tmp_path / "locations.csv"
    link_file = tmp_path / "link.txt"

    locations_file.write_text(
        "ID,Latitude,Longitude,Category\n"
        "1,10.1,10.1,bank\n",
        encoding="utf-8",
    )
    link_file.write_text(
        "0.0 0.0 0.0 1.0\n"
        "10.0 10.0 10.0 11.0\n",
        encoding="utf-8",
    )

    main.DEFAULT_LOCATIONS_PATH = locations_file
    main.LOCATIONS_CACHE.clear()
    main.GRAPH_CACHE.clear()

    result = main.search_core(0.0, 0.0, "bank", 20.0, str(link_file))

    assert result == []


def test_off_graph_candidate_is_snapped_to_the_nearest_road_node(tmp_path: Path):
    locations_file = tmp_path / "locations.csv"
    link_file = tmp_path / "link.txt"

    locations_file.write_text(
        "ID,Latitude,Longitude,Category\n"
        "1,0.05,0.00,bank\n",
        encoding="utf-8",
    )
    link_file.write_text(
        "0.0 0.0 0.0 1.0\n",
        encoding="utf-8",
    )

    main.DEFAULT_LOCATIONS_PATH = locations_file
    main.LOCATIONS_CACHE.clear()
    main.GRAPH_CACHE.clear()

    result = main.search_core(0.1, 0.1, "bank", 0.5, str(link_file))

    assert result == [1]


def test_disconnected_component_is_excluded_even_if_within_euclidean_radius(tmp_path: Path):
    locations_file = tmp_path / "locations.csv"
    link_file = tmp_path / "link.txt"

    locations_file.write_text(
        "ID,Latitude,Longitude,Category\n"
        "1,0.2,0.0,bank\n"
        "2,10.1,10.0,bank\n",
        encoding="utf-8",
    )
    link_file.write_text(
        "0.0 0.0 0.0 1.0\n"
        "0.0 1.0 1.0 1.0\n"
        "10.0 10.0 10.0 11.0\n",
        encoding="utf-8",
    )

    main.DEFAULT_LOCATIONS_PATH = locations_file
    main.LOCATIONS_CACHE.clear()
    main.GRAPH_CACHE.clear()

    result = main.search_core(0.1, 0.1, "bank", 20.0, str(link_file))

    assert result == [1]
