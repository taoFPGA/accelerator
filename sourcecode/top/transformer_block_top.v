`timescale 1ns / 1ps
// Structural integration blueprint: MatMul (MM_ultra) -> Softmax (Softmax_control)
// -> GELU (EightGelus), wired back-to-back into one streaming pipeline.
//
// Data flow, one tensor row at a time:
//   1. MM_ultra streams its result A_size scalars/cycle (a 128-bit beat for
//      the default A_size=16, data_width=8 config). Each output *row* of
//      the matmul (OUT_COLS_NUM = W_width_block_num_in * A_size scalars)
//      is spread across W_width_block_num_in beats.
//   2. A row-boundary counter here (NOT MM_ultra's own out_data_last --
//      see note below) turns "beat W_width_block_num_in-1 of a row" into
//      a per-row 'last' pulse.
//   3. axis_downsizer unpacks each wide beat into A_size sequential
//      scalar cycles, forwarding the per-row 'last' onto the row's final
//      scalar -- exactly the framing Softmax_control's top_last_in expects
//      (it normalizes one 'length'-element group per 'last' pulse).
//   4. Softmax_control consumes one scalar/cycle and produces one
//      normalized scalar/cycle on its output -- with NO backpressure
//      capability on that output (see axis_upsizer_fifo.v for why that
//      matters).
//   5. axis_upsizer_fifo buffers Softmax's unconditional output stream and
//      repacks it into num_gelu-wide beats (with 'keep' for a partial
//      final beat), presenting a normal valid/ready handshake.
//   6. EightGelus consumes num_gelu scalars/cycle and applies GELU
//      element-wise, 'num_gelu' lanes fully pipelined.
//
// IMPORTANT -- why out_data_last from MM_ultra is *not* used directly:
// MM_out_buffer (inside MM_ultra) defines out_data_last as
// 'out_data_cnt == F_length*W_width_block_num - 1', i.e. it only pulses
// once, at the very last beat of the *entire* matrix -- not at each row
// boundary. Softmax needs a 'last' every OUT_COLS_NUM scalars (once per
// row), so this module derives its own row-boundary signal instead. The
// final row's boundary and MM_ultra's whole-matrix out_data_last coincide
// automatically (the last row IS the last beat), so no information is
// lost by not using it directly.
//
// Known blueprint simplifications (call out explicitly rather than hide):
//   - axis_downsizer is single-buffered: mm stage backpressures (in_ready
//     deasserted) for the ~A_size cycles it takes to drain each beat, so
//     this pipeline is not full-throughput. See axis_downsizer.v.
//   - FIFO_DEPTH in the Softmax->GELU bridge must be sized >= the softmax
//     row length (OUT_COLS_NUM) actually used, or in_overflow will fire
//     and samples will be dropped -- there is no flow-control path back
//     to Softmax_control to prevent this, because none exists in the core.
//   - GELU's 'scale' and Softmax's 'scale_in'/'scale_out' are tied to
//     static top-level config inputs, matching how the existing unit
//     testbenches drive them (must be held constant through the run).
//   - REAL GAP, not worked around here: gelu_in must be told the same
//     fractional-bit scale Softmax used for its output (GELU's 'scale'
//     port and Softmax's 'scale_out_input' must carry the same value for
//     the pipeline to be numerically meaningful). But Softmax_control's
//     scale_out_input is 4 bits wide (its own header comment documents a
//     valid range of 7-12), while gelu.v/EightGelus's 'scale' port is
//     only 3 bits wide (max representable value 7). The two IPs as they
//     exist today therefore only agree at scale=7; Softmax's higher-
//     precision range (8-12) cannot be fed to GELU without widening
//     gelu.v's 'in_scale' port (a small RTL change outside this
//     blueprint's scope, flagged here rather than papered over).
//   - REAL FINDING in EightGelus.v: its internal valid/last shift
//     registers ('valid_reg', 'last_reg') advance unconditionally every
//     clock, regardless of 'out_ready' -- there is no internal skid
//     buffer. 'in_ready' is simply wired to 'out_ready'
//     (assign in_ready = out_ready;), which only protects data that
//     hasn't entered the pipe yet; anything already in flight keeps
//     shifting even while 'out_ready' is low, so a beat present on
//     'out_data'/'out_valid' the cycle 'out_ready' drops is silently
//     lost, not held. EightGelus is therefore not safe to place in front
//     of a consumer that applies real backpressure without a buffer
//     after it. The integration testbench works around this by holding
//     its final consumer's 'ready' high at all times; this is a real RTL
//     issue worth fixing in EightGelus.v itself, not something this
//     blueprint attempts to fix.
module transformer_block_top #(
    parameter integer A_size                = 16,
    parameter integer data_width             = 8,
    parameter integer shift_width            = 10,
    parameter integer Weight_Block_num       = 2400,
    parameter integer IN_Feature_Block_num   = 2400,
    parameter integer OUT_Feature_Block_num  = 2400,
    parameter integer OUT_MEM_WIDTH          = 21,
    parameter integer F_length_width         = 10,
    parameter integer F_width_block_num_width = 5,
    parameter integer W_width_block_num_width = 5,
    parameter integer num_gelu               = 4,
    parameter integer GELU_FIFO_DEPTH        = 512
)(
    input                                        clk,
    input                                        rst_n,

    // ---- MM stage: config + feature/weight input streams (see MM_ultra.v) ----
    input  [shift_width-1:0]                     mm_shift_in,
    input  [F_length_width-1:0]                  mm_F_length_in,
    input  [F_width_block_num_width-1:0]         mm_F_width_block_num_in,
    input  [W_width_block_num_width-1:0]         mm_W_width_block_num_in,

    input                                        mm_in_F_valid,
    input                                        mm_in_F_last,
    output                                       mm_in_F_ready,
    input  [A_size*data_width-1:0]               mm_in_F_data,

    input                                        mm_in_W_valid,
    input                                        mm_in_W_last,
    output                                       mm_in_W_ready,
    input  [A_size*data_width-1:0]               mm_in_W_data,

    // ---- Softmax stage config. length_input is derived internally
    //      (mm_W_width_block_num_in * A_size) so it can never disagree
    //      with the matmul's actual row width. ----
    input  signed [4:0]                          softmax_scale_in,
    input  [3:0]                                 softmax_scale_out,

    // ---- GELU stage config ----
    input  [2:0]                                 gelu_scale,

    // ---- Final pipeline output: num_gelu-wide AXI-stream ----
    output                                        out_valid,
    input                                          out_ready,
    output                                         out_last,
    output [num_gelu*data_width-1:0]               out_data,
    output [num_gelu-1:0]                          out_keep,

    // ---- Debug/visibility: see axis_upsizer_fifo.v ----
    output                                         softmax_to_gelu_fifo_overflow
);

// =======================================================================
// Stage 1: MM_ultra
// =======================================================================
wire                          mm_out_valid;
wire                          mm_out_ready;
wire                          mm_out_last;   // whole-matrix last (see header note)
wire [A_size*data_width-1:0]  mm_out_data;

MM_ultra #(
    .A_size(A_size),
    .data_width(data_width),
    .shift_width(shift_width),
    .Weight_Block_num(Weight_Block_num),
    .IN_Feature_Block_num(IN_Feature_Block_num),
    .OUT_Feature_Block_num(OUT_Feature_Block_num),
    .OUT_MEM_WIDTH(OUT_MEM_WIDTH),
    .F_length_width(F_length_width),
    .F_width_block_num_width(F_width_block_num_width),
    .W_width_block_num_width(W_width_block_num_width)
) u_MM_ultra (
    .clk(clk),
    .rst_n(rst_n),

    .shift_in(mm_shift_in),
    .F_length_in(mm_F_length_in),
    .F_width_block_num_in(mm_F_width_block_num_in),
    .W_width_block_num_in(mm_W_width_block_num_in),

    .in_F_valid(mm_in_F_valid),
    .in_F_last(mm_in_F_last),
    .in_F_ready(mm_in_F_ready),
    .in_F_data(mm_in_F_data),

    .in_W_valid(mm_in_W_valid),
    .in_W_last(mm_in_W_last),
    .in_W_ready(mm_in_W_ready),
    .in_W_data(mm_in_W_data),

    .out_data_valid(mm_out_valid),
    .out_data_ready(mm_out_ready),
    .out_data_last(mm_out_last),
    .out_data(mm_out_data)
);

// ---- row-boundary counter: turns "last beat of a row" into a 'last'
//      pulse aligned with mm_out_data, once every mm_W_width_block_num_in
//      beats (see header note on why mm_out_last isn't used here) ----
reg [W_width_block_num_width-1:0] row_beat_cnt;
wire                              mm_row_last = (row_beat_cnt == mm_W_width_block_num_in - 1'b1);

always @(posedge clk or negedge rst_n) begin
    if (~rst_n)
        row_beat_cnt <= {W_width_block_num_width{1'b0}};
    else if (mm_out_valid && mm_out_ready) begin
        if (mm_row_last)
            row_beat_cnt <= {W_width_block_num_width{1'b0}};
        else
            row_beat_cnt <= row_beat_cnt + 1'b1;
    end
end

wire [F_length_width+W_width_block_num_width-1:0] softmax_length_full = mm_W_width_block_num_in * A_size;
wire [9:0] softmax_length = softmax_length_full[9:0]; // Softmax_control.length_input is [9:0]

// =======================================================================
// Stage 1->2 bridge: wide MM beats -> serial Softmax scalars
// =======================================================================
wire                    sm_in_valid, sm_in_ready, sm_in_last;
wire [data_width-1:0]   sm_in_data;

axis_downsizer #(
    .LANES(A_size),
    .DATA_WIDTH(data_width)
) u_mm_to_softmax_downsizer (
    .clk(clk), .rst_n(rst_n),
    .in_valid(mm_out_valid), .in_ready(mm_out_ready), .in_last(mm_row_last), .in_data(mm_out_data),
    .out_valid(sm_in_valid), .out_ready(sm_in_ready), .out_last(sm_in_last), .out_data(sm_in_data)
);

// =======================================================================
// Stage 2: Softmax_control
// =======================================================================
wire                  sm_out_valid, sm_out_last;
wire [data_width-1:0] sm_out_data;

Softmax_control u_Softmax_control (
    .clk(clk),
    .rst_n(rst_n),

    .length_input(softmax_length),
    .scale_in_input(softmax_scale_in),
    .scale_out_input(softmax_scale_out),

    .top_data_in(sm_in_data),
    .top_valid_in(sm_in_valid),
    .top_ready_in(sm_in_ready),
    .top_last_in(sm_in_last),

    .top_data_out(sm_out_data),
    .top_valid_out(sm_out_valid),
    .top_last_out(sm_out_last)
);

// =======================================================================
// Stage 2->3 bridge: unconditional serial Softmax output -> num_gelu-wide
// buffered/handshaked GELU input (see axis_upsizer_fifo.v for why this
// needs a real FIFO and not just a shift register)
// =======================================================================
wire                              gelu_in_valid, gelu_in_ready, gelu_in_last;
wire [num_gelu*data_width-1:0]    gelu_in_data;
wire [num_gelu-1:0]               gelu_in_keep;

axis_upsizer_fifo #(
    .LANES(num_gelu),
    .DATA_WIDTH(data_width),
    .FIFO_DEPTH(GELU_FIFO_DEPTH)
) u_softmax_to_gelu_fifo (
    .clk(clk), .rst_n(rst_n),
    .in_valid(sm_out_valid), .in_last(sm_out_last), .in_data(sm_out_data), .in_overflow(softmax_to_gelu_fifo_overflow),
    .out_valid(gelu_in_valid), .out_ready(gelu_in_ready), .out_last(gelu_in_last), .out_data(gelu_in_data), .out_keep(gelu_in_keep)
);

// =======================================================================
// Stage 3: EightGelus
// =======================================================================
EightGelus #(
    .num_gelu(num_gelu)
) u_EightGelus (
    .clk(clk),
    .rst_n(rst_n),

    .in_data(gelu_in_data),
    .in_valid(gelu_in_valid),
    .in_ready(gelu_in_ready),
    .in_last(gelu_in_last),
    .in_keep(gelu_in_keep),

    .out_data(out_data),
    .out_valid(out_valid),
    .out_ready(out_ready),
    .out_last(out_last),
    .out_keep(out_keep),

    .scale(gelu_scale)
);

endmodule
