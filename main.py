from __future__ import annotations

import csv
import math
from collections import defaultdict, deque
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Set, Tuple

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


def load_locations(path: Path) -> Dict[str, Tuple[LocationEntry, ...]]:
    categories: DefaultDict[str, List[LocationEntry]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return {}
        for row in reader:
            if not row or len(row) < 4:
                continue
            try:
                _id = int(row[0].strip())
                lat = float(row[1].strip())
                lon = float(row[2].strip())
                cat = normalize_category(row[3].strip())
            except ValueError:
                continue
            categories[cat].append((_id, lat, lon))
    return {key: tuple(value) for key, value in categories.items()}


def load_graph(path: Path) -> Dict[Coord, Set[Coord]]:
    graph: DefaultDict[Coord, Set[Coord]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 4:
                continue
            try:
                lon_a, lat_a, lon_b, lat_b = map(float, parts)
            except ValueError:
                continue
            a = (float(lon_a), float(lat_a))
            b = (float(lon_b), float(lat_b))
            graph[a].add(b)
            graph[b].add(a)
    return {key: set(value) for key, value in graph.items()}


def _resolve_path(raw: Optional[str], default: Path) -> Path:
    if raw is None or not raw.strip():
        return default
    path = Path(raw.strip()).expanduser()
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return path


def _nearest_graph_node(start: Coord, graph: Dict[Coord, Set[Coord]]) -> Coord:
    if not graph:
        return start
    if start in graph:
        return start
    best_node = None
    best_dist_sq = float("inf")
    for node in graph:
        dist_sq = (start[0] - node[0]) ** 2 + (start[1] - node[1]) ** 2
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_node = node
    return best_node if best_node is not None else start


def bfs_distances(start: Coord, graph: Dict[Coord, Set[Coord]]) -> Dict[Coord, int]:
    if not graph:
        return {}
    start_node = _nearest_graph_node(start, graph)
    queue: deque[Coord] = deque([start_node])
    distances: Dict[Coord, int] = {start_node: 0}
    while queue:
        current = queue.popleft()
        dist = distances[current]
        for neighbor in graph.get(current, ()):  # type: ignore[arg-type]
            if neighbor not in distances:
                distances[neighbor] = dist + 1
                queue.append(neighbor)
    return distances


LOCATIONS_CACHE: Dict[str, Tuple[LocationEntry, ...]] = {}
GRAPH_CACHE: Dict[Path, Dict[Coord, Set[Coord]]] = {}


def get_locations(category: str) -> Tuple[LocationEntry, ...]:
    norm = normalize_category(category)
    if norm not in LOCATIONS_CACHE:
        LOCATIONS_CACHE.update(load_locations(DEFAULT_LOCATIONS_PATH))
    return LOCATIONS_CACHE.get(norm, ())


def get_graph(path: Path) -> Dict[Coord, Set[Coord]]:
    if path not in GRAPH_CACHE:
        GRAPH_CACHE[path] = load_graph(path)
    return GRAPH_CACHE[path]


def search_core(lat: float, long: float, cat: str, rad: float, link: Optional[str]) -> List[int]:
    if not math.isfinite(lat) or not math.isfinite(long) or not math.isfinite(rad):
        raise HTTPException(status_code=400, detail="lat, long, and rad must be finite numbers.")
    if rad < 0.0:
        raise HTTPException(status_code=400, detail="rad must be non-negative.")
    if not cat or not cat.strip():
        raise HTTPException(status_code=400, detail="cat must be non-empty.")

    path = _resolve_path(link, DEFAULT_LINK_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"link file not found: {path}")

    graph = get_graph(path)
    if not graph:
        return []

    query = (float(long), float(lat))
    distances = bfs_distances(query, graph)
    if not distances:
        return []

    category_points = get_locations(cat)
    candidate_results: List[Tuple[int, int, float, float]] = []
    for _id, point_lat, point_lon in category_points:
        point_coord = (float(point_lon), float(point_lat))
        if point_coord not in distances:
            continue
        delta_lat = point_lat - lat
        delta_lon = point_lon - long
        euclid = math.hypot(delta_lat, delta_lon)
        if euclid > rad:
            continue
        candidate_results.append((distances[point_coord], _id, point_lat, point_lon))

    candidate_results.sort(key=lambda item: (item[0], math.hypot(item[2] - lat, item[3] - long), item[1]))
    return [entry_id for _, entry_id, _, _ in candidate_results[:10]]


app = FastAPI(title="Spatial Graph Search API")


@app.get("/IP/search/")
@app.get("/search/")
async def search_get(
    lat: float = Query(..., description="Latitude of the query point."),
    long: float = Query(..., description="Longitude of the query point."),
    cat: str = Query(..., description="Category to match."),
    rad: float = Query(..., description="Radius in coordinate units."),
    link: Optional[str] = Query(None, description="Optional path to the link file."),
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
