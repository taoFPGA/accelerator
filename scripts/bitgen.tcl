################################################################################
# taoFPGA -- Bitstream generation from the post-route, DSP-fixed checkpoint
#
# Reopens scripts/soc_build/post_route.dcp (written by scripts/impl.tcl's
# final DSP-fixed run -- WNS +0.293ns @ 100MHz, 205/220 DSP48E1, see
# report/synthesis_data.md Run 4) and generates the final bitstream plus a
# fixed hardware-platform handoff (.xsa, bitstream embedded) into exports/,
# matching the layout the README's build-flow diagram documents.
#
# No re-synthesis/re-place/re-route here -- reopening an already-routed
# checkpoint and writing outputs from it is deliberately cheap/low-risk
# compared to another full opt/place/route pass.
#
# Usage:
#   cd scripts && vivado -mode batch -source bitgen.tcl
################################################################################

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file normalize "$SCRIPT_DIR/.."]
set EXPORTS    "$REPO_ROOT/exports"
set DCP        "$REPO_ROOT/scripts/soc_build/post_route.dcp"

file mkdir $EXPORTS

puts "=== BITGEN: opening post-route checkpoint $DCP ==="
open_checkpoint $DCP

puts "=== BITGEN: write_bitstream ==="
write_bitstream -force "$EXPORTS/design.bit"

puts "=== BITGEN: write_hw_platform (fixed platform, bitstream embedded) ==="
write_hw_platform -fixed -force -include_bit -file "$EXPORTS/design.xsa"

puts "=== BITGEN: DONE ==="
