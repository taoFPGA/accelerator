# Xcelium simcontrol script: dump every signal in the design to a SHM
# waveform database and run to completion.
#
# Usage: xrun ... -input waves.tcl
# View:  simvision waves.shm &
database -open waves -shm -default
probe -create / -all -depth all -database waves
run
exit
