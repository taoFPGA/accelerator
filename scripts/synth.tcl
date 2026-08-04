################################################################################
# taoFPGA -- Synthesis automation (in-memory, non-project batch mode)
#
# Establishes an area/timing baseline for the full transformer accelerator
# pipeline (MM_ultra -> Softmax_control -> EightGelus, chained via the
# top/*.v adapters), targeting the PYNQ-Z1 board's Zynq-7000 part.
#
# Top module: transformer_block_top -- the complete verified pipeline, not
# just the MM_ultra_top AXI-wrapped sub-block that scripts/prj.tcl integrates
# into the SoC. transformer_block_top.v's own declared parameter defaults
# (A_size=16, data_width=8, shift_width=10, *_Block_num=2400, ...) already
# match everything verified in simulation -- see report/simulation_data.md
# and report/project_story.md -- so no -generic overrides are needed here.
#
# Usage:
#   cd scripts && vivado -mode batch -source synth.tcl
#   (or from anywhere: vivado -mode batch -source /path/to/scripts/synth.tcl)
################################################################################

set PART        "xc7z020clg400-1"
set TOP_MODULE  "transformer_block_top"

# Baseline clock: 100MHz, matching the Zynq PS7's FCLK0 configuration in
# scripts/prj.tcl (CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}) -- this is the
# clock this accelerator actually runs from once integrated into the SoC.
set CLK_PERIOD_NS 10.000

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file normalize "$SCRIPT_DIR/.."]
set CORE       "$REPO_ROOT/sourcecode/core"
set TOPDIR     "$REPO_ROOT/sourcecode/top"
set REPORTS    "$REPO_ROOT/reports/syn"

file mkdir $REPORTS

# In-memory project -- no .xpr written to disk, just an ephemeral project so
# the standard synth_design / report_* commands are available.
create_project -in_memory -part $PART

puts "=== SYNTH: reading sources ==="
read_verilog -library xil_defaultlib [list \
    "$CORE/MM_ultra.v" \
    "$CORE/MM_in_buffer.v" \
    "$CORE/MM_buffer.v" \
    "$CORE/MM_out_buffer.v" \
    "$CORE/MM.v" \
    "$CORE/PE_array.v" \
    "$CORE/PE_line.v" \
    "$CORE/PE.v" \
    "$CORE/AdderS.v" \
    "$CORE/right_shifter.v" \
    "$CORE/Softmax_control.v" \
    "$CORE/Softmax.v" \
    "$CORE/Exp_module.v" \
    "$CORE/Ln_module.v" \
    "$CORE/EightGelus.v" \
    "$CORE/gelu.v" \
    "$CORE/lin.v" \
    "$TOPDIR/axis_downsizer.v" \
    "$TOPDIR/axis_upsizer_fifo.v" \
    "$TOPDIR/transformer_block_top.v" \
]

# -mode out_of_context: this block has no board-level I/O of its own (no
# XDC pin assignments) and is meant to be instantiated inside a larger
# system, not synthesized as if it were a standalone top-level bitstream
# target. OOC mode avoids Vivado inserting artificial top-level IBUF/OBUF
# pairs that would skew the utilization numbers below.
puts "=== SYNTH: running synth_design (top=$TOP_MODULE, part=$PART, mode=out_of_context) ==="
synth_design -top $TOP_MODULE -part $PART -mode out_of_context

# Applied after synth_design (standard for OOC blocks): just enough of a
# clock definition for report_timing_summary to be meaningful, not meant to
# drive timing-optimized synthesis decisions the way a full top-level XDC
# would.
create_clock -name clk -period $CLK_PERIOD_NS [get_ports clk]

puts "=== SYNTH: generating reports into $REPORTS ==="
report_utilization    -file "$REPORTS/utilization.rpt"
report_timing_summary -file "$REPORTS/timing_summary.rpt"
report_drc            -file "$REPORTS/drc.rpt"

puts "=== SYNTH: DONE ==="
