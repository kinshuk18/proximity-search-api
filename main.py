from __future__ import annotations

import csv
import math
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOCATIONS_PATH = BASE_DIR / "locations.csv"
DEFAULT_LINK_PATH = BASE_DIR / "link.txt"

Coord = Tuple[float, float]
LocationEntry = Tuple[int, float, float]


class SearchRequest(BaseModel):
    lat: float
    long: float
    cat: str
    rad: float
    link: Optional[str] = None


def normalize_category(value: str) -> str:
    return value.strip().casefold()


def resolve_path(raw: Optional[str], default: Path) -> Path:
    if raw is None or not raw.strip():
        return default
    candidate = Path(raw.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()
    return candidate


@lru_cache(maxsize=None)
def load_locations(path: str) -> Dict[str, Tuple[LocationEntry, ...]]:
    categories: DefaultDict[str, List[LocationEntry]] = defaultdict(list)
    data_path = Path(path)
    if not data_path.exists():
        return {}
    with data_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return {}
        for row in reader:
            if not row or len(row) < 4:
                continue
            try:
                location_id = int(row[0].strip())
                latitude = float(row[1].strip())
                longitude = float(row[2].strip())
                category = normalize_category(row[3].strip())
            except ValueError:
                continue
            categories[category].append((location_id, latitude, longitude))
    return {key: tuple(value) for key, value in categories.items()}


@lru_cache(maxsize=None)
def load_graph(path: str) -> Dict[Coord, Tuple[Coord, ...]]:
    graph: DefaultDict[Coord, set[Coord]] = defaultdict(set)
    data_path = Path(path)
    if not data_path.exists():
        return {}
    with data_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) != 4:
                continue
            try:
                lon_a, lat_a, lon_b, lat_b = map(float, tokens)
            except ValueError:
                continue
            node_a = (lon_a, lat_a)
            node_b = (lon_b, lat_b)
            graph[node_a].add(node_b)
            graph[node_b].add(node_a)
    return {node: tuple(sorted(neighbors)) for node, neighbors in graph.items()}


LOCATIONS_CACHE: Dict[Path, Dict[str, Tuple[LocationEntry, ...]]] = {}
GRAPH_CACHE: Dict[Path, Dict[Coord, Set[Coord]]] = {}


def get_locations(category: str) -> Tuple[LocationEntry, ...]:
    normalized = normalize_category(category)
    loc_path = DEFAULT_LOCATIONS_PATH
    if loc_path not in LOCATIONS_CACHE:
        LOCATIONS_CACHE[loc_path] = load_locations(loc_path)
    return LOCATIONS_CACHE.get(loc_path, {}).get(normalized, ())


def get_graph(path: Path) -> Dict[Coord, Set[Coord]]:
    if path not in GRAPH_CACHE:
        GRAPH_CACHE[path] = load_graph(path)
    return GRAPH_CACHE[path]


def snap_to_graph_node(coord: Coord, graph: Mapping[Coord, Iterable[Coord]]) -> Optional[Coord]:
    if not graph:
        return None
    if coord in graph:
        return coord
    best_node: Optional[Coord] = None
    best_distance = math.inf
    for node in graph:
        distance = math.hypot(node[0] - coord[0], node[1] - coord[1])
        if distance < best_distance or (math.isclose(distance, best_distance, rel_tol=1e-12, abs_tol=1e-12) and (best_node is None or node < best_node)):
            best_distance = distance
            best_node = node
    return best_node


def bfs_distances(start: Coord, graph: Mapping[Coord, Iterable[Coord]]) -> Dict[Coord, int]:
    if not graph:
        return {}
    queue: deque[Coord] = deque([start])
    distances: Dict[Coord, int] = {start: 0}
    while queue:
        current = queue.popleft()
        depth = distances[current]
        for neighbor in graph.get(current, ()):  # type: ignore[arg-type]
            if neighbor not in distances:
                distances[neighbor] = depth + 1
                queue.append(neighbor)
    return distances


def search_core(lat: float, long: float, cat: str, rad: float, link: Optional[str]) -> List[int]:
    if not math.isfinite(lat) or not math.isfinite(long) or not math.isfinite(rad):
        raise HTTPException(
            status_code=400, detail="lat, long, and rad must be finite numbers.")
    if rad < 0.0:
        raise HTTPException(
            status_code=400, detail="rad must be non-negative.")
    if not cat or not cat.strip():
        raise HTTPException(status_code=400, detail="cat must be non-empty.")

    link_path = resolve_path(link, DEFAULT_LINK_PATH)
    if not link_path.exists():
        raise HTTPException(
            status_code=404, detail=f"link file not found: {link_path}")

    graph = get_graph(link_path)
    if not graph:
        return []

    query_coord = (float(long), float(lat))
    start_node = snap_to_graph_node(query_coord, graph)
    if start_node is None:
        return []

    distances = bfs_distances(start_node, graph)
    if not distances:
        return []

    results: List[Tuple[int, float, int]] = []
    for location_id, point_lat, point_lon in get_locations(cat):
        candidate_coord = (float(point_lon), float(point_lat))
        snapped_node = snap_to_graph_node(candidate_coord, graph)
        if snapped_node is None or snapped_node not in distances:
            continue
        straight_line = math.hypot(point_lat - lat, point_lon - long)
        if straight_line > rad:
            continue
        road_distance = distances[snapped_node]
        results.append((location_id, straight_line, road_distance))

    results.sort(key=lambda item: (item[2], item[1], item[0]))
    return [location_id for location_id, _, _ in results[:10]]


app = FastAPI(title="Spatial Graph Search API")


@app.get("/IP/search/")
@app.get("/search/")
async def search_get(
    lat: float = Query(..., description="Latitude of the query point."),
    long: float = Query(..., description="Longitude of the query point."),
    cat: str = Query(..., description="Category to match."),
    rad: float = Query(..., description="Radius in coordinate units."),
    link: Optional[str] = Query(
        None, description="Optional path to the link file."),
):
    return {"ids": search_core(lat, long, cat, rad, link)}


@app.post("/IP/search/")
@app.post("/search/")
async def search_post(payload: SearchRequest):
    return {"ids": search_core(payload.lat, payload.long, payload.cat, payload.rad, payload.link)}


@app.get("/")
async def root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
