# ===========================================================================
# Xcelium automation for the transformer-accelerator testbenches.
#
# IMPORTANT -- this project's interactive login node is shared. Running
# `xrun` directly at this shell for anything heavier than gelu_tb/
# Softmax_top_tb has previously overloaded the shared machine. Prefer
# submitting these through the site's batch scheduler (PBS/qsub) rather
# than running `make run_mm`/`make run_transformer` directly here,
# especially the *_profile targets, which are heavier still.
#
# Usage:
#   make run_gelu            # gelu_tb: compile + elaborate + run
#   make run_softmax
#   make run_mm
#   make run_transformer
#   make run_all             # all four, sequentially
#
#   make waves_gelu          # same, but dump a full-design SHM waveform
#                             # (open with: simvision run/gelu/waves.shm &)
#
#   make profile_gelu        # same, but with -profile + toggle coverage,
#                             # and wrapped in `/usr/bin/time -v` for peak
#                             # memory. See the *_profile targets below for
#                             # exactly what's captured and how to view it.
#
#   make clean                # remove all run/ output directories
#
# Every target compiles and runs in its own run/<name>/ subdirectory so
# outputs never collide or land in the source tree.
# ===========================================================================

XRUN         := xrun
SIMDIR       := $(CURDIR)
CORE         := $(SIMDIR)/../core
TB           := $(SIMDIR)/../tb
TOP          := $(SIMDIR)/../top
RUNROOT      := $(SIMDIR)/run

# -sv is required project-wide now: stall_monitor.sv (SV, used by
# MM_Ultra_tb.sv, Softmax_top_tb.sv and transformer_block_tb.sv) and
# several core .v files rely on SystemVerilog constructs (automatic
# variables, $pow()/$clog2() in constant expressions, etc).
COMMON_FLAGS := -access +rwc -sv -timescale 1ns/1ps

# -profile        : Xcelium performance/time profiler (function & instance
#                    level). Produces a profile database in the run dir;
#                    open with the Indago/SimVision profiler GUI, e.g.
#                    `indago -db xcelium.d` from inside that run dir, or
#                    `simprofile view` if that's available on this
#                    install -- check `xrun -profile -help` / local docs,
#                    the exact viewer invocation has moved between
#                    Xcelium releases.
# -coverage t      : toggle coverage only (activity per net), scoped to
#                    just what was asked for rather than turning on the
#                    full functional-coverage suite (line/branch/fsm/...).
# -covoverwrite    : re-running a profile target overwrites its previous
#                    coverage database instead of merging into it.
# -covtest <name>  : names this run's coverage test, so `imc` can load it
#                    (`imc -load cov_work/scope/<name>` from the run dir).
PROFILE_FLAGS := -profile
COVERAGE_FLAGS = -coverage t -covoverwrite -covtest $(1)

# Peak memory (RSS) and wall-clock time for the simulator process itself.
# This is a plain OS-level measurement, not an Xcelium feature -- Xcelium
# has no dedicated "simulation memory efficiency" flag as of this
# install, so `/usr/bin/time -v` is the honest way to get that number.
TIME_WRAP := /usr/bin/time -v

GELU_FILES = \
	$(CORE)/gelu.v \
	$(CORE)/lin.v \
	$(TB)/gelu_tb.sv

SOFTMAX_FILES = \
	$(CORE)/Softmax_control.v \
	$(CORE)/Softmax.v \
	$(CORE)/Exp_module.v \
	$(CORE)/Ln_module.v \
	$(TB)/stall_monitor.sv \
	$(TB)/Softmax_top_tb.sv

MM_FILES = \
	$(CORE)/MM_ultra.v \
	$(CORE)/MM_in_buffer.v \
	$(CORE)/MM_buffer.v \
	$(CORE)/MM_out_buffer.v \
	$(CORE)/MM.v \
	$(CORE)/PE_array.v \
	$(CORE)/PE_line.v \
	$(CORE)/PE.v \
	$(CORE)/AdderS.v \
	$(CORE)/right_shifter.v \
	$(TB)/stall_monitor.sv \
	$(TB)/MM_Ultra_tb.sv

TRANSFORMER_FILES = \
	$(CORE)/MM_ultra.v \
	$(CORE)/MM_in_buffer.v \
	$(CORE)/MM_buffer.v \
	$(CORE)/MM_out_buffer.v \
	$(CORE)/MM.v \
	$(CORE)/PE_array.v \
	$(CORE)/PE_line.v \
	$(CORE)/PE.v \
	$(CORE)/AdderS.v \
	$(CORE)/right_shifter.v \
	$(CORE)/Softmax_control.v \
	$(CORE)/Softmax.v \
	$(CORE)/Exp_module.v \
	$(CORE)/Ln_module.v \
	$(CORE)/EightGelus.v \
	$(CORE)/gelu.v \
	$(CORE)/lin.v \
	$(TB)/stall_monitor.sv \
	$(TOP)/axis_downsizer.v \
	$(TOP)/axis_upsizer_fifo.v \
	$(TOP)/transformer_block_top.v \
	$(TB)/transformer_block_tb.sv

