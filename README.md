# Proximity Search API

This project implements a FastAPI endpoint that searches for the nearest valid locations in a road graph while respecting both the Euclidean radius filter and the graph-distance ordering requirement.

## Setup

```bash
cd "<workspace-folder>"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install fastapi uvicorn pytest httpx
```

Run the service:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or run directly:

```bash
python main.py
```

## API

### GET /search/

Required query parameters:
- lat: latitude of the query point
- long: longitude of the query point
- cat: category to match (case-insensitive)
- rad: Euclidean radius in coordinate units
- link: optional path to the road graph file; defaults to link.txt in the project folder

Example:

```bash
curl "http://localhost:8000/search/?lat=0.5&long=0.5&cat=bank&rad=0.4&link=link.txt"
```

Response format:

```json
{"ids": [4850, 4948, 4947, 4753, 5349, 4648, 5348, 4451, 5155, 5452]}
```

## Algorithm

- Parse locations.csv into a category map.
- Parse each line of link.txt as an undirected road between two grid points stored as `(longitude, latitude)` tuples.
- Build an adjacency list once and cache it by file path.
- Map the query coordinate and each candidate location to the nearest graph node.
- Filter candidates by category and the Euclidean radius requirement.
- Run BFS from the query node to compute shortest-path distances over the road graph.
- Sort candidates by graph distance, then by straight-line distance, then by ID.
- Return up to 10 IDs.

This is correct for an unweighted road graph because BFS yields the minimum number of road steps from the query node to each reachable node.

## Correctness notes

- Longitude and latitude are never swapped. The link file is read as `Longitude_A Latitude_A Longitude_B Latitude_B`, matching the given specification.
- If a candidate is unreachable from the query component, it is excluded because that node has no valid road path.
- Missing roads, empty files, invalid inputs, and non-finite values are handled gracefully.
- Relative link paths are resolved relative to the project directory, which matches the lab setup.

## Complexity

- Graph load: O(E)
- BFS per request: O(V + E)
- Candidate scan: O(C)
- Memory: O(V + E + C)

where V is the number of graph nodes, E is the number of road edges, and C is the number of locations in the selected category.

## Validation

Verified in this workspace with:

```bash
.venv/bin/python -m pytest -q
```

which returned `4 passed, 1 warning in 0.25s`.

The API smoke test also returned HTTP 200 for the default dataset query and produced a valid ID list.
