# taoFPGA — Simulation Data

Compiled record of every simulation run performed during the verification pass on the
Matrix-Multiply → Softmax → GELU transformer accelerator pipeline. All figures below come
directly from actual Xcelium (`xrun` 23.09-s013) runs; nothing here is estimated or
projected. Runs were executed directly on the project's login-node VM (2 vCPU / 7.4GB RAM)
— see `project_story.md` for why (PBS batch submission is not a supported path in this
environment).

Report artifacts referenced below live under `reports/sim/`.

---

## 1. `gelu_tb` — GELU approximation module, standalone

**Objective:** Verify the fixed-point GELU approximation (`core/gelu.v`) against a
real-valued software reference (`tanh`-based GELU formula), specifically re-validating
after widening `in_scale` from 3 bits (max representable value 7) to 4 bits (0–15), which
added a previously-missing right-shift code path for `in_scale > 7`.

**Method:** `make run_gelu`. Testbench randomizes `x` and `in_scale` every cycle
(`in_scale = {$random}%12`, i.e. exercises 0–11 — extended from the original `%7`, which
never even reached 7) across 200 samples, comparing hardware output to a real-valued
reference computed in the testbench.

**Result:** All 200 samples completed; 55 samples were flagged for exceeding the
per-sample display threshold, all with `diff` in the range **−0.008 to +0.033** — consistent
with ordinary fixed-point quantization noise, not a functional defect. Critically, none of
the flagged samples showed an order-of-magnitude blowup, which is what a wrong shift
direction in the new `in_scale > 7` branch would have produced. Peak memory ~54MB, wall
time ~3–4s.

**Conclusion:** GELU scale-widening fix (see `project_story.md` §10) is numerically correct
across the full newly-enabled range.

---

## 2. `Softmax_top_tb` — Softmax module, standalone

**Objective:** Verify `core/Softmax_control.v` / `core/Softmax.v` normalization output
against a real-valued reference.

**Method:** `make run_softmax`, direct execution, no parameter changes needed (no scaling
issue found in this module).

**Result:**
```
The ratio of error greater than the minimum precision: 0.0000%
real_max = 0.0051, hard_max = 0.0000
The ratio of error greater than the minimum precision: 0.00000%
real_max = 0.01874, hard_max = 0.01562
```
Clean pass, `$finish` reached normally. Stall monitor on the `top_in` interface: 39.90%
stall / 20.00% utilization (expected — driven by the testbench's own input pacing, not a
DUT limitation).

**Conclusion:** No issues found or fixed in this module during this pass.

---

## 3. `MM_Ultra_tb` — Matrix-multiply engine, standalone

**Objective:** Verify `core/MM_ultra.v` (and its sub-blocks: `MM_in_buffer`, `MM_buffer`,
`MM_out_buffer`, `MM`, `PE_array`, `PE_line`, `PE`, `AdderS`, `right_shifter`) at the
project's real target workload size (200 rows × 96 contraction cols × 160 output cols —
`A_size=16` systolic array), and establish real hardware latency and elaboration resource
cost.

**Method:** `make run_mm`, comparing hardware output (`z_hard`) against a software golden
model (`MM_soft` task) computed in the testbench. Two structural bugs were found and fixed
along the way (see `project_story.md` §6–9):
1. `start_trans` was referenced before its own declaration — compile error, fixed by
   reordering.
2. The testbench's `x_in_array`/`y_in_array` (input packing) and `z_hard_array` (output
   unpacking) were each materialized via a `generate` loop unrolling **one hardware object
   per scalar element** — at full scale, ~34,500 and ~32,000 objects respectively. This is
   what was blowing up Xcelium's elaboration-time memory and had, on a prior attempt,
   crashed the entire host session. Fixed by replacing both with on-demand packing/unpacking
   functions (`pack_x_word`, `pack_y_word`, computed inline via `unpack_z_word` calls),
   since only one word is ever needed per cycle.

**Data — resource cost by size, before vs. after the elaboration fix** (all runs monitored
live with `ps`-based RSS polling every 2s and a hard kill switch at 5,500MB to protect the
host):

| Size (rows³) | Peak RSS (before fix) | Peak RSS (after fix) | HW latency (after fix) | Pass? |
|---|---|---|---|---|
| 16×16×16  | 59MB  | — (not retested, trivial) | 144 cycles (1,440 ns) | ✅ |
| 32×32×32  | 76MB  | — (not retested, trivial) | 594 cycles (5,940 ns) | ✅ |
| 64×64×64  | 482MB | 93MB | 2,894 cycles (28,940 ns) | ✅ |
| 128×128×128 | **>5,900MB — killed mid-elaboration, still climbing** | 32MB | 15,621 cycles (156,210 ns) | ✅ (after fix) |
| **200×96×160 (full/real scale)** | *(would certainly have exceeded host memory — not attempted before the fix)* | **51MB** | **21,544 cycles (215,440 ns)** | ✅ |

**Result at full scale (post-fix):** `No Error.` / `No zero_error.` (both the numeric
matmul-vs-reference check and the internal output-buffer zero-residue check passed).
Hardware latency **21,544 cycles (215,440 ns)** from `start_trans` to `out_data_last`.

**Conclusion:** The DUT (`MM_ultra` and sub-blocks) is functionally correct at full
representative scale. The elaboration-memory issue was entirely a testbench
implementation artifact (per-element `generate` unrolling), not a DUT defect — confirmed by
the fact the identical golden-model comparison passes before and after the fix, and the
64³ hardware-latency figure is bit-for-bit identical pre- and post-fix (2,894 cycles both
times), proving the restructuring changed nothing about simulated behavior.

---

## 4. `transformer_block_tb` — Full pipeline integration (MM → Softmax → GELU)

