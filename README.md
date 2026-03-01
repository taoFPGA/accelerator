
================================================================================
  TRANSFORMER_FPGA
  Transformer Accelerator on FPGA  |  Project #309
  Bar-Ilan University  |  Computer Engineering - Hardware and Chip Design Track
================================================================================

  Supervisor        : David Freud          (david.freud@mail.huji.ac.il)
  Academic Authority: Dr. Leonid Yavits   (Leonid.yavits@biu.ac.il)
  Student 1         : Eliran Turgeman      (-)
  Student 2         : Shay Rask            (-)

================================================================================
  TABLE OF CONTENTS
================================================================================

  1. Project Overview
  2. Project Deliverables
  3. Directory Structure
  4. Getting Started
  5. Build Flow
  6. Work Plan & Milestones
  7. Tools & Requirements
  8. References

================================================================================
  1. PROJECT OVERVIEW
================================================================================

  Transformer models are the current state-of-the-art in both Natural Language
  Processing (NLP) and Computer Vision (Vision Transformers - ViT). Their high
  computational complexity and memory requirements create significant bottlenecks
  in real-time, low-latency, and energy-constrained environments -- challenges
  that become critical when targeting edge devices.

  This project designs, implements, and evaluates a complete Hardware Accelerator
  for a selected Transformer model, deployed on an FPGA platform using Vivado.

  Key performance targets vs. CPU/GPU baselines:
    - Latency      : Reduced inference time per sample
    - Throughput   : Higher inference samples per second
    - Efficiency   : Lower power consumption per inference operation

================================================================================
  2. PROJECT DELIVERABLES
================================================================================

  [1] Functional Hardware Prototype
      A complete bitstream deployed on FPGA capable of executing inference
      for a Transformer component (e.g., Attention block or full compact model).

  [2] Comprehensive Final Project Report
      Full documentation: background, architecture decisions, implementation
      stages, testing procedures, and performance evaluation.

  [3] Midterm and Final Presentations
      Two structured presentations covering project progression, architectural
      decisions, performance findings, and conclusions.

  [4] Full Hardware Micro-Architecture Documentation
      Block diagrams, Processing Element (PE) descriptions, memory hierarchy,
      dataflow methods (Memory Tiling, Systolic Array), and methodology docs
      (HLS or Verilog/VHDL).

================================================================================
  3. DIRECTORY STRUCTURE
================================================================================

  Transformer_FPGA/
  |
  +-- apps/               High-level models (Python / PyTorch / C++)
  |                       Golden Model verification and weight extraction.
  |                       Run first to generate expected outputs for RTL comparison.
  |
  +-- dbs/                Database files and Design Checkpoints (.dcp)
  |                       Intermediate snapshots of synthesized/routed design.
  |                       Commit checkpoints manually at clean milestones.
  |
  +-- exports/            Final deliverables
  |                       Bitstreams (.bit), Hardware handoff (.xsa), log archives.
  |                       Outputs flashed to FPGA or handed to the PS side.
  |
  +-- inputs/             Design inputs and constraints
  |                       Xilinx Design Constraints (.xdc): clock definitions,
  |                       pin mapping, timing exceptions, and I/O standards.
  |
  +-- libraries/          Vendor IPs and external primitives
  |                       Xilinx/Intel IP cores and external modules
  |                       (e.g., Floating Point units, AXI interconnects).
  |
  +-- mem_gen/            Weight conversion scripts and tools
  |                       Converts PyTorch weights (float) to fixed-point or
  |                       hex formats (.coe, .mem) for BRAM initialization.
  |
  +-- reports/            Analysis outputs after implementation
  |                       Timing summary (WNS), Power analysis,
  |                       Resource Utilization (LUT, FF, BRAM, DSP counts).
  |
  +-- scripts/            Automation scripts for the Vivado build flow
  |                       Tcl scripts for Synthesis, Implementation, Bitstream.
  |                       Entire flow runnable from these scripts alone:
  |                         vivado -mode batch -source scripts/synth.tcl
  |                         vivado -mode batch -source scripts/impl.tcl
  |                         vivado -mode batch -source scripts/bitgen.tcl
  |
  +-- sourcecode/         All HDL source files
  |   |
  |   +-- core/           Transformer compute modules
  |   |                   Attention (QKV, Scaled Dot-Product, Softmax),
  |   |                   MLP (Linear + Activation), LayerNorm.
  |   |
  |   +-- hls/            High-Level Synthesis source (optional)
  |   |                   C/C++ for modules developed in Vitis HLS.
  |   |                   Export generated RTL into core/ after validation.
  |   |
  |   +-- top/            Top-level wrapper
  |   |                   Connects accelerator core to SoC bus (AXI/AHB).
  |   |                   Instantiates core/ modules and control interface.
  |   |
  |   +-- tb/             Testbenches and simulation environments
  |                       Self-checking testbenches comparing RTL outputs
  |                       against golden model references from apps/.
  |
  +-- workspace/          Local EDA tool runtime directory (GITIGNORED)
  |                       Auto-generated by Vivado (.cache, .runs, .sim).
  |                       Safe to delete and regenerate at any time.
  |
  +-- .gitignore          Excludes tool-generated and binary files from git
  +-- README.md           This file
  +-- setup.sh            Sources EDA tool paths and environment variables
                          Run before any Vivado session:  source setup.sh

