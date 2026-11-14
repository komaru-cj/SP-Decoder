# fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s

Outdoor capture plan: 10 Fig.13 source runs and 14 Fig.15 runs. Every
node sends business traffic for 20 s. Fig.13 uses 25% per-node duty, while Fig.15
uses 75% per-node duty. A capture requests 50 s and the RX runner adds a 5 s guard. Formal decoding uses only the traffic-relative
middle 10 s: `[traffic_start + 5 s, traffic_start + 15 s]`.

## Fig.13

Physical source captures use SF=8/10/12, BW=250 kHz (PHY profiles 4/5/6), and
N=3/6/9/12/15. The later N=18/21/24 points are not RF runs: for each PHY, merge
the aligned N=15 capture with N=3/6/9 respectively. This preserves real waveforms,
channels, CFOs and noise while correctly recording source packet identities.

## Fig.15

Node A is fixed at 80 m from the gateway. Node B positions are
20, 40, 60, 80, 100, 150, 200 m. The provided distance list has
7 positions, so this plan uses those seven positions. At every position it
first captures `ab_simultaneous`, then `b_only`; both runs share the same position index.
`ab_simultaneous` activates Node01 and Node02 (`active_nodes=[1,2]`), whereas `b_only`
activates only Node02 (`active_nodes=[2]`). Thus the seven positions produce 14 runs.
There is a 30 s `POSITION_BREAK` only before the next position, not between
the two modes at one position.

## Capture

On the Ubuntu RX machine, start the matching script first. Start the Windows control
script when RX prints its start prompt, within 10 s.

```bash
bash run_fig13_receiver.sh
bash run_fig15_receiver.sh
```

```powershell
& .\run_fig13_controller.ps1 -PythonExecutable "D:\mysoft2\radioconda\python.exe" -ControlTxGain 60
& .\run_fig15_controller.ps1 -PythonExecutable "D:\mysoft2\radioconda\python.exe" -ControlTxGain 60
```

The shared slot is 75 s. Both runners record failures and retain the fixed schedule;
rerun only listed failed run IDs with a new output directory/manifest label.

## Strict Decode And Merge

After copying controller manifests beside their matching IQ directories, use this
order for every formal PRR source: strict-window alignment, v2 fine-sync database
construction and audit, then formal decode. D is the certified anonymous physical
candidate set; all Fig.13--15 PRR values are `CRC-valid decoded candidates / D`.
The detector never receives packet schedules, node IDs, or sequences. Replace
`RUNS_ROOT` when the RX data are
stored outside the default path.

```bash
RUNS_ROOT="$PWD/real_collision_experiment/runs_outdoor"
REPORTS="$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15/reports"
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s 10 \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 --alignment-only

python3 real_collision_experiment/analysis/build_fine_sync_database.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15"

for database in "$PWD"/real_collision_experiment/analysis/outdoor_fig13_fig15/fine_sync/run_*.json; do
  python3 real_collision_experiment/analysis/audit_fine_sync_database.py "$database" || exit 1
done

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s 10 \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10

python3 real_collision_experiment/analysis/merge_outdoor_scale_runs.py \
  --campaign "$PWD/real_collision_experiment/paper_experiments/generated/fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s/campaign.json" \
  --runs "$RUNS_ROOT" --reports "$REPORTS" \
  --traffic-start-map "$REPORTS/merged_traffic_starts.json"

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s 10 \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \
  --traffic-start-map "$REPORTS/merged_traffic_starts.json" \
  --alignment-only --overwrite

python3 real_collision_experiment/analysis/build_fine_sync_database.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15" \
  --run-id e0412600 --run-id e0415600 --run-id e0418600 \
  --run-id e0512600 --run-id e0515600 --run-id e0518600 \
  --run-id e0612600 --run-id e0615600 --run-id e0618600

for database in "$PWD"/real_collision_experiment/analysis/outdoor_fig13_fig15/fine_sync/run_e*.json; do
  python3 real_collision_experiment/analysis/audit_fine_sync_database.py "$database" || exit 1
done

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s 10 \
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \
  --traffic-start-map "$REPORTS/merged_traffic_starts.json" \
  --overwrite \
  --run-id e0412600 --run-id e0415600 --run-id e0418600 \
  --run-id e0512600 --run-id e0515600 --run-id e0518600 \
  --run-id e0612600 --run-id e0615600 --run-id e0618600
```

Decode Fig.15 separately with the same three phases: run the driver with
`--include-figure fig15 --alignment-only`, build/audit its v2 databases, then rerun
without `--alignment-only`. Since CRC-failed anonymous candidates have no valid node
identity, Fig.15 reports `ab_simultaneous` and `b_only` traffic-mode PRR rather than
inventing per-node D subsets.

## Fig.14 AWGN

Fig.14 uses only the physical Fig.13 SF8/BW250 N=3 source report. The driver reads
its certified v2 fine-sync database, adds covariance-matched noise, and accepts
points by measured median preamble-SNR bin: `<-30`, `[-30,-10)`, `[-10,10)`, or
`>=10` dB. It is a decoder PRR measurement on fixed shared D targets, not a
low-SNR detector-recall result. Existing v2 AWGN caches are rejected; pass
`--overwrite` when rebuilding.

```bash
python3 real_collision_experiment/node01_sp_receiver/run_fig14_snr_sweep.py \
  --reports "$REPORTS" \
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15/fig14_awgn" \
  --overwrite
```