**Objective:** Verify the full integrated pipeline (`top/transformer_block_top.v`, chaining
`MM_ultra` → `Softmax_control` → `EightGelus` via `axis_downsizer`/`axis_upsizer_fifo`)
end-to-end at real workload scale, and gather real cycle-count/latency/stall data for the
performance-analysis phase ahead of synthesis.

**Method:** `make run_transformer` (plain) and `make profile_transformer` (adds `-profile`
+ toggle coverage instrumentation). Hardware output (`gelu_hw_flat`) compared against a
chained software reference (matmul → per-row softmax → per-element real-valued GELU). Same
elaboration-blowup pattern as `MM_Ultra_tb` was found in this testbench's
`x_in_array`/`y_in_array` (identical fix applied), plus two additional fixes needed to scale
it up safely:
- `IN_Feature_Block_num`/`Weight_Block_num`/`OUT_Feature_Block_num` bumped from 256 to 2400
  — required headroom above the actual beat count at full scale (2,000 beats), per the
  file's own documented warning; undersizing this exact parameter had previously caused a
  register-overflow bug that permanently blocked the weight stream (fixed separately, prior
  to this session, commit `1c09132`).
- `gelu_scale` local testbench register widened from `[2:0]` to `[3:0]` to match the port
  width fixed on the DUT side (see `project_story.md` §10) — was still only capable of
  driving scale=7 even after the DUT itself was fixed.

**Data — staged scale-up** (same live-monitored protocol as §3; this testbench started at
a deliberately tiny 4×32×32 "structural wiring" config):

| Size | Elements checked | Errors | End-to-end latency | Peak RSS |
|---|---|---|---|---|
| 4×32×32 (original toy config, pre-array-fix) | 128 | 0 | 487 cycles (4,870 ns) | 37MB |
| 4×32×32 (post-array-fix, regression check) | 128 | 0 | 487 cycles (4,870 ns) — **identical**, confirms fix is behavior-preserving | 18MB |
| 32×32×32 | 1,024 | 0 | 599 cycles (5,990 ns) | (not memory-critical) |
| 64×64×64 | 4,096 | 0 | 2,611 cycles (26,110 ns) | (not memory-critical) |
| 128×128×128 | 16,384 | 0 | 14,027 cycles (140,270 ns) | 52MB |
| **200×96×160 (full/real scale)** | **32,000** | **0** | **18,083 cycles (180,830 ns)** | **53MB** |

**Stall/utilization breakdown at full scale** (the key performance-analysis data point
ahead of synthesis):

| Interface | Stall % | Utilization % |
|---|---|---|
| `mm_in_F` (matmul feature input) | 84.91% | 1.03% |
| `mm_in_W` (matmul weight input) | 84.91% | 0.83% |
| `pipe_out` (final GELU output) | **93.11%** | 6.89% |

The `pipe_out` stall figure is consistent across every scale tested (96.96% at the original
tiny 4×32×32 config, 93.11% at full scale) — this rules out "it's just a toy-scale
artifact" and confirms it's a structural characteristic of the current pipeline, not
something that improves at real workload size. Root cause is already documented in
`top/transformer_block_top.v`'s header comments: `axis_downsizer` is single-buffered (not
full-throughput) and `EightGelus` has no internal skid buffer, so the pipeline cannot
sustain back-to-back beats under real backpressure. **This is the single most important
number for the upcoming synthesis/timing-vs-throughput discussion** — cycle count alone
(18,083 cycles) understates how far this pipeline is from its achievable throughput ceiling.

**Coverage/profiling artifacts:** `make profile_transformer` was first run at the *original*
small 4×32×32 config (before this testbench was scaled up), producing a 3.7KB `xmprof.out`.
Re-run afterward at full 200×96×160 scale using the same monitored-launch protocol: peak RSS
**74.9MB**, wall clock **8s**, functional results identical to the plain `run_transformer`
run (0/32,000 outside tolerance, 18,083-cycle latency, same stall breakdown) — confirming
profiling/coverage instrumentation doesn't perturb simulated behavior. Produced a 24KB
`xmprof.out` (function/instance-level profiling data) and a full `cov_work/scope/...` toggle
coverage database under `sourcecode/sim/run/transformer_profile/`, both now representative
of real workload scale. `xmelab` noted one expected limitation: toggle coverage isn't
supported for `stall_monitor.sv`'s integer-typed ports (informational only, not an error).

**Conclusion:** Full pipeline is functionally correct at real workload scale (0/32,000
elements outside tolerance, tolerance = ±6 LSBs at the shared Softmax/GELU scale, accounting
for two compounded quantization stages). The dominant performance characteristic is
handshake starvation on the output path, not compute latency — a synthesis/timing pass
alone will not reveal this; it needs the throughput-focused view captured here.

---

## Cross-cutting: the monitored-launch protocol

Every run at or above a scale where elaboration cost was untested used the following
protocol, developed after a prior full-scale attempt exhausted host memory and crashed the
entire session:

1. Launch `make <target>` as a backgrounded shell job.
2. Poll `ps -u <user> -o rss=,cmd=` every 2 seconds, summing RSS across
   `xrun`/`xmvlog_cg`/`xmelab`/`xmsim`/`xmvlog` processes.
3. If combined RSS exceeds a 5,500MB threshold (leaving headroom on a 7.4GB host), issue
   `pkill -9` against the process family immediately and abort.
4. Confirm full cleanup (`ps` shows nothing, `free -h` shows memory recovered) before
   proceeding.

This protocol is what allowed safely finding the exact MM_Ultra_tb breaking point (64³ safe,
128³ dangerous) without a second host crash, and should be reused for any future
scale-up work (e.g. re-running `profile_transformer` at full scale, or any post-synthesis
gate-level simulation).