.PHONY: run_all run_gelu run_softmax run_mm run_transformer \
        waves_gelu waves_softmax waves_mm waves_transformer \
        profile_gelu profile_softmax profile_mm profile_transformer \
        clean help

help:
	@echo "Targets: run_gelu run_softmax run_mm run_transformer run_all"
	@echo "         waves_gelu waves_softmax waves_mm waves_transformer"
	@echo "         profile_gelu profile_softmax profile_mm profile_transformer"
	@echo "         clean"

run_all: run_gelu run_softmax run_mm run_transformer

# ---- plain compile + elaborate + run -------------------------------------
run_gelu:
	mkdir -p $(RUNROOT)/gelu
	cd $(RUNROOT)/gelu && $(XRUN) $(COMMON_FLAGS) $(GELU_FILES) -top gelu_tb

run_softmax:
	mkdir -p $(RUNROOT)/softmax
	cd $(RUNROOT)/softmax && $(XRUN) $(COMMON_FLAGS) $(SOFTMAX_FILES) -top Softmax_top_tb

run_mm:
	mkdir -p $(RUNROOT)/mm
	cd $(RUNROOT)/mm && $(XRUN) $(COMMON_FLAGS) $(MM_FILES) -top MM_Ultra_tb

run_transformer:
	mkdir -p $(RUNROOT)/transformer
	cd $(RUNROOT)/transformer && $(XRUN) $(COMMON_FLAGS) $(TRANSFORMER_FILES) -top transformer_block_tb

# ---- same, but with a full-design waveform dump ---------------------------
waves_gelu:
	mkdir -p $(RUNROOT)/gelu_waves
	cp $(SIMDIR)/waves.tcl $(RUNROOT)/gelu_waves/
	cd $(RUNROOT)/gelu_waves && $(XRUN) $(COMMON_FLAGS) $(GELU_FILES) -top gelu_tb -input waves.tcl

waves_softmax:
	mkdir -p $(RUNROOT)/softmax_waves
	cp $(SIMDIR)/waves.tcl $(RUNROOT)/softmax_waves/
	cd $(RUNROOT)/softmax_waves && $(XRUN) $(COMMON_FLAGS) $(SOFTMAX_FILES) -top Softmax_top_tb -input waves.tcl

waves_mm:
	mkdir -p $(RUNROOT)/mm_waves
	cp $(SIMDIR)/waves.tcl $(RUNROOT)/mm_waves/
	cd $(RUNROOT)/mm_waves && $(XRUN) $(COMMON_FLAGS) $(MM_FILES) -top MM_Ultra_tb -input waves.tcl

waves_transformer:
	mkdir -p $(RUNROOT)/transformer_waves
	cp $(SIMDIR)/waves.tcl $(RUNROOT)/transformer_waves/
	cd $(RUNROOT)/transformer_waves && $(XRUN) $(COMMON_FLAGS) $(TRANSFORMER_FILES) -top transformer_block_tb -input waves.tcl

# ---- same, but with -profile + toggle coverage + peak-memory capture -----
# These are the heaviest targets (profiling/coverage instrumentation adds
# real overhead on top of the simulation itself) -- run via the batch
# queue, not directly on the interactive node, per the note at the top of
# this file.
profile_gelu:
	mkdir -p $(RUNROOT)/gelu_profile
	cd $(RUNROOT)/gelu_profile && $(TIME_WRAP) $(XRUN) $(COMMON_FLAGS) $(PROFILE_FLAGS) $(call COVERAGE_FLAGS,gelu_tb) $(GELU_FILES) -top gelu_tb

profile_softmax:
	mkdir -p $(RUNROOT)/softmax_profile
	cd $(RUNROOT)/softmax_profile && $(TIME_WRAP) $(XRUN) $(COMMON_FLAGS) $(PROFILE_FLAGS) $(call COVERAGE_FLAGS,softmax_tb) $(SOFTMAX_FILES) -top Softmax_top_tb

profile_mm:
	mkdir -p $(RUNROOT)/mm_profile
	cd $(RUNROOT)/mm_profile && $(TIME_WRAP) $(XRUN) $(COMMON_FLAGS) $(PROFILE_FLAGS) $(call COVERAGE_FLAGS,mm_ultra_tb) $(MM_FILES) -top MM_Ultra_tb

profile_transformer:
	mkdir -p $(RUNROOT)/transformer_profile
	cd $(RUNROOT)/transformer_profile && $(TIME_WRAP) $(XRUN) $(COMMON_FLAGS) $(PROFILE_FLAGS) $(call COVERAGE_FLAGS,transformer_block_tb) $(TRANSFORMER_FILES) -top transformer_block_tb

clean:
	rm -rf $(RUNROOT)
