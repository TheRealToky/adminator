# Convenience wrapper for the isolated ACCRUAL sandbox stack (Windows / pwsh).
#
#   ./scripts/accrual.ps1 up        # build + start in background
#   ./scripts/accrual.ps1 down      # stop (keeps the database volume)
#   ./scripts/accrual.ps1 logs      # follow backend logs
#   ./scripts/accrual.ps1 test      # run the ledger test suite
#   ./scripts/accrual.ps1 psql      # open a psql shell on the sandbox DB
#   ./scripts/accrual.ps1 nuke      # stop + delete the sandbox volume (fresh start)
#
# Never touches the main (adminator) or scratch (adminator-scratch) stacks.
param([Parameter(Position = 0)][string]$cmd = "up")

$ErrorActionPreference = "Stop"
$compose = @("-f", "docker-compose.yml", "-f", "docker-compose.accrual.yml")

switch ($cmd) {
    "up"    { docker compose @compose up -d --build }
    "down"  { docker compose @compose down }
    "logs"  { docker compose @compose logs -f backend }
    "test"  { docker exec adminator-accrual-backend python -m pytest apps/ledger -v }
    "psql"  { docker exec -it adminator-accrual-postgres psql -U adminator -d adminator }
    "nuke"  { docker compose @compose down -v }
    default { Write-Host "Unknown command '$cmd'. Use: up | down | logs | test | psql | nuke" }
}
