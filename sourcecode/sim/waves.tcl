# ===========================================================================
# waves.tcl -- SimVision waveform preset for transformer_block_tb
#
# Sourced by the `waves_*` targets in ./Makefile after elaboration
# (xrun ... -input waves.tcl) to auto-populate the SimVision wave window
# with the signals worth looking at when debugging the full pipeline:
#   * the two MatMul input streams (mm_in_F_* / mm_in_W_*) and the final
#     GELU output stream (out_*), with their valid/ready/last handshakes;
#   * Softmax_control's 3-pass state (cnt_stage + the length{1,2,3}_flag
#     pass-boundary flags);
#   * the testbench's own end-to-end latency counters
#     (pipe_latency_cycles / pipe_latency_running).
# Edit the list below to probe more signals; hierarchical paths are
# relative to the sim top (transformer_block_tb).
# ===========================================================================
waveform add -signals [list \
  transformer_block_tb.mm_in_F_valid \
  transformer_block_tb.mm_in_F_ready \
  transformer_block_tb.mm_in_F_data \
  transformer_block_tb.mm_in_F_last \
  transformer_block_tb.mm_in_W_valid \
  transformer_block_tb.mm_in_W_ready \
  transformer_block_tb.mm_in_W_last \
  transformer_block_tb.out_valid \
  transformer_block_tb.out_ready \
  transformer_block_tb.out_data \
  transformer_block_tb.out_last \
  transformer_block_tb.u_transformer_block_top.u_Softmax_control.cnt_stage \
  transformer_block_tb.u_transformer_block_top.u_Softmax_control.length1_flag \
  transformer_block_tb.u_transformer_block_top.u_Softmax_control.length2_flag \
  transformer_block_tb.u_transformer_block_top.u_Softmax_control.length3_flag \
  transformer_block_tb.pipe_latency_cycles \
  transformer_block_tb.pipe_latency_running \
]
