# 🚀 Transformer Accelerator on FPGA (taoFPGA)

| **Project Info** | **Details** |
| :--- | :--- |
| **Project Number** | 309 |
| **Team** | Eliran Turgeman & Shay Rask |
| **Supervisor** | David Freud |

---

## 📖 Project Overview

The goal of this project is to design and implement a hardware accelerator on an **FPGA platform (Xilinx/Intel)** to optimize the inference of Transformer models.

The accelerator focuses on improving **Latency**, **Throughput**, and **Energy Efficiency** by utilizing specialized hardware structures like **Systolic Arrays** and advanced **Quantization** techniques.

---

## 📂 Directory Structure

```text
taoFPGA/
├── src/               # Core logic (HLS, RTL, IP)
├── sim/               # Verification (Testbenches, Golden Models)
├── sw/                # Host software & Drivers
├── data/              # Model weights & Test sets
├── docs/              # Documentation & Reports
├── scripts/           # Automation & Build scripts
└── constraints/       # Physical & Timing constraints

Detailed Breakdown
src/ (Source Code)
Contains all the core logic files for the hardware design.

src/hls/ – Stores C/C++ source files intended for High-Level Synthesis (HLS), allowing for faster development of complex algorithms like Softmax and LayerNorm.

src/rtl/ – Contains hardware description files (Verilog/SystemVerilog) for low-level structural design, such as the Systolic Array processing elements (PEs).

src/ip/ – Houses configuration files for vendor-specific Intellectual Property (IP) cores, such as Xilinx DSP macros or memory controllers.

sim/ (Simulation & Verification)
Dedicated to verifying the functional correctness of the design before hardware deployment.

sim/testbenches/ – Hardware-level testbenches (RTL) to simulate the signals and timing of the accelerator.

sim/models/ – High-level "Golden Models" (often in Python or C) used to generate expected results for comparison with hardware outputs.

sw/ (Software & Drivers)
Contains code that runs on the Host CPU or embedded processor to control the FPGA.

sw/driver/ – Logic for managing communication between the CPU and FPGA, including DMA (Direct Memory Access) and PCIe interfaces.

sw/app/ – Application-level scripts (e.g., Python/Jupyter) for loading data, running inference, and testing on platforms like PYNQ.

data/ (Model Data)
Storage for the inputs and parameters required for the Transformer model.

data/weights/ – Quantized model weights (e.g., INT8 or BCM format) that are loaded into the FPGA’s on-chip memory.

data/test_sets/ – Sample datasets used for evaluation, such as WikiText-2 or IMDB review sets.

docs/ (Documentation)
Essential documentation for project deliverables as defined in the pre-project report.

docs/architecture/ – Detailed Micro-Architecture documentation, including block diagrams of PEs and memory hierarchies.

docs/reports/ – Synthesis and implementation reports detailing hardware resource utilization (DSPs, BRAMs) and power consumption.

scripts/ (Automation)
Contains automation tools to streamline the build process.

prj.tcl – Tcl scripts for automated project creation, synthesis, and Bitstream generation in Vivado or Quartus.

Python/Bash scripts for managing the end-to-end development flow.

constraints/ (Hardware Constraints)
Stores XDC (Xilinx Design Constraints) files that map the logical signals of the design to the physical pins of the FPGA board and define timing requirements.
