# `sourcecode/` — RTL for the taoFPGA Transformer accelerator

This is the hardware. It implements one Transformer building block —
**MatMul → Softmax → GELU** — as a single streaming pipeline that a Zynq PS
drives over AXI. The written design rationale lives in
[`../report/`](../report/) (Project Book / paper); this file is the map
for reading the code.

## Pipeline at a glance

```
          features (int8)                 weights (int8)
                │                               │
          ┌─────▼───────────────────────────────▼─────┐
          │  MM_ultra          tiled integer matmul   │   core/MM_ultra.v
          │  ├ MM_in_buffer    whole-matrix staging   │
          │  ├ MM_buffer ─ MM ─ PE_array  systolic MAC │
          │  └ MM_out_buffer   accumulate + requantize │
          └─────┬─────────────────────────────────────┘
                │ A_size int8 lanes / cycle
        axis_downsizer      wide beat → 1 scalar/cycle      top/axis_downsizer.v
                │
          ┌─────▼─────┐
          │ Softmax_control   buffer a row, replay it 3×   core/Softmax_control.v
          │  └ Softmax ─ Exp_module / Ln_module           │  (max, Σexp, normalize)
          └─────┬─────┘
                │ 1 scalar/cycle, no backpressure
        axis_upsizer_fifo   elastic FIFO, 1 → num_gelu/beat  top/axis_upsizer_fifo.v
                │
          ┌─────▼─────┐
          │ EightGelus       num_gelu parallel GELU lanes   core/EightGelus.v
          │  └ gelu ─ lin                                   │
          └─────┬─────┘
                │
          output (int8, num_gelu lanes, with `keep`)
```

Default configuration (from `top/transformer_block_top.v`, matched by
`scripts/synth.tcl` and every testbench): `A_size = 16`, `data_width = 8`
(int8), `num_gelu = 4`, target part `xc7z020clg400-1` (PYNQ-Z1/Z2).

## Directory layout

| Path | What's in it |
|------|--------------|
| `core/` | The compute modules — the matmul array, the softmax/GELU math, and their per-stage AXI-Lite IP wrappers. |
| `top/`  | Integration: the three stages wired back-to-back (`transformer_block_top.v`), the stream width/rate adapters between them, and the combined AXI wrapper (`transformer_block_axi*.v`). |
| `tb/`   | SystemVerilog testbenches — one per stage plus a full-pipeline one. |
| `sim/`  | Xcelium automation (`Makefile`, PBS wrapper, SimVision wave preset). |
| `hls/`  | Placeholder for optional Vitis HLS experiments (empty). |

### `core/` module map

| File | Role |
|------|------|
| `PE.v` | One weight-stationary multiply-accumulate cell. |
| `PE_line.v` / `PE_array.v` | A row of PEs / the full `A_size`×`A_size` systolic array, with the skew buffers that keep the wavefront aligned. |
| `MM.v` | Weight loader + activation feeder around `PE_array`. |
| `MM_buffer.v` | Per-tile weight/feature replay sequencer (FSM: load weights → stream features). |
| `MM_in_buffer.v` | Soaks up the whole feature and weight matrices, dispatches them tile by tile. |
| `MM_out_buffer.v` | Wide accumulator BRAM across contraction passes, then requantize to int8. |
| `AdderS.v` | SIMD saturating signed adder (used by `MM_out_buffer`). |
| `right_shifter.v` | Rounding, saturating arithmetic right shift — the requantize step. |
| `MM_ultra.v` | Top of the matmul core: ties the four buffers together. |
| `Softmax.v` | Streaming numerically-stable softmax datapath (3-pass: max, Σexp, normalize). |
| `Softmax_control.v` | Buffers one row and replays it into `Softmax.v` the three times it needs. |
| `Exp_module.v` | Fixed-point `e^x` for `x ≤ 0` (base-2 split + linear fraction term). |
| `Ln_module.v` | Fixed-point `ln(x)` for `x ≥ 1` (leading-one normalize + one multiply). |
| `EightGelus.v` | `num_gelu` parallel GELU lanes with AXI-Stream framing. |
| `gelu.v` | One int8 GELU lane — tanh approximation, matches `F.gelu(approximate='tanh')`. |
| `lin.v` | The even quadratic kernel inside the GELU approximation. |
| `*_top.v` / `*_axi.v` | Xilinx AXI4-Lite + AXI4-Stream IP wrappers so each stage can also be used standalone in a block design. Register maps are in each `*_axi.v` header. |

## Fixed-point notation

Signal names carry their fixed-point format as a suffix, e.g. `x_max_S9Q10`,
`e_sum_U8Q12`, `x_U8Q8`:

* **`S`** = signed (two's-complement), **`U`** = unsigned.
* **`i`** in `SiQf` / `UiQf` = number of integer bits (including the sign bit
  for `S`), **`f`** = number of fractional bits. Total width = `i + f`.
* The real value of a raw register `r` is `r / 2^f`.

Example: `S9Q10` means 9 integer bits + 10 fractional bits = 19 value bits
(usually carried in a 20-bit signed reg, so the names track the intended
math while the declared width keeps a spare guard bit). `U0Q25` is a pure
fraction in `[0, 1)`.

The runtime `scale_in` / `scale_out` / `shift` / `in_scale` register values
are just the `f` (fraction-bit count) to use at that interface — the
software driver (`apps/MM.py`, `apps/golden_model.py`) and the testbenches
use the identical constants.

## Building & simulating

```sh
# RTL simulation (Xcelium) — from sourcecode/sim/
make run_gelu          # light  — single GELU lane vs. real-valued reference
make run_softmax       # light  — Softmax_control vs. numerically-stable ref
make run_mm            # heavy  — MM_ultra vs. integer matmul ref  (batch!)
make run_transformer   # heavy  — full pipeline vs. chained golden model
make waves_transformer # + open SimVision with sim/waves.tcl preset
# Reports land in ../reports/sim/*.rpt

# Synthesis / implementation (Vivado) — from scripts/
vivado -mode batch -source synth.tcl       # OOC baseline, transformer_block_top
vivado -mode batch -source synth_soc.tcl   # full SoC
vivado -mode batch -source impl.tcl        # place & route, signoff reports
vivado -mode batch -source bitgen.tcl      # bitstream -> ../exports/
```

The shared login node is easily overloaded — run the heavy `make` targets
through the batch scheduler (`sim/run_xrun.pbs`), not interactively. See
`sim/Makefile` for the full target list.
