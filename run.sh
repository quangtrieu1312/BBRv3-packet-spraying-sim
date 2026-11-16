#!/usr/bin/env bash
SCRIPT_DIR=$(realpath $(dirname $0))
BENCHMARK_SCRIPT=$SCRIPT_DIR/benchmark.py
LATENCY_SWEEP=(0 1 2 3 4 5 6 8 10 15 20)
LOSS_SWEEP=(0 0.25 0.5 0.75 1 1.5 2 2.5 3 4 5 6)
LINK_SWEEP=(1 2 3 4 5 6 8 10 15 20)
CUBIC_PAIR_SWEEP=(0 1 2 3 4 5)

output=$SCRIPT_DIR/output.txt
err=$SCRIPT_DIR/err.txt

rm -rf $output $err

echo "===== Start link sweep =====" >>$output
for link in "${LINK_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --link-count $link "$@" >>$output 2>>$err || exit 1
done
echo "===== Start loss sweep =====" >>$output
for loss in "${LOSS_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --loss $loss "$@" >>$output 2>>$err || exit 1
done
echo "===== Start latency skew sweep =====" >>$output
for latency in "${LATENCY_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --latency $latency "$@" >>$output 2>>$err || exit 1
done
echo "===== Start fairness skew sweep (single path) =====" >>$output
for pair in "${CUBIC_PAIR_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --fairness --cubic-pair $pair --link-count 1 "$@" >>$output 2>>$err || exit 1
done
echo "===== Start fairness skew sweep (spray) =====" >>$output
for pair in "${CUBIC_PAIR_SWEEP[@]}"; do
  sudo mn -c >/dev/null 2>&1
  sudo $BENCHMARK_SCRIPT --fairness --cubic-pair $pair "$@" >>$output 2>>$err || exit 1
done
