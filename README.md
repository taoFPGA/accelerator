# 🔧 Transformer_FPGA
### FPGA-Based Hardware Accelerator for Transformer Models

> **Project #309** | Bar-Ilan University | Computer Engineering – Hardware and Chip Design Track

---

## 👥 Team

| Role | Name | ID | Contact |
|------|------|----|---------|
| Student | Eliran Turgeman | 316372002 | — |
| Student | Shay Rask | 314951658 | — |
| Supervisor | David Freud | — | david.freud@mail.huji.ac.il |
| Academic Authority | Dr. Leonid Yavits | — | Leonid.yavits@biu.ac.il |

---

## 📌 Project Overview

Transformer models are the current state-of-the-art in both **Natural Language Processing (NLP)** and **Computer Vision** (Vision Transformers – ViT). Their high computational complexity and memory requirements create significant bottlenecks in real-time, low-latency, and energy-constrained environments — challenges that become critical when targeting **edge devices**.

This project designs, implements, and evaluates a complete **Hardware Accelerator** for a selected Transformer model, deployed on an **FPGA platform** using AMD/Xilinx Vivado.

### Key Performance Targets vs. CPU/GPU Baselines

| Metric | Goal |
|--------|------|
| ⚡ Latency | Reduced inference time per sample |
| 📈 Throughput | Higher inference samples per second |
| 🔋 Energy Efficiency | Lower power consumption per inference |

---

## 📦 Project Deliverables

1. **Functional Hardware Prototype** — A complete bitstream deployed on FPGA, capable of executing inference for a Transformer component (e.g., Attention block or full compact model).
2. **Comprehensive Final Report** — Full documentation covering background, architecture decisions, implementation stages, testing, and performance evaluation.
3. **Midterm & Final Presentations** — Two structured presentations covering progress, architectural decisions, performance findings, and conclusions.
4. **Micro-Architecture Documentation** — Block diagrams, PE descriptions, memory hierarchy, dataflow methods (Memory Tiling, Systolic Array), and methodology docs.

---

## 📁 Directory Structure

```
Transformer_FPGA/
│
├── apps/               # High-level models (Python / PyTorch / C++)
│                       # Golden Model verification and weight extraction
│
├── dbs/                # Database files and Design Checkpoints (.dcp)
│                       # Intermediate snapshots of synthesized/routed design
│
├── exports/            # Final deliverables
│                       # Bitstreams (.bit), Hardware handoff (.xsa), log archives
│
├── inputs/             # Design inputs and constraints
│                       # Xilinx Design Constraints (.xdc), clock definitions, pin mapping
│
├── libraries/          # Vendor IPs and external primitives
│                       # Xilinx/Intel IP cores (e.g., Floating Point units, AXI interconnects)
│
├── mem_gen/            # Weight conversion scripts and tools
│                       # Converts PyTorch weights to fixed-point/hex (.coe, .mem)
│
├── reports/            # Analysis outputs after implementation
│                       # Timing (WNS), Power, Resource Utilization (LUT, FF, BRAM, DSP)
│
├── scripts/            # Automation scripts for the Vivado build flow
│                       # Tcl scripts for Synthesis, Implementation, Bitstream generation
│
├── sourcecode/         # All HDL source files
│   ├── core/           # Transformer modules: Attention, MLP, LayerNorm, Softmax
│   ├── hls/            # C/C++ source for Vitis HLS modules (optional)
│   ├── top/            # Top-level wrapper connecting accelerator to SoC bus (AXI/AHB)
│   └── tb/             # Testbenches and simulation environments
│
├── workspace/          # Local EDA tool runtime directory (gitignored)
│
├── .gitignore
├── README.md
└── setup.sh            # Sources EDA tool paths and environment variables
```

---

## 🚀 Getting Started

```bash
# 1. Source the environment
source setup.sh

# 2. Generate weights from the golden model
cd apps/
python export_weights.py --model transformer_base --output ../mem_gen/weights/

# 3. Convert weights to FPGA memory format
cd ../mem_gen/
python float_to_fixed.py --input weights/ --output ../inputs/mem/

# 4. Run RTL simulation
vivado -mode batch -source scripts/sim.tcl

# 5. Run the full implementation flow
vivado -mode batch -source scripts/synth.tcl
vivado -mode batch -source scripts/impl.tcl
vivado -mode batch -source scripts/bitgen.tcl

# 6. Check results
ls reports/    # Timing, power, and utilization summaries
ls exports/    # Final .bit and .xsa files
```

---

## 🔄 Build Flow

```
PyTorch Golden Model (apps/)
         │
         ▼
Weight Extraction ──► Fixed-Point Conversion (mem_gen/)
         │
         ▼
RTL Design (sourcecode/core/, top/)
         │
         ▼
Simulation & Verification (sourcecode/tb/) ◄── vs. Golden Model
         │
         ▼
Synthesis (scripts/synth.tcl) ──────────────► reports/synth_utilization.rpt
         │
         ▼
Implementation P&R (scripts/impl.tcl) ──────► reports/timing_summary.rpt
         │                                     reports/power_analysis.rpt
         ▼
Bitstream Generation (scripts/bitgen.tcl) ──► exports/design.bit
         │                                     exports/design.xsa
         ▼
FPGA Programming & Hardware Validation
```

---

## 🗓️ Work Plan & Milestones

| # | Phase | Description | Target | Owner |
|---|-------|-------------|--------|-------|
| 1 | Literature Review | Transformer architectures, quantization, FPGA acceleration | 12/2025 | Eliran |
| 2 | Architecture Selection | Model selection, quantization strategy, block-level design | 01/2026 | Shay |
| 3 | POC Implementation | First accelerator component in HLS/Verilog + verification | 02/2026 | Eliran |
| ⭐ | **Midterm Presentation** | | **02/2026** | **Both** |
| 4 | Full Implementation | All PEs completed, full system integration | 04/2026 | Shay |
| 5 | Performance Testing | FPGA deployment, inference tests, Latency/Throughput measurement | 05/2026 | Eliran |
| 6 | Results & Final Report | CPU/GPU comparison, analysis, report writing | 06/2026 | Both |
| ⭐ | **Final Presentation & Report** | | **06/2026** | **Both** |

---

## 🛠️ Tools & Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Vivado | 2023.x / 2024.x | Synthesis, Implementation, Bitstream |
| Vitis HLS | optional | HLS module development |
| Python | 3.9+ | Golden model and weight conversion |
| PyTorch | 2.x | Transformer golden model |
| Verilog / VHDL | — | RTL implementation language |

---

## 📚 References

1. Vaswani et al. (2017). **"Attention Is All You Need."** *NeurIPS.*
2. Zhu, Li, Chen & Ma (2023). **"High-Performance FPGA Acceleration for Transformer-Based Models: A Survey."** *IEEE Transactions on VLSI Systems.*
3. Li, Chen, Cheng & Huang (2022). **"ME-ViT: A Single-Load Memory-Efficient FPGA Accelerator for Vision Transformers."** *ACM/IEEE ISLPED.*
4. Liu & Sun (2021). **"FTRANS: Energy-Efficient Acceleration of Transformers using FPGA."** *ACM/SIGDA FPGA Symposium.*
5. Cai, Zhang & Chen (2020). **"A High-Throughput and Energy-Efficient FPGA-Based Transformer Accelerator."** *IEEE IPDPS.*
