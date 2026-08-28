# Xcelium simcontrol script: dump every signal in the design to a SHM
# waveform database and run to completion.
#
# Usage: xrun ... -input waves.tcl
# View:  simvision waves.shm &
#
# NOTE: `probe -create /` (bare VHDL-hierarchy-separator root) fails on
# this all-Verilog/SystemVerilog design with "*E,PNOVHD: No VHDL root in
# design" -- Xcelium tries to resolve '/' as the VHDL design root, which
# doesn't exist here. Omitting the scope argument lets `probe` resolve
# the current (Verilog) top scope implicitly instead.
database -open waves -shm -default
probe -create -all -depth all -database waves
run
exit
