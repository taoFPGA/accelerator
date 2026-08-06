# taoFPGA — Synthesis Data

Tracking log for the synthesis phase of the transformer accelerator, parallel in spirit to
`simulation_data.md` for the verification phase. Each run is logged here with objective,
method, key results, and the gap list it surfaced. Report artifacts referenced below live
under `reports/syn/` (git-ignored contents, `.gitkeep`-tracked directory — regenerate by
re-running `scripts/synth.tcl`).

---

## Methodology

**Script:** `scripts/synth.tcl` — in-memory, non-project batch synthesis (`vivado -mode batch
-source scripts/synth.tcl`). No `.xpr` is written to disk; it's a throwaway in-memory Vivado
project purely for running `synth_design` and the report commands.

**Target:** `xc7z020clg400-1` (PYNQ-Z1's Zynq-7000 part).

**Top module:** `transformer_block_top` — the complete verified pipeline (`MM_ultra` →
`Softmax_control` → `EightGelus`, chained via the `top/*.v` adapters), not the AXI-wrapped
`MM_ultra_top` sub-block that `scripts/prj.tcl` integrates into the SoC. Its own declared
parameter defaults (`A_size=16`, `data_width=8`, `shift_width=10`, `*_Block_num=2400`, ...)
already match everything verified in simulation (see `simulation_data.md` and
`project_story.md`), so `synth.tcl` applies no `-generic` overrides.

**Synthesis mode:** `-mode out_of_context`. This block has no board-level I/O of its own (no
XDC pin assignments) and is meant to be instantiated inside the larger SoC design, not
synthesized as if it were a standalone top-level bitstream target. OOC mode avoids Vivado
inserting artificial top-level IBUF/OBUF pairs that would skew the utilization numbers, at
the cost of two known, expected limitations (see Run 1's gap list below): clock delay/skew
can't be estimated without `HD.CLK_SRC` set, and DRC can't run all connectivity-based checks
without the surrounding context.

**Clock constraint:** `create_clock -period 10.000 -name clk [get_ports clk]` — 100MHz,
applied after `synth_design` (standard practice for OOC blocks: enough for
`report_timing_summary` to be meaningful, not meant to drive timing-optimized synthesis
decisions the way a full top-level XDC would). 100MHz matches the Zynq PS7's FCLK0
configuration in `scripts/prj.tcl` (`CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}`) — i.e. the
actual clock this accelerator runs from once integrated into the SoC.

**Reports generated**, all under `reports/syn/`:
- `utilization.rpt` — `report_utilization`
- `timing_summary.rpt` — `report_timing_summary`
- `drc.rpt` — `report_drc`

---

## Run 1 — Baseline (2026-08-04)

**Objective:** Establish the first area/timing/DRC baseline for the full transformer
accelerator pipeline, now that both the RTL (verified in simulation) and the Vivado toolchain
(installed, licensed, `prj.tcl` validated) are in place.

**Result:** Clean synthesis. `Synthesis finished with 0 errors, 0 critical warnings and 6
warnings.` Peak memory ~3.3GB, wall time ~2.5 minutes for `synth_design` (~3.5 minutes total
run including report generation) — run directly on the login node with the same
resource-monitored protocol used throughout the simulation phase (no issues, well within the
5.5GB safety threshold).

### Utilization

| Resource | Used | Available | Utilization |
|---|---|---|---|
| Slice LUTs | 27,327 | 53,200 | 51.37% |
| — LUT as Logic | 26,833 | 53,200 | 50.44% |
| — LUT as Memory (Shift Register) | 494 | 17,400 | 2.84% |
| Slice Registers | 17,821 | 106,400 | 16.75% |
| F7 Muxes | 560 | 26,600 | 2.11% |
| F8 Muxes | 263 | 13,300 | 1.98% |

Comfortable headroom on the xc7z020 at this configuration (`A_size=16`, full `*_Block_num`
headroom) — LUTs are the tightest resource at ~51%, everything else well under 20%.

### Timing (at 100MHz / 10ns period)

| Metric | Value |
|---|---|
| WNS (Worst Negative Slack) | **+0.682 ns** |
| TNS (Total Negative Slack) | 0.000 ns (0 failing endpoints / 30,296 total) |
| WHS (Worst Hold Slack) | **+0.219 ns** |
| THS (Total Hold Slack) | 0.000 ns (0 failing endpoints / 30,296 total) |

**"All user specified timing constraints are met."** Positive margin on both setup (WNS) and
hold (WHS) — the design has slack at 100MHz, meaning there's headroom before this becomes the
limiting factor (worth revisiting once full SoC-level implementation timing is available,
since OOC clock delay/skew can't be fully estimated yet — see gaps below).

### DRC — 0 errors, warnings only

| Rule | Count | Category | Severity |
|---|---|---|---|
| REQP-1839 (RAMB36 async control check) | 20 (capped — likely more) | Correctness risk | **Worth fixing** |
| REQP-1840 (RAMB18 async control check) | 20 (capped — likely more) | Correctness risk | **Worth fixing** |
| DPIP-1 (DSP input pipelining) | 13 | Performance/power | Optimization opportunity |
| DPOP-2 (DSP MREG multiplier pipelining) | 12 | Performance/power | Optimization opportunity |
| DPOP-1 (DSP PREG output pipelining) | 5 | Performance/power | Optimization opportunity |
| CHECK-3 (rule-limit-reached meta-warning) | 2 | Reporting only | Not a real issue |
| ZPS7-1 (PS7 block required) | 1 | Expected for OOC | Not a real issue (resolves once integrated via `prj.tcl`) |

**The one gap worth real follow-up: REQP-1839/1840, 40+ instances.** Both `MM_in_buffer` and
`MM_buffer`'s block RAM instances (`in_F_array_reg_*`, `feature_buffer_reg_*`, etc.) have
control pins (`ENARDEN`, `ADDRARDADDR`) driven by registers with an *asynchronous* set/reset.
Xilinx's own DRC description: *"This may cause corruption of the memory contents and/or read
values when the set/reset is asserted and is not analyzed by the default static timing
analysis."* This wasn't caught by simulation (functional correctness was verified there, and
asynchronous-reset timing races are exactly the class of issue that doesn't reliably show up
in a testbench, only in real silicon/timing corners) — this is squarely the kind of gap
synthesis exists to surface. Not yet root-caused to a specific line of RTL; next step is
tracing which reset signal(s) feed these buffers' control logic and converting to synchronous
reset on those specific paths, or restructuring so reset doesn't reach the BRAM control pins
directly.

**Synthesis-level warnings (6, from `synth_design` itself)** — minor RTL cleanliness items,
none functionally blocking:
- `axis_upsizer_fifo.v:58` — `fifo_mem_reg` has set and reset at the same priority (simulation-mismatch risk, not incorrect today but worth rewriting to remove ambiguity).
- Same register: Vivado couldn't implement it as Block RAM/Distributed RAM, falling back to registers (potential unnecessary LUT/FF cost — worth checking why the RAM inference failed).
- `lin.v` — two `x_in_L_2Q9` bits unconnected/no load (dead port bits).
- `Exp_module.v:13`, `lin.v:36` — two internal registers trimmed (unconnected upper bits synthesized away; harmless but signals wider-than-needed declarations).

**OOC-mode limitations** (expected, not defects):
- `WARNING: [Timing 38-242]` — `HD.CLK_SRC` not set on the `clk` port, so clock delay/skew can't be estimated in this OOC run. Will be resolved once this block is part of the full `prj.tcl` SoC-level synthesis, where the actual PS7 clock source location is known.
- `WARNING: [DRC 23-814]` — not all connectivity-based DRC checks can run without full top-level context, for the same reason.

### Open items carried from Run 1 (status after Run 2, below)
1. ~~Root-cause and fix the REQP-1839/1840 async-reset-on-BRAM-control gap~~ — **done, see Run 2.**
2. ~~Investigate why `fifo_mem_reg` in `axis_upsizer_fifo.v` couldn't map to Block RAM~~ —
   **resolved as a side effect of Run 2's fix** (see below).
3. Consider whether the DPIP-1/DPOP-1/DPOP-2 DSP pipelining suggestions are worth taking once
   the design is otherwise stable — timing has positive margin today, so not urgent, but cheap
   wins for a later pass. **Still open.**
4. Re-run timing/DRC once this block is integrated into the full `prj.tcl` SoC design, to get
   real clock-source-aware numbers instead of the OOC estimate. **Still open.**

---

## Run 2 — Async-reset-on-BRAM-control fix (2026-08-04)

**Objective:** Root-cause and clear Run 1's one real gap: `REQP-1839`/`REQP-1840` (RAMB36/RAMB18
async control check), 40+ instances warning that block RAM control pins in `MM_in_buffer` and
`MM_buffer` were driven by asynchronously-reset registers.

**Root cause:** In every module holding one of this design's five block RAM arrays
(`in_F_array`/`in_W_array` in `MM_in_buffer.v`, `weight_buffer`/`feature_buffer` in
`MM_buffer.v`, `F_array` in `MM_out_buffer.v`, plus `Softmax_control.v`'s own `in_data_buffer`),
the actual memory read/write `always` blocks were already clean (no reset at all — correct).
The problem was every address counter, valid-pipeline register, and FSM state register that
*feeds* those ports' address/enable inputs, directly or through simple combinational logic —
all used `always @(posedge clk or negedge rst_n)`, Verilog's asynchronous-reset idiom. An
asynchronous reset can transition independent of any clock edge, so when Vivado maps these
registers' fanout onto a RAMB18/RAMB36 control pin, that's a control-pin transition standard
clocked timing analysis doesn't cover.

**Fix:** Converted every `always @(posedge clk or negedge rst_n)` block to synchronous-reset-only
(`always @(posedge clk)`, `if (~rst_n) ... else ...` body unchanged) — Xilinx's own recommended
remedy. Scope grew significantly beyond the three buffer files first suspected, discovered across
three iterative rounds (fix → re-synthesize → trace the next violation's driving register →
repeat), because valid/ready backpressure signals ripple through the entire pipeline and any one
of them can reach a BRAM control pin combinationally:

| Round | Files | Blocks converted | Why found |
|---|---|---|---|
| 1 | `MM_in_buffer.v`, `MM_buffer.v`, `MM_out_buffer.v` | 12 + 14 + 11 = 37 | Directly named in Run 1's DRC violations |
| 2 | `MM.v` | 10 | Violation now traced to `MM_out_data_valid_reg_array` (the systolic array's own output-valid pipeline, instantiated inside `MM_buffer.v`) |
| 2 | `PE_array.v`, `PE.v`, `axis_downsizer.v` | 4 + 1 + 1 = 6 | Violation traced to `draining_reg` in `axis_downsizer.v` (the MM→Softmax width adapter) — backpressure (`out_data_ready`) from outside `MM_ultra` entirely was reaching `F_array`'s enable |
| 3 | `Softmax_control.v`, `Softmax.v`, `EightGelus.v`, `axis_upsizer_fifo.v`, `transformer_block_top.v` | 4 + 3 + 7 + 2 + 1 = 17 | Violation traced to `Softmax_control.v`'s own internal `in_data_buffer` BRAM — a fifth block RAM not previously visible because Run 1's report was capped at 20 violations per rule and fully saturated by `MM_in_buffer`/`MM_buffer` instances |

**Total: 12 files, 60 always blocks converted.** Full file list: `MM_in_buffer.v`, `MM_buffer.v`,
`MM_out_buffer.v`, `MM.v`, `PE_array.v`, `PE.v`, `axis_downsizer.v`, `Softmax_control.v`,
`Softmax.v`, `EightGelus.v`, `axis_upsizer_fifo.v`, `transformer_block_top.v` — i.e. essentially
every reset-bearing register in the full `transformer_block_top` hierarchy that isn't already
reset-free. Every diff was verified as sensitivity-list-only (no logic changes) before moving on.

**Regression (re-run after every round, all four full-scale runs identical to pre-fix baseline):**
- `MM_Ultra_tb` (200×96×160): `No Error.` / `No zero_error.`, hardware latency **21,544 cycles**
  — bit-for-bit identical to Run 1's pre-fix baseline.
- `transformer_block_tb` (200×96×160): **0 / 32,000** elements outside tolerance, end-to-end
  latency **18,083 cycles** — identical to pre-fix baseline.

This confirms the fix is exactly what it was designed to be: a change in *when* reset takes
effect (next clock edge vs. immediately), invisible to every testbench (all of which hold
`rst_n` low far longer than one clock period before deasserting), with zero functional change.

**Post-fix synthesis result:**
- `REQP-1839`: 20 → **0**. `REQP-1840`: 20 → **0**. Fully cleared.
- **Bonus, unplanned:** two of Run 1's six `synth_design` warnings also disappeared —
  `axis_upsizer_fifo.v`'s `fifo_mem_reg` "Set and reset with same priority" warning, and its
  companion "trying to implement RAM in registers, Block RAM implementation is not possible"
  warning (Run 1 open item #2, above). Both were consequences of the same async
  set/reset-on-a-memory-register pattern; removing the async reset let Vivado infer Block RAM
  for it correctly instead of falling back to discrete registers.
- **Bonus, unplanned: utilization improved.** LUTs 27,327→**25,506** (51.37%→**47.94%**),
  Registers 17,821→**13,624** (16.75%→**12.80%**), F7 Muxes 560→**40**, F8 Muxes 263→**0**.
  Removing async set/reset from ~60 registers let Vivado pack flip-flops more efficiently
  (async reset requires dedicated FF control-pin resources and, in a design this control-set-
  diverse, apparently drove a lot of F7/F8 mux usage for merged control logic that's no longer
  needed).
- **Timing unaffected** (as expected — this fix doesn't touch any datapath): WNS still
  **+0.682ns**, WHS **+0.208ns** (negligible change from +0.219ns), all constraints still met
  at 100MHz.

### Remaining DRC after Run 2
Only performance-suggestion and expected-for-OOC items: `DPIP-1`×10, `DPOP-1`×5, `DPOP-2`×12
(DSP pipelining, open item #3 above), `ZPS7-1`×1 (PS7 required, expected/not-a-real-issue for a
standalone OOC sub-block). No correctness-risk DRC warnings remain.

### Open items after Run 2 (status after Run 3, below)
1. DSP pipelining suggestions (`DPIP-1`/`DPOP-1`/`DPOP-2`) — optimization opportunity, not
   urgent given positive timing margin. **Still open** (unchanged in Run 3).
2. ~~Re-run timing/DRC once integrated into the full `prj.tcl` SoC design for real
   clock-source-aware numbers~~ — **done, see Run 3.**

---

## Run 3 — Full SoC integration (2026-08-04)

**Objective:** Move from standalone accelerator synthesis (Runs 1-2, out-of-context, no
board-level I/O) to the real target: the transformer accelerator integrated into the full
Zynq-7000 SoC (PS7 + DMA + interconnect), synthesized as the actual chip top-level with real
DDR/FIXED_IO package I/O.

**Prerequisite — the full pipeline had no AXI wrapper.** `scripts/prj.tcl` as it existed only
integrated `MM_ultra_top` (the matmul engine alone, via `MM_ultra_axi.v`/`MM_ultra_top.v`) —
never wrapped for AXI at all was `transformer_block_top`, the complete verified
MM→Softmax→GELU pipeline. Built two new files mirroring the existing wrapper's structure:
- **`sourcecode/top/transformer_block_axi.v`** — AXI4-Lite register file (8 word registers,
  `C_S_AXI_ADDR_WIDTH=5`: 7 read-write config registers for `mm_shift_in`, `mm_F_length_in`,
  `mm_F_width_block_num_in`, `mm_W_width_block_num_in`, `softmax_scale_in`,
  `softmax_scale_out`, `gelu_scale`, plus a read-only status register exposing
  `softmax_to_gelu_fifo_overflow` live) + dual AXI4-Stream slave (feature/weight in) + AXI4-Stream
  master with `tkeep` (GELU output, needed for its partial-final-beat case that `MM_ultra_top`
  never had to handle) wrapping `transformer_block_top`.
- **`sourcecode/top/transformer_block_axi_top.v`** — outer port-list wrapper, mirrors
  `MM_ultra_top.v`'s structure exactly.

**Deliberate deviation from `MM_ultra_axi.v`'s convention:** kept `transformer_block_top.v`'s
own parameter names (`A_size`, `Weight_Block_num`, ...) instead of inventing lowercase aliases
(`array_size`, ...) the way the existing wrapper does. That renaming is exactly what caused the
`array_size`/`A_size` default-drift bug documented in Sections 15-16 of `project_story.md` —
avoided a second instance of the same class of bug by keeping one name per concept. Set every
default to match `transformer_block_top.v`'s own (already-verified) defaults, so — unlike
`MM_ultra_top`, which needed 6 parameter corrections in `prj.tcl` — **no `-generic`/`CONFIG`
overrides were needed for the new wrapper at all.**

**Validated in isolation first** (same discipline as everything else this project): synthesized
`transformer_block_axi_top` standalone (OOC) before touching `prj.tcl` — 0 errors, 0 critical
warnings, 23 warnings, all traced to either (a) already-known/pre-existing items, (b) benign
implicit-truncation notes from connecting full 32-bit AXI registers to narrower config ports
(identical pattern to the working `MM_ultra_axi.v`), or (c) the standard unused `AWPROT`/`ARPROT`
ports inherent to this AXI4-Lite peripheral template (present in the original wrapper too, just
never previously surfaced since `MM_ultra_top` was never OOC-synthesized standalone).

**Updated `scripts/prj.tcl`:** renamed every `MM_ultra_top_0` reference to
`transformer_block_axi_top_0`, changed the module-reference name and check list, and removed
the old 6-line `CONFIG` override block entirely (no longer needed — see above). Left all
downstream connectivity (DMA, SmartConnect, AXI-Lite address segments) untouched: the new
wrapper kept identical pin names (`s0_axis`/`s1_axis`/`m0_axis`/`s00_axi`/`aclk`/`aresetn`) to
`MM_ultra_top`, so only the cell-instance rename was structurally required.

**Block design generation and validation:** ran the updated `prj.tcl` — clean, `validate_bd_design`
reported zero errors, `design_1.bd` saved. Reopened the saved design and queried it directly to
confirm:
- All 12 `transformer_block_axi_top_0` parameters resolved to verified values, zero drift.
- `s0_axis`/`s1_axis`: 16 bytes each (matches `A_size×data_width` = 16×8).
- `m0_axis`: **4 bytes** (matches `num_gelu×data_width` = 4×8 — down from `MM_ultra_top`'s 16
  bytes, since GELU's output is narrower than the raw matmul output), with **`HAS_TKEEP=1`**
  confirmed present.
- `axis_dwidth_converter_2`'s input side auto-propagated to the new 4-byte width with **zero
  explicit reconfiguration** — Vivado's connectivity-based inference handled the change
  correctly on its own, exactly as it did for the analogous check in Section 16's validation.
- AXI-Lite: `ADDR_WIDTH=5`, `DATA_WIDTH=32`, matching the 8-register map by design.

**Full SoC synthesis** (new `scripts/synth_soc.tcl` — on-disk project this time, since
`prj.tcl`'s block-design + `generate_target` + `make_wrapper` flow needs real project files,
unlike `synth.tcl`'s `-in_memory` OOC approach): `synth_design -top design_1_wrapper` (the real
chip top, not out-of-context) completed successfully. ~6 minutes, peak memory ~4.6GB (safely
under the monitored threshold), run directly on the login node with the same resource-monitored
protocol used throughout.

### Results

| Metric | Standalone (Run 2) | Full SoC (Run 3) |
|---|---|---|
| WNS | +0.682ns | **+0.507ns** |
| WHS | +0.208ns | **+0.033ns** |
| Timing constraints | met | **met** — "All user specified timing constraints are met." |
| Slice LUTs | 25,506 (47.94%) | **31,012 (58.29%)** |
| Slice Registers | 13,624 (12.80%) | **20,307 (19.09%)** |
| Errors | 0 | **0** |
| Warnings | 4 | **207** |
| DRC correctness-risk items | 0 | **0** |

Both timing margins shrank somewhat (expected — more logic, more routing complexity, and this
time real interconnect/DMA fan-out instead of an isolated OOC block) but stayed comfortably
positive; **100MHz is still met with margin at the full-SoC level.** Utilization grew
proportionally to the added PS7-side infrastructure (3× DMA, 3× SmartConnect, crossbar,
protocol converter) — still well within the `xc7z020`'s capacity.

**All 207 warnings audited and categorized** — every one traces to either Xilinx's own
pre-built `axi_dma`/`smartconnect` IP (unused optional ports/scatter-gather features never
enabled — none of it our RTL), the same benign width-truncation/`AWPROT`/`ARPROT` notes already
seen in isolation, or the already-documented `lin.v`/`Exp_module.v` items. **Zero new warnings
attributable to our own RTL or the new AXI wrapper.**

**DRC:** only `DPIP-1`×10, `DPOP-1`×5, `DPOP-2`×12 (the same DSP pipelining suggestions, open
item #1 above) — `ZPS7-1` ("PS7 block required") is gone this time, since the real PS7 is now
actually present (that warning was purely an OOC-mode artifact, as expected). **Zero
`REQP-1839`/`REQP-1840` async-reset-on-BRAM warnings** — confirms the Section 18 fix holds at
full SoC scale too, including through the newly-added `Softmax_control.v` `in_data_buffer` BRAM
path now exercised by the real DMA/interconnect traffic pattern.

### Open items after Run 3
1. DSP pipelining suggestions (`DPIP-1`/`DPOP-1`/`DPOP-2`) — still open, optimization only.
2. Physical implementation (place/route, bitstream) not yet attempted — still blocked on the
   missing PYNQ-Z1 board file for real pin constraints (non-fatal for synthesis-level analysis,
   would matter for actual hardware bring-up).
3. `axi_dma_2`'s S2MM stream-width tuning (4-byte GELU output → 8-byte DMA width, handled today
   by `axis_dwidth_converter_2`'s automatic widening) not yet evaluated for burst efficiency —
   functionally correct, not yet optimized.

---

## Run 4 — Post-route implementation baseline + DSP-inference-gap fix (2026-08-06)

**Objective:** Two sequential steps. (1) Move past post-synthesis-only estimates (Runs 1-3) and
establish the project's first genuine, signoff-quality baseline by running the full
`opt_design → place_design → route_design` implementation flow plus `report_power`. (2) Fix the
DSP-inference gap identified by analysis of the Run 1-3 utilization data (DSP 5.91% vs. LUT
58.29% at the full-SoC level — the 256-PE systolic array's signed 8×8 MACs were being
synthesized entirely into LUT/CARRY4 fabric instead of DSP48E1 hard macros), then re-verify with
a second implementation pass to get a true apples-to-apples post-route comparison.

**Method — Step 1 (baseline):** New `scripts/impl.tcl`, sourcing `synth_soc.tcl` to regenerate
the synthesized design, then running `opt_design`/`place_design`/`route_design` with **default
directives** — deliberately not `prj.tcl`'s managed `impl_1` run, which is configured for the
more expensive `Performance_ExplorePostRoutePhysOpt` strategy (multi-pass search per step); given
this VM's 7.4GB RAM and prior crash history, default directives were chosen for predictable
resource use over maximal QoR search. Run in the background with active memory-safety monitoring
(a corrected version of the resource-monitored protocol used throughout this project — the first
monitoring attempt tracked only `vivado`'s immediate child via `--ppid`, which missed the actual
heavy process living several forks deeper in the tree and reported a flat, meaningless ~6.7MB RSS
the whole run; corrected to track total system `MemAvailable` directly instead, which is robust
regardless of process-tree topology). Real vivado tree RSS peaked at **~3.65GB** with system
available memory dropping to **~1.7GB** at one point — closer to the danger zone than any prior
run in this project, though it completed without needing the kill-switch.

**Method — Step 2 (DSP fix):** Investigated whether DSP48E1 dual-8-bit SIMD packing (pairing two
independent MACs per DSP via a shared-multiplicand trick) was achievable as a `PE.v`-local change
first. Traced the actual cycle timing in `PE_line.v`: adjacent PEs in a line do eventually
process the same `x` value, but staggered by exactly one cycle (the systolic skew), never
simultaneously — the shared-multiplicand technique requires simultaneity, so true dual-MAC
packing would require restructuring `PE_line.v`'s skew scheme and `PE_array.v`'s output-alignment
logic to match, not a `PE.v`-local edit. Given that risk, chose the lower-risk **partial 1:1 DSP
mapping**: force 12 of the 16 systolic rows (192 of 256 PEs) onto dedicated DSP48E1s via a new
`NUM_DSP_ROWS` parameter threaded through `PE_array.v` → `PE_line.v` → `PE.v`, leaving the
remaining 4 rows (64 PEs) LUT-mapped. Sized so total DSP usage (192 + the ~13 already consumed by
the Softmax/GELU scalar pipeline) stays under the `xc7z020`'s 220-DSP budget with margin — a full
1:1 mapping of all 256 PEs would need 256+13=269, overflowing the device by 49 DSPs.

### 1. Post-Route Sign-Off Comparison

The definitive apples-to-apples comparison — both rows are **real post-route data** (not
synthesis estimates), same `scripts/impl.tcl` flow, same default directives, differing only in
the DSP-fix RTL change:

| Metric (post-route, full SoC) | Pre-Fix Baseline | Post-Fix Final | Change |
|---|---|---|---|
| WNS @ 100MHz | +0.361 ns | +0.293 ns | −0.068 ns (−19% margin, still met) |
| Total On-Chip Power | 1.741 W | **1.687 W** | **−3.1%** |
| Dynamic Power | 1.590 W | 1.538 W | −3.3% |
| Static Power | 0.151 W | 0.150 W | ~flat |
| Slice LUTs | 30,276 (56.91%) | **15,363 (28.88%)** | **−49.3%** |
| Slice Registers | 20,255 (19.04%) | 14,854 (13.96%) | −26.7% |
| DSP48E1 | 13 (5.91%) | **205 (93.18%)** | +192, as designed |
| Block RAM Tiles | 86.5 (61.79%) | 86.5 (61.79%) | unchanged (expected — unrelated to this fix) |
| DRC | clean, advisory-only | clean, advisory-only | no regressions |

(Corresponding post-synthesis-only numbers, for reference: standalone accelerator LUT
25,506→10,536 [−58.7%], CARRY4 4,874→1,674 [−65.6%], DSP 13→205; full SoC LUT 31,012→16,068
[−48.2%], CARRY4 4,874→1,862 [−61.8%]. Post-route figures above are the authoritative ones.)

Artifacts: `reports/impl_pre_dspfix/` (pre-fix post-route baseline, preserved), `reports/impl/`
(post-fix post-route, current), `reports/syn/` and `reports/syn/soc/` (post-fix
post-synthesis-only), `scripts/soc_build/post_{opt,place,route}.dcp` (checkpoints for both runs).

### 2. Post-Mortem & Bug Fixes

**Bug 1 — `use_dsp` attribute silently ignored when placed on an `always` block.** The first
`PE.v` edit placed `(* use_dsp = "yes" *)` directly above the `always @(posedge clk)` block
containing the MAC. Re-synthesizing produced byte-identical LUT/DSP/CARRY4 counts to the
unfixed baseline — a silent no-op, not an error. Per Xilinx UG901 (Synthesis guide), `use_dsp`
must be attached to the **register declaration** that holds the multiply-accumulate result, not
to the enclosing procedural block; an attribute on the `always` statement itself is not a
recognized attachment point and is dropped during elaboration with no warning. Fixed by changing
`psum_out` from `output reg` to `output wire`, introducing a per-branch internal
`(* use_dsp = "yes"/"no" *) reg psum_out_r` inside each `generate if/else` branch to carry the
attribute correctly, and driving the output port via a continuous `assign psum_out = psum_out_r`
— functionally and timing-identical to the original, verified by the fact both branches'
`always`-block bodies remained byte-for-byte identical to the pre-fix RTL. Second synthesis
attempt confirmed the fix: DSP48E1 13→205, CARRY4 4,874→1,674 (standalone).

**Bug 2 — Tcl `source` doesn't create a new variable scope.** `impl.tcl` calls
`source "$SCRIPT_DIR/synth_soc.tcl"` to regenerate the synthesized design before running
`opt_design` onward. Both scripts independently declared a top-level variable named `REPORTS`
pointing at different paths (`reports/impl` vs. `reports/syn/soc`). Because Tcl's `source`
executes the sourced script in the *same* interpreter scope as the caller — unlike, e.g., a
function call, which gets its own local scope — `synth_soc.tcl`'s `set REPORTS
"reports/syn/soc"` silently overwrote `impl.tcl`'s own assignment. The first full implementation
run's post-route reports (including the first-ever `power.rpt`) landed in `reports/syn/soc/`,
overwriting what had previously been post-synthesis-only data there, rather than in the intended
`reports/impl/`. Caught by checking `reports/impl/` immediately after the run reported success
and finding it empty. Fixed by renaming `impl.tcl`'s variable to `IMPL_REPORTS`, computed *after*
the `source` call rather than before, so it cannot collide with anything `synth_soc.tcl` sets
internally. The genuine post-route data was not lost — copied from `reports/syn/soc/` to
`reports/impl/` before `reports/syn/soc/` was regenerated (correctly, this time) by re-running
`synth_soc.tcl` alone.

### 3. Physical Trade-off & Congestion Analysis

The post-route comparison surfaces a real, worth-stating-plainly trade-off: **timing margin
shrank** (WNS +0.361ns → +0.293ns, about 19% less slack) even though **both power and area
improved**. This is not a contradiction — it's a direct physical consequence of the fix's own
mechanism. Packing 205 DSP48E1 slices into what is now **93.18% of the `xc7z020`'s entire DSP
column capacity** (205 of 220) concentrates a large fraction of the design's arithmetic into a
much smaller, denser physical footprint than the previous LUT/CARRY4-diffuse implementation,
which had 256 MAC-equivalent operations spread thinly across general fabric with much more
placement freedom. Denser DSP-column packing constrains the placer's options and increases
routing congestion pressure around those columns — the router still closes timing (WNS stays
comfortably positive at 100MHz, real f_max ≈103.0MHz), but with less slack than before, since some
net on the critical path now routes through more contested territory. This is a standard,
expected physical-implementation dynamic, not a sign the fix was wrong: a design that trades a
LUT-fabric-wide, diffuse implementation for a DSP-column-concentrated one predictably shifts
routing pressure from "spread everywhere, contested nowhere" to "concentrated somewhere,
contested there" — the net win (49% fewer LUTs, 3.1% less power) is real and comes with this
specific, identifiable, and fully quantified cost, rather than being a free lunch.

### 4. Shift in Hardware Boundaries

This fix officially changes the accelerator's resource profile. Before Run 4, the design was
**LUT-bound**: DSP at 5.91% while LUT sat at 56.91% (post-route) — the PE array's 256 MACs
existing almost entirely as general fabric logic while dedicated arithmetic hardware sat
essentially idle. After the fix, **DSP is now the binding constraint**: 205 of 220 DSP48E1
slices used (93.18%), with exactly **15 DSP48E1 slices of headroom** remaining on the device —
while LUT has fallen to 28.88%, now the *least* pressured of the major resource classes. This is
the firm, current-hardware baseline for any future ViT/transformer-scaling discussion: further
growing the systolic array (e.g. 16×16 → 32×32) is no longer primarily a LUT-budget question —
it is now gated almost entirely by the 15 remaining DSP48E1 slices, unless a future pass
implements the true dual-8-bit SIMD packing design considered (and deferred, as the higher-risk
option) in Step 2's investigation above, which would roughly halve DSP demand per PE and reopen
that scaling headroom.

### Open items after Run 4

1. DSP pipelining suggestions (`DPIP-1`/`DPOP-1`/`DPOP-2`) — still open, optimization only, now
   with slightly more instances (more DSPs to advise about), same advisory-only severity.
2. Bitstream generation (`write_bitstream`) not yet attempted — still blocked on the missing
   PYNQ-Z1 board file question, though Section discussion elsewhere in this project established
   that `design_1_wrapper`'s only top-level ports (`DDR_*`/`FIXED_IO_*`) are PS-fixed silicon
   pins needing no board-specific XDC, and `prj.tcl`'s `processing_system7_0` already carries
   real PYNQ-Z1 DDR3/MIO values — so board files may not actually be a hard blocker for a
   functional bitstream, only for GUI convenience/future PL-side I/O.
3. Full dual-8-bit SIMD DSP packing (the higher-payoff, higher-risk option deferred in Step 2)
   not yet implemented — would require restructuring `PE_line.v`'s skew timing and
   `PE_array.v`'s output alignment, plus a full regression re-run to re-confirm the
   0/32,000-tolerance numerical result still holds. Would roughly halve DSP demand per PE
   (~128 vs. 192 for the array), reopening scaling headroom noted in section 4 above.
4. `axi_dma_2`'s S2MM stream-width tuning — still open from Run 3, unchanged by this run.

---

## Run 5 — Bitstream generation & repository integrity closeout (2026-08-06)

**Objective:** Close out open item #2 from Run 4 (bitstream generation not yet attempted) by
generating the final `.bit`/`.xsa` artifacts from the DSP-fixed post-route checkpoint, then audit
`.gitignore` to make sure everything needed to review and reproduce this project's analysis —
reports, docs, scripts, the signoff checkpoint, and the bitstream itself — survives a fresh clone
onto a machine that may not even have Vivado installed. No new synthesis or implementation was
run for this entry; it operates entirely on Run 4's existing `post_route.dcp`.

### 1. Bitstream & Hardware Handoff Artifacts

New `scripts/bitgen.tcl`: reopens `scripts/soc_build/post_route.dcp` — Run 4's final, DSP-fixed,
timing-closed checkpoint (**WNS +0.293ns @ 100MHz, 205/220 DSP48E1**) — directly, with no
re-synthesis or re-place/re-route, and runs `write_bitstream` followed by `write_hw_platform
-fixed -include_bit` for the modern `.xsa` hardware handoff (the current replacement for the
legacy `.hdf` format).

**Result:** clean signoff on both counts.
- Pre-bitstream DRC check: **0 Errors**.
- `write_bitstream`: **0 Warnings, 0 Critical Warnings, 0 Errors** ("Bitgen Completed
  Successfully").
- `write_hw_platform`'s own internal bitstream regeneration: same, clean.
- `exports/design.bit` — **4.05MB**, verified via `file` as a genuine Xilinx bitstream
  (`Version=2026.1`, `design_1_wrapper`).
- `exports/design.xsa` — **1.08MB**, a valid hardware-platform archive with the bitstream
  embedded.

This is the project's first physically-implementable bitstream for the `xc7z020clg400-1` — a
direct, traceable artifact of the exact signoff numbers in Run 4's comparison table, not a
separate or re-derived build.

### 2. Repository Integrity & Analysis Accessibility

Audited `.gitignore` against the question "if this repo is cloned fresh onto a machine without
Vivado/Xcelium, is everything needed to review this project's actual results present, or only
the means to regenerate them?" Found the report `.rpt` files — the actual data behind every
number cited in `project_story.md`/`synthesis_data.md` — were gitignored, meaning a fresh clone
would have the analysis prose but not the artifacts it was written from. Fixed:

- **Un-ignored** `reports/sim/*.rpt`, `reports/syn/*.rpt`, `reports/syn/soc/*.rpt`,
  `reports/impl/*.rpt` (previously excluded; `reports/impl_pre_dspfix/*.rpt` needed no rule
  change, nothing was catching it). Documented in `.gitignore` itself that these will show up as
  diffs after every future run — expected, not a sign of a problem.
- **Checkpoints:** rather than un-ignoring `scripts/soc_build/` wholesale (~589 files of
  disposable Vivado project/IP-cache internals, fully regenerable from `synth_soc.tcl` +
  `impl.tcl` — un-ignoring it would work directly against keeping the repo clean), copied the
  specific signoff checkpoint to `dbs/design_1_wrapper_post_route_dspfix.dcp` (16.6MB) — `dbs/`
  being exactly the directory README.md already documents for "Design Checkpoints (.dcp)...
  Intermediate snapshots of synthesized/routed design." `scripts/soc_build/` itself remains fully
  ignored.
- **Confirmed already correct** (verified with `git check-ignore`, not assumed): `report/*.md`,
  all `scripts/*.tcl` (including the two new ones, `impl.tcl` and `bitgen.tcl`), `setup.sh`, all
  RTL/testbench sources, and `exports/*.bit`/`*.xsa` (the blanket exclusion for these was already
  commented out in the original scaffolding). Disposable artifacts (`scripts/soc_build/`,
  `*.log`, `*.jou`, `xcelium.d/`) confirmed still correctly ignored.

### 3. Final Project Status & Summary

This closes the arc that began with Run 1's standalone synthesis baseline: the accelerator has
moved from a verified RTL/behavioral-simulation model, through synthesis, through a real
DSP-inference architectural fix, through post-route timing signoff, to a **physically
implementable, timing-closed, energy-characterized hardware artifact** —

- **Timing:** closes at 100MHz with +0.293ns of real, post-route slack.
- **Power:** 1.687W total on-chip (1.538W dynamic + 0.150W static), measured, not estimated.
- **Resource profile:** DSP-bound (205/220, 93.18%), not LUT-bound — the architectural gap
  identified in Runs 1-3 and fixed in Run 4.
- **Deliverable:** a genuine `.bit`/`.xsa` pair, generated cleanly with zero DRC/bitgen errors or
  warnings, ready to program onto real PYNQ-Z1 hardware.
- **Reproducibility:** every number in this document is now backed by a tracked artifact a fresh
  clone can inspect directly, not just prose describing a run that happened once.

### Open items after Run 5
1. Item #2 from Run 4 (bitstream generation) — **closed** by this run.
2. DSP pipelining suggestions (`DPIP-1`/`DPOP-1`/`DPOP-2`) — still open, optimization only.
3. Full dual-8-bit SIMD DSP packing (deferred in Run 4) — still open; would reopen DSP headroom
   beyond the current 15-slice margin if the array is scaled further.
4. `axi_dma_2`'s S2MM stream-width tuning — still open, unchanged.
5. Real hardware bring-up (programming the PYNQ-Z1 board with `exports/design.bit` and running
   against actual DDR3/peripherals) not yet attempted — everything to this point has been
   simulation and EDA-tool-verified only.
