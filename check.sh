#!/usr/bin/env bash
# Everything the pipeline runs, in the order it runs it. Each stage is gated on
# its own exit status so one failure does not hide the next.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
PY="${PYTHON:-python}"
failed=()

run() {
  local name="$1"; shift
  echo "--- $name"
  if ! "$@"; then
    failed+=("$name")
  fi
}

run ruff-check "$PY" -m ruff check .
run ruff-format "$PY" -m ruff format --check .
run mypy "$PY" -m mypy

for tool in $(ls src/tariffpeg/tools/check_*.py | xargs -n1 basename | sed 's/\.py$//'); do
  run "$tool" "$PY" -m "tariffpeg.tools.$tool"
done

for tool in $(ls src/tariffpeg/tools/build_*.py src/tariffpeg/tools/schema_dump.py \
  | xargs -n1 basename | sed 's/\.py$//'); do
  run "$tool" "$PY" -m "tariffpeg.tools.$tool" --check
done

run pytest "$PY" -m pytest -q
run smoke "$PY" -m tariffpeg.tools.smoke --quiet
run release-check "$PY" -m tariffpeg.tools.release_check

if [ "${#failed[@]}" -gt 0 ]; then
  printf '%d failed: %s\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
echo "everything passed"
