#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.." || exit 1
if [[ "$PWD" == *:* ]]; then
  ln -sfn "$PWD" /tmp/proximity_clean
  cd /tmp/proximity_clean || exit 1
fi
L=report/logs; rm -rf "$L"; mkdir -p "$L"
URL="http://localhost:${HOST_PORT:-8000}"
Q='/search/?lat=0.5&long=0.5&cat=bank&rad=0.4&link=link.txt'
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
runs(){ { echo "\$ $2"; bash -c "set -o pipefail; $2" 2>&1; echo "[exit=$?]"; } > "$L/$1.txt"; }
runs 01_env 'grep PRETTY_NAME /etc/os-release; uname -r; docker --version; docker compose version'
runs 02_config 'docker compose config -q && echo COMPOSE_CONFIG_VALID'
runs 03_clean 'docker compose down -v --rmi local --remove-orphans'
runs 04_up 'docker compose up -d --build 2>&1 | tail -n 25'
sleep 3
runs 05_ps 'docker compose ps; docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "REPOSITORY|proximity"'
runs 06_search "curl -s -w '\nHTTP %{http_code} in %{time_total}s\n' '$URL$Q'"
C=$(curl -s "$URL$Q" | python3 -c 'import sys,json;print(json.load(sys.stdin)["ids"])' 2>&1 | tail -n1)
P=$($PY -c "from fastapi.testclient import TestClient; import main; print(TestClient(main.app).get('/search/',params=dict(lat=0.5,long=0.5,cat='bank',rad=0.4,link='link.txt')).json()['ids'])" 2>&1 | tail -n1)
{ echo '$ compare container response vs local main.app'; echo "container: $C"; echo "local    : $P"; [ "$C" = "$P" ] && echo PARITY_OK || echo PARITY_MISMATCH; echo "[exit=0]"; } > "$L/07_parity.txt"
runs 08_docs "curl -s -o /dev/null -w 'GET /docs -> HTTP %{http_code}\n' $URL/docs"
runs 09_isolation 'echo "api published host ports: [$(docker port proximity-api)]"; docker compose port gateway 80'
runs 10_network 'docker network ls --filter name=backend; docker network inspect proximity-search_backend --format "{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}"'
runs 11_nonroot 'docker exec proximity-api id; docker exec proximity-api ls -l /app'
runs 12_volume_ro "docker exec proximity-api sh -c 'touch /app/link.txt && echo WRITABLE || echo READ_ONLY_MOUNT_OK'"
runs 13_logs 'docker compose logs --no-color --tail=6'
runs 14_down 'docker compose down; docker compose ps -a'
echo SCRIPT_DONE
