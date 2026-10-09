# Lab 7: Proximity Search API Report

## Summary

The final implementation loads the road graph and locations once, validates request inputs, and ranks category matches by shortest-path distance on the road network rather than by direct Euclidean distance.

## Implementation approach

1. Parse the CSV file to keep locations grouped by category.
2. Parse the link file as an undirected edge list of the form `Longitude_A Latitude_A Longitude_B Latitude_B`.
3. Build an adjacency list with a cached dictionary keyed by the path to the data file.
4. Snap both the query point and each candidate point to the nearest road-graph node using Euclidean distance.
5. Check whether the candidate satisfies the category filter and the Euclidean radius requirement.
6. Run BFS from the nearest query node. Because each road segment has equal cost, BFS gives the shortest-path distance in the road graph.
7. Sort the eligible candidates by road distance, then by straight-line distance, then by ID, and return the first 10 IDs.

## Correctness rationale

- The lab requirement states that a candidate must match the target category and lie within Euclidean radius `rad` of the query coordinate before ranking.
- The ranking requirement explicitly says to use shortest-path distance over the undirected road graph, not direct coordinate distance.
- In the unweighted road graph, BFS is the correct algorithm because every edge has equal cost.
- The implementation never swaps latitude and longitude; the graph file is interpreted exactly as `longitude latitude` pairs, which is necessary for correct coordinate mapping.
- Missing or invalid edges are ignored, disconnected components are handled safely, and non-finite or invalid input values raise a 400 error.

## Complexity

Let V be the count of graph vertices, E the number of road edges, and C the number of candidate locations in the selected category.

- Loading and adjacency construction: O(E)
- BFS per request: O(V + E)
- Candidate filtering and sorting: O(C log C)
- Total memory usage: O(V + E + C)

## Validation

### Automated test results

Command run:

```bash
.venv/bin/python -m pytest -q
```

Observed output:

```text
4 passed, 1 warning in 0.25s
```

The warning is a Starlette/HTTPX deprecation warning and does not indicate a functional failure.

### API smoke test

Command run:

```bash
.venv/bin/python -c "from fastapi.testclient import TestClient; from main import app; client = TestClient(app); r = client.get('/search/', params={'lat': 0.5, 'long': 0.5, 'cat': 'bank', 'rad': 0.4, 'link': 'link.txt'}); print(r.status_code); print(r.json())"
```

Observed output:

```text
200
{'ids': [4850, 4948, 4947, 4753, 5349, 4648, 5348, 4451, 5155, 5452]}
```

This confirms the route is responding successfully with the expected JSON shape.

## Notes

The only practical ambiguity in the assignment is how a relative `link` path should be resolved. This implementation resolves relative paths against the project directory so that the default lab file (`link.txt`) works reliably and custom paths remain usable.