================================================================================
  4. GETTING STARTED
================================================================================

  Step 1 - Source the environment:
    source setup.sh

  Step 2 - Generate weights from the golden model:
    cd apps/
    python export_weights.py --model transformer_base --output ../mem_gen/weights/

  Step 3 - Convert weights to FPGA memory format:
    cd mem_gen/
    python float_to_fixed.py --input weights/ --output ../inputs/mem/

  Step 4 - Run RTL simulation:
    vivado -mode batch -source scripts/sim.tcl

  Step 5 - Run the full implementation flow:
    vivado -mode batch -source scripts/synth.tcl
    vivado -mode batch -source scripts/impl.tcl
    vivado -mode batch -source scripts/bitgen.tcl

  Step 6 - Check results:
    ls reports/       <-- Timing, power, and utilization summaries
    ls exports/       <-- Final .bit and .xsa files

================================================================================
  5. BUILD FLOW
================================================================================

    PyTorch Golden Model  (apps/)
             |
             v
    Weight Extraction --> Fixed-Point Conversion  (mem_gen/)
             |
             v
    RTL Design  (sourcecode/core/, top/)
             |
             v
    Simulation & Verification  (sourcecode/tb/)  <-- vs. Golden Model
             |
             v
    Synthesis  (scripts/synth.tcl)               --> reports/synth_utilization.rpt
             |
             v
    Implementation P&R  (scripts/impl.tcl)       --> reports/timing_summary.rpt
             |                                       reports/power_analysis.rpt
             v
    Bitstream Generation  (scripts/bitgen.tcl)   --> exports/design.bit
             |                                       exports/design.xsa
             v
    FPGA Programming & Hardware Validation

================================================================================
  6. WORK PLAN & MILESTONES
================================================================================

  Phase  Description                              Target    Owner
  -----  ---------------------------------------  --------  ---------------
    1    Literature Review & Theoretical          12/2025   Eliran Turgeman
         Foundation (Transformer architectures,
         quantization, FPGA acceleration)

    2    Architecture Selection & Methodology     01/2026   Shay Rask
         (Model selection, quantization strategy,
         block-level hardware architecture)

    3    Critical Component Implementation / POC  02/2026   Eliran Turgeman
         (First accelerator component in HLS
         or Verilog + initial verification)

         *** MIDTERM PRESENTATION ***             02/2026   Both

    4    Full Implementation & System Integration 04/2026   Shay Rask
         (All PEs completed, full accelerator
         system integrated and ready for FPGA)

    5    Performance Testing & Calibration        05/2026   Eliran Turgeman
         (FPGA deployment, inference tests,
         Latency/Throughput measurement)

    6    Results Analysis & Final Report          06/2026   Both
         (CPU/GPU comparison, analysis,
         comprehensive report writing)

         *** FINAL PRESENTATION & REPORT ***      06/2026   Both

================================================================================
  7. TOOLS & REQUIREMENTS
================================================================================

  Tool              Version           Purpose
  ----------------  ----------------  -----------------------------------------
  Vivado            2023.x / 2024.x   Synthesis, Implementation, Bitstream gen
  Vitis HLS         (optional)        HLS module development
  Python            3.9+              Golden model and weight conversion
  PyTorch           2.x               Transformer golden model
  Verilog / VHDL    --                RTL implementation language

================================================================================
  8. REFERENCES
================================================================================

  [1] Vaswani et al. (2017)
      "Attention Is All You Need."
      Advances in Neural Information Processing Systems.

  [2] Zhu, Li, Chen & Ma (2023)
      "High-Performance FPGA Acceleration for Transformer-Based Models: A Survey."
      IEEE Transactions on VLSI Systems.

  [3] Li, Chen, Cheng & Huang (2022)
      "ME-ViT: A Single-Load Memory-Efficient FPGA Accelerator for Vision Transformers."
      ACM/IEEE ISLPED.

  [4] Liu & Sun (2021)
      "FTRANS: Energy-Efficient Acceleration of Transformers using FPGA."
      ACM/SIGDA International Symposium on FPGAs.

  [5] Cai, Zhang & Chen (2020)
      "A High-Throughput and Energy-Efficient FPGA-Based Transformer Accelerator."
      IEEE IPDPS.

================================================================================
