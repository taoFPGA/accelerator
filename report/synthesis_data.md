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

### Open items for next run
1. Root-cause and fix the REQP-1839/1840 async-reset-on-BRAM-control gap (highest priority —
   real correctness risk, not just a style nit).
2. Investigate why `fifo_mem_reg` in `axis_upsizer_fifo.v` couldn't map to Block RAM.
3. Consider whether the DPIP-1/DPOP-1/DPOP-2 DSP pipelining suggestions are worth taking once
   the design is otherwise stable — timing has positive margin today, so not urgent, but cheap
   wins for a later pass.
4. Re-run timing/DRC once this block is integrated into the full `prj.tcl` SoC design, to get
   real clock-source-aware numbers instead of the OOC estimate.
