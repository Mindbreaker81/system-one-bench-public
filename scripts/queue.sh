#!/bin/bash
# Run several jevbench jobs one after another; one log per run under results/logs/.
# Usage: [PHASES=a,b] scripts/queue.sh <venv> <adapter> "<run>|k=v k=v" ...
# Launch it detached, passing the HF token on stdin:
#   printf '%s\n' "$HF_API_KEY" | ssh host 'read -r T; cd ~/proyectos/jev-tests && \
#     tmux new -d -s q "HF_TOKEN=$T scripts/queue.sh anyjev anyjev \"anyjev_qwen3_8b_l0|model=Qwen/Qwen3-8B\""'
cd "$(dirname "$0")/.."
mkdir -p results/logs
venv=$1 adapter=$2; shift 2
for job in "$@"; do
  run=${job%%|*}; opts=()
  for kv in ${job#*|}; do opts+=(--opt "$kv"); done
  echo "=== $run start $(date +%T)" | tee -a results/logs/queue.txt
  ".venv-$venv/bin/python" -m jevbench.run "$adapter" --run "$run" --retry-errors ${PHASES:+--phases "$PHASES"} "${opts[@]}" >> "results/logs/$run.log" 2>&1
  echo "=== $run exit=$? $(date +%T)" | tee -a results/logs/queue.txt
done
echo QUEUE_DONE | tee -a results/logs/queue.txt
