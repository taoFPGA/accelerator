################################################################################
# taoFPGA -- Full SoC synthesis (Zynq PS7 + DMA + transformer accelerator)
#
# Builds the complete block design via scripts/prj.tcl (Zynq processing_system7,
# 3x AXI DMA, SmartConnect/interconnect, and transformer_block_axi_top -- the
# AXI-wrapped full MM_ultra -> Softmax_control -> EightGelus pipeline), wraps
# it in an HDL top-level, and synthesizes the whole thing as the real chip
# top (not out-of-context, unlike scripts/synth.tcl's standalone-block run --
# this one has actual DDR/FIXED_IO package I/O).
#
# Usage:
#   cd scripts && vivado -mode batch -source synth_soc.tcl
#
# Reports land in reports/syn/soc/ (utilization/timing/DRC for the full SoC,
# separate from reports/syn/'s standalone-accelerator baseline).
################################################################################

set PART "xc7z020clg400-1"

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file normalize "$SCRIPT_DIR/.."]
set CORE       "$REPO_ROOT/sourcecode/core"
set TOPDIR     "$REPO_ROOT/sourcecode/top"
set REPORTS    "$REPO_ROOT/reports/syn/soc"
set PROJ_DIR   "$REPO_ROOT/scripts/soc_build"

file mkdir $REPORTS

create_project project_1 "$PROJ_DIR/myproj" -part $PART -force

# Physical board is a PYNQ-Z2 (TUL), not the PYNQ-Z1 this flow was
# originally built against -- same xc7z020clg400-1 part, so this line is
# non-fatal either way (board_part is only I/O pin-constraint metadata and
# doesn't affect synthesis). See project_story.md for the full
# investigation, and prj.tcl's processing_system7_0 comment for why the
# DDR3/MIO CONFIG values still need a real board-preset re-apply (not just
# this board_part string) before trusting a bitstream on physical hardware.
if { [catch {set_property board_part tul.com.tw:pynq-z2:part0:1.0 [current_project]} err] } {
    puts "WARNING: could not set board_part (continuing without it): $err"
}

puts "=== SYNTH_SOC: reading sources ==="
add_files -norecurse [list \
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
    "$TOPDIR/transformer_block_axi.v" \
    "$TOPDIR/transformer_block_axi_top.v" \
]
update_compile_order -fileset sources_1

puts "=== SYNTH_SOC: building the block design via prj.tcl ==="
source "$REPO_ROOT/scripts/prj.tcl"

set bd_file [get_files "$PROJ_DIR/myproj/project_1.srcs/sources_1/bd/design_1/design_1.bd"]

puts "=== SYNTH_SOC: generating IP output products (PS7 clock constraints etc.) ==="
generate_target all $bd_file

puts "=== SYNTH_SOC: generating HDL wrapper for design_1 ==="
set wrapper_file [make_wrapper -files $bd_file -top]
add_files -norecurse $wrapper_file
update_compile_order -fileset sources_1
set_property top design_1_wrapper [current_fileset]
update_compile_order -fileset sources_1

puts "=== SYNTH_SOC: running synth_design (full chip top, not out-of-context) ==="
synth_design -top design_1_wrapper -part $PART

puts "=== SYNTH_SOC: generating reports into $REPORTS ==="
report_utilization    -file "$REPORTS/utilization.rpt"
report_timing_summary -file "$REPORTS/timing_summary.rpt"
report_drc            -file "$REPORTS/drc.rpt"

puts "=== SYNTH_SOC: DONE ==="
