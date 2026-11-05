#!/bin/zsh
# strata librarian — the daily job (DEC-2026-10-29-04·16, template DEC-2026-10-31-29).
# Pulls the vault, collects measurements and the project's product-flow indicators (read-only commands in its Tier P
# indicators.yaml) for each project, writes the indicators that moved the worse way as open signal notes (no
# destination — a person chooses it, DEC-2026-11-01-14·17), commits only the measurement and signal files, publishes
# the generated views. Every run starts and ends with a marked line so a reader (tools/doctor.py) can cut the log into runs, and a
# failed step makes the run fail: launchd's exit code used to carry only the last command's.
#
#   STRATA_PYTHON        python with PyYAML (launchd's login shell may not see asdf/pyenv) — required
#   STRATA_KIT           strata-kit checkout — required
#   STRATA_VAULT         vault checkout — required
#   LIBRARIAN_PROJECTS   space-separated "<vault project id>=<repo path>" pairs to measure
emulate -L zsh
: "${STRATA_PYTHON:?set STRATA_PYTHON}" "${STRATA_KIT:?set STRATA_KIT}" "${STRATA_VAULT:?set STRATA_VAULT}"
export STRATA_KIT STRATA_VAULT
cd "$STRATA_KIT" || exit 1
rev=$(git -C "$STRATA_KIT" rev-parse --short HEAD 2>/dev/null || echo '?')
echo "=== strata-librarian start $(date -u +%Y-%m-%dT%H:%M:%SZ) kit $rev ==="
failed=()
step() {   # step <name> <command...> — runs it, remembers the name if it fails
  local name=$1; shift
  "$@" || { echo "librarian step failed: $name (exit $?)"; failed+=("$name"); }
}
step vault-pull "$STRATA_PYTHON" kb vault-git pull
paths=()
for pair in ${=LIBRARIAN_PROJECTS}; do
  id=${pair%%=*}; repo=${pair#*=}
  step "metrics:$id" "$STRATA_PYTHON" tools/metrics.py --write collect "$repo"
  paths+=("projects/$id/measurements")
  step "indicators:$id" "$STRATA_PYTHON" kb indicators collect --project "$id" --repo "$repo" --write   # product-flow indicators, read-only (DEC-2026-11-01-17)
  step "signals:$id" "$STRATA_PYTHON" kb signals candidates --project "$id" --write
  [[ -d "$STRATA_VAULT/projects/$id/signals" ]] && paths+=("projects/$id/signals")   # a missing path fails the whole add
  "$STRATA_PYTHON" kb signals list --project "$id" | sed "s/^/librarian signals $id: /"
done
(( ${#paths} )) && step measurements-push "$STRATA_PYTHON" kb vault-git commit-push "librarian daily measurements and signal candidates $(date +%F)" "${paths[@]}"
step security-daily "$STRATA_PYTHON" kb security daily --commit
step views-publish "$STRATA_PYTHON" kb views-publish
echo "=== strata-librarian end $(date -u +%Y-%m-%dT%H:%M:%SZ) failed ${#failed}${failed:+: ${(j:, :)failed}} ==="
(( ${#failed} == 0 ))
