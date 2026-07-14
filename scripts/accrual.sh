#!/usr/bin/env bash
# Convenience wrapper for the isolated ACCRUAL sandbox stack.
#
#   ./scripts/accrual.sh up        # build + start in background
#   ./scripts/accrual.sh down      # stop (keeps the database volume)
#   ./scripts/accrual.sh logs      # follow backend logs
#   ./scripts/accrual.sh test      # run the ledger test suite
#   ./scripts/accrual.sh psql      # open a psql shell on the sandbox DB
#   ./scripts/accrual.sh nuke      # stop + delete the sandbox volume (fresh start)
#
# Never touches the main (adminator) or scratch (adminator-scratch) stacks.
set -euo pipefail

COMPOSE=(-f docker-compose.yml -f docker-compose.accrual.yml)
cmd="${1:-up}"

case "$cmd" in
  up)   docker compose "${COMPOSE[@]}" up -d --build ;;
  down) docker compose "${COMPOSE[@]}" down ;;
  logs) docker compose "${COMPOSE[@]}" logs -f backend ;;
  test) docker exec adminator-accrual-backend python -m pytest apps/ledger -v ;;
  psql) docker exec -it adminator-accrual-postgres psql -U adminator -d adminator ;;
  nuke) docker compose "${COMPOSE[@]}" down -v ;;
  *)    echo "Unknown command '$cmd'. Use: up | down | logs | test | psql | nuke" ;;
esac
