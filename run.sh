#!/usr/bin/env bash
SCRIPT_DIR=$(realpath $(dirname $0))
BENCHMARK_SCRIPT=$SCRIPT_DIR/benchmark.py
LATENCY_SWEEP=(0 1 2 3 4 5 6 7 8 9 10 15 20 25 30)
LOSS_SWEEP=(0 1 2 3 4 5 6 7 8 9 10 15 20 25 30)
LINK_SWEEP=(2 3 4 5 6 7 8 9 10 15 20 25 30)
for link in "${LINK_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --link-count $link "$@" || exit 1
done
for loss in "${LOSS_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --loss $loss "$@" || exit 1
done
for latency in "${LATENCY_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --latency $latency "$@" || exit 1
done
