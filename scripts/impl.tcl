################################################################################
# taoFPGA -- Post-synthesis physical implementation (full SoC)
#
# Regenerates the synthesized design via synth_soc.tcl, then runs the direct
# opt_design -> place_design -> route_design flow (default directives -- NOT
# prj.tcl's managed 'impl_1' run, which uses the more expensive "Explore"
# strategy meant for GUI project mode; default directives are far more
# memory/time-predictable on this resource-constrained VM).
#
# Usage:
#   cd scripts && vivado -mode batch -source impl.tcl
#
# Reports land in reports/impl/ (post-ROUTE utilization/timing/power/DRC --
# the first real, signoff-quality numbers in this project, vs. the
# post-synthesis-only estimates in reports/syn/soc/).
################################################################################

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file normalize "$SCRIPT_DIR/.."]

puts "=== IMPL: regenerating the synthesized design via synth_soc.tcl ==="
source "$SCRIPT_DIR/synth_soc.tcl"

# NOTE: synth_soc.tcl (sourced above) sets its OWN top-level 'REPORTS'
# variable (to reports/syn/soc) -- Tcl 'source' does not create a new scope,
# so reusing the name 'REPORTS' here would silently clobber it and send
# these post-route reports to the wrong directory. Use a distinct name,
# computed fresh after the source call.
set IMPL_REPORTS "$REPO_ROOT/reports/impl"
file mkdir $IMPL_REPORTS

puts "=== IMPL: opt_design ==="
opt_design

puts "=== IMPL: write post-opt checkpoint (recovery point) ==="
write_checkpoint -force "$REPO_ROOT/scripts/soc_build/post_opt.dcp"

puts "=== IMPL: place_design ==="
place_design

puts "=== IMPL: write post-place checkpoint (recovery point) ==="
write_checkpoint -force "$REPO_ROOT/scripts/soc_build/post_place.dcp"

puts "=== IMPL: route_design ==="
route_design

puts "=== IMPL: write post-route checkpoint (recovery point) ==="
write_checkpoint -force "$REPO_ROOT/scripts/soc_build/post_route.dcp"

puts "=== IMPL: generating post-route signoff reports into $IMPL_REPORTS ==="
report_utilization    -file "$IMPL_REPORTS/utilization.rpt"
report_timing_summary -file "$IMPL_REPORTS/timing_summary.rpt"
report_power           -file "$IMPL_REPORTS/power.rpt"
report_drc             -file "$IMPL_REPORTS/drc.rpt"

puts "=== IMPL: DONE ==="
