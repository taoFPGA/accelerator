# taoFPGA

### An FPGA hardware accelerator for a Transformer block

> **Project #309** · Bar-Ilan University · Computer Engineering — Hardware and Chip Design track

taoFPGA implements one Transformer building block — a fused
**matrix-multiply → softmax → GELU** pipeline — as int8 streaming RTL on a
Xilinx Zynq-7000, driven from the ARM PS over AXI. It was designed,
verified, synthesized, placed & routed, and run on real silicon
(PYNQ-Z1/Z2, `xc7z020clg400-1`, 100 MHz).

---

## Team

| Role | Name | Contact |
|------|------|---------|
| Student | Eliran Turgeman | linkedin.com/in/elirantur1/ |
| Student | Shay Rask | linkedin.com/in/shay-rask-a0a570228 |
| Supervisor | David Freud | david.freud@mail.huji.ac.il |
| Academic authority | Dr. Leonid Yavits | Leonid.yavits@biu.ac.il |

---

## Results

| | Outcome |
|---|---|
| **Functional verification** | Full pipeline vs. a chained software golden model at real workload scale (200×96×160): **0 / 32,000 output elements outside tolerance**. Every stage also verified standalone. |
| **Timing (post-route, full SoC)** | Meets 100 MHz with **WNS +0.293 ns**; 0 failing endpoints. |
| **Resources (post-route)** | After the DSP-inference fix: **205 / 220 DSP48E1 (93 %)**, LUT **29 %**, BRAM comfortably within budget — the design is DSP-bound, not LUT-bound. |
| **Hardware bring-up** | Bitstream + hardware handoff generated ([`exports/`](exports/)) and executed on a PYNQ-Z2. |
| **ViT kernel benchmark** | On the fused matmul+softmax+GELU op at ViT-Tiny shapes: **70–98× faster** than the board's ARM CPU running the same op. Scoped as a kernel-level number, *not* an end-to-end ViT-inference claim — see [`apps/vit/vit_benchmark.py`](apps/vit/vit_benchmark.py). |

The full story — architecture decisions, every simulation/synthesis run, the
bugs found and fixed — is written up in the project book and paper (see
**Documentation** below).

---

## Repository layout

```
taoFPGA/
├── sourcecode/     RTL — see sourcecode/README.md for the module map
│   ├── core/       compute: systolic MAC array, softmax & GELU math, AXI IP wrappers
│   ├── top/        integration: the 3 stages wired together + stream adapters + AXI
│   ├── tb/         SystemVerilog testbenches (per-stage + full pipeline)
│   └── sim/        Xcelium automation (Makefile, PBS wrapper, SimVision preset)
│
├── apps/           software: bare-metal Zynq self-test (C++), PYNQ driver (MM.py),
│                   pure-NumPy ViT-Tiny + kernel benchmark (vit/)
│
├── scripts/        Vivado Tcl flow: synth / synth_soc / impl / bitgen / prj
│
├── dbs/            intentional design checkpoints (.dcp)
├── exports/        final deliverables: design.bit / design.xsa / design.hwh
├── reports/        synthesis / implementation / simulation report artifacts (*.rpt)
├── inputs/  mem_gen/  libraries/    placeholder dirs for the intended
│                   constraints / weight-conversion / vendor-IP workflow
│                   (the current OOC + PS7-clock flow needs none of them)
│
├── report/         the finished written deliverables (project book, final
│                   presentation, first report) as PDF + the overview video
│
├── setup.sh        sources the EDA toolchain, auto-detects the Vivado version
├── LICENSE         Apache-2.0
└── NOTICE
```

---

## Build & run

```sh
source setup.sh          # put Vivado / Xcelium on PATH

# --- RTL simulation (Xcelium) --- from sourcecode/sim/
make run_gelu            # light  — GELU lane vs. real-valued reference
make run_softmax         # light  — Softmax vs. numerically-stable reference
make run_mm              # heavy  — MM_ultra vs. integer matmul reference
make run_transformer     # heavy  — full pipeline vs. chained golden model
#   heavy targets: submit through sim/run_xrun.pbs, the login node is shared.
#   reports land in reports/sim/*.rpt

# --- Vivado flow --- from scripts/
vivado -mode batch -source synth.tcl       # OOC synthesis, transformer_block_top
vivado -mode batch -source synth_soc.tcl   # full SoC synthesis
vivado -mode batch -source impl.tcl        # place & route + signoff reports
vivado -mode batch -source bitgen.tcl      # -> exports/design.bit, design.xsa

# --- ViT kernel benchmark --- on the board, from apps/vit/
python export_vit_weights.py   # dev machine only: fetch pretrained timm weights
python vit_benchmark.py        # NumPy ViT-Tiny baseline + measured kernel speedup
```

The tool versions used: Vivado 2023.x/2024.x, Xcelium 23.09, Python 3.9+.

---

## Documentation

| Document | File |
|----------|------|
| Bar-Ilan final project book | [`report/taoFPGA_Project_Book.pdf`](report/taoFPGA_Project_Book.pdf) |
| Final presentation | [`report/taoFPGA_Final_Presentation.pdf`](report/taoFPGA_Final_Presentation.pdf) |
| First (midterm) report | [`report/First_Project_Report_Group_309.pdf`](report/First_Project_Report_Group_309.pdf) |
| Overview video (3B1B-style, 1080p60) | [`report/TaoFPGAOverview.mp4`](report/TaoFPGAOverview.mp4) |
| RTL guide (pipeline diagram, module map, fixed-point notation) | [`sourcecode/README.md`](sourcecode/README.md) |

Every RTL and application source file carries a header comment explaining
what it does and how it fits the pipeline.

---

## License

Apache License 2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
Bundled third-party reference data (ImageNet class list, one sample image,
the `timm` ViT-Tiny architecture) is identified in `NOTICE`; pretrained
weights are fetched at setup time and are not redistributed here.

---

## References

1. Vaswani et al. (2017). *Attention Is All You Need.* NeurIPS.
2. Zhu, Li, Chen & Ma (2023). *High-Performance FPGA Acceleration for Transformer-Based Models: A Survey.* IEEE TVLSI.
3. Li, Chen, Cheng & Huang (2022). *ME-ViT: A Single-Load Memory-Efficient FPGA Accelerator for Vision Transformers.* ACM/IEEE ISLPED.
4. Liu & Sun (2021). *FTRANS: Energy-Efficient Acceleration of Transformers using FPGA.* ACM/SIGDA FPGA.
5. Cai, Zhang & Chen (2020). *A High-Throughput and Energy-Efficient FPGA-Based Transformer Accelerator.* IEEE IPDPS.
