`timescale 1ns / 1ns

// ===========================================================================
// transformer_block_tb.sv
//
// Top-level SYSTEM INTEGRATION testbench: drives transformer_block_top.v
// (MM_ultra -> Softmax_control -> EightGelus, chained via the adapters in
// sourcecode/top/) with one feature/weight tensor pair, and checks the
// final GELU output against a real-valued software reference that chains
// the same three golden models already used individually in
// MM_Ultra_tb.sv, Softmax_top_tb.sv and gelu_tb.sv.
//
// This is intentionally a SMALL configuration (see the `define block
// below): 4 matmul rows x 32 columns. The goal here is to exercise the
// pipeline's structural wiring, handshake correctness, and the adapters'
// framing (row-boundary 'last' generation, width conversion, the
// Softmax->GELU elastic FIFO) -- not to be a performance benchmark, and
// deliberately not sized anywhere near MM_Ultra_tb.sv's heavier
// standalone matmul config. Scale it up only after this passes and the
// team has decided how to run larger sims safely (batch queue, not the
// interactive login node).
// ===========================================================================

`define A_size 16
`define DATA_WIDTH 8
`define SHIFT_WIDTH 10
// NOTE: these *_Block_num values must be given real headroom ABOVE the
// actual number of beats used by IN_ROWS_NUM/IN_COLS_NUM/OUT_COLS_NUM
// below, not just sized to exactly match. MM_in_buffer.v sizes its
// internal threshold registers (e.g. W_block_size) as
// clogb2(Weight_Block_num) bits, but that threshold needs to be able to
// hold the value Weight_Block_num_actually_used_beats itself (a strict
// `in_W_cnt < W_block_size` gate), not just address up to that count
// minus one. Sizing a *_Block_num parameter to exactly the beat count
// needed (e.g. 64 when 64 beats are used) makes that threshold overflow
// and wrap to 0, permanently blocking that stream's `ready` -- see the
// project notes for how this was root-caused (a $monitor trace on
// MM_ultra.v's W_width_block_num capture chain showed the exact
// wrap-to-zero). Keep several multiples of headroom, matching how
// MM_Ultra_tb.sv itself uses e.g. Weight_Block_num=2400 against ~960
// actual beats needed.
`define IN_Feature_Block_num 2400
`define Weight_Block_num 2400
`define OUT_Feature_Block_num 2400
`define OUT_MEM_WIDTH 21
`define F_length_width 10
`define F_width_block_num_width 5
`define W_width_block_num_width 5

`define IN_ROWS_NUM 200   // matmul rows (F_length) == number of independent softmax groups
`define IN_COLS_NUM 96    // matmul contraction dim; must be a multiple of `A_size
`define OUT_COLS_NUM 160  // matmul output row width; becomes the softmax 'length' automatically
`define NUM_GELU 4       // GELU lanes; `OUT_COLS_NUM must be a multiple of this in this simple tb
                          // (the adapters support a partial final beat via 'keep', just not exercised here)

module transformer_block_tb;

parameter integer P_shift             = 9;
parameter integer P_F_length          = `IN_ROWS_NUM;
parameter integer P_F_width_block_num = `IN_COLS_NUM / `A_size;
parameter integer P_W_width_block_num = `OUT_COLS_NUM / `A_size;

// P_softmax_scale_out and P_gelu_scale MUST be equal for the pipeline to
// be numerically meaningful. Both ports are 4 bits wide (valid range
// 7-12 per Softmax_control's header), so any value in that range works
// here -- pinned to 7 for now since that's what's been validated.
parameter integer P_softmax_scale_in  = 6;  // interpretation of MM's int8 output; a system-level calibration choice
parameter integer P_softmax_scale_out = 7;
parameter integer P_gelu_scale        = 7;

reg clk;
reg rst_n;

reg  [`SHIFT_WIDTH-1:0]              mm_shift_in;
reg  [`F_length_width-1:0]           mm_F_length_in;
reg  [`F_width_block_num_width-1:0]  mm_F_width_block_num_in;
reg  [`W_width_block_num_width-1:0]  mm_W_width_block_num_in;

reg                                  mm_in_F_valid;
wire                                 mm_in_F_last;
wire                                 mm_in_F_ready;
wire [`A_size*`DATA_WIDTH-1:0]       mm_in_F_data;

reg                                  mm_in_W_valid;
wire                                 mm_in_W_last;
wire                                 mm_in_W_ready;
wire [`A_size*`DATA_WIDTH-1:0]       mm_in_W_data;

reg  signed [4:0]                    softmax_scale_in;
reg  [3:0]                           softmax_scale_out;
reg  [3:0]                           gelu_scale;

wire                                 out_valid;
// EightGelus.v has no real internal backpressure support (see
// transformer_block_top.v header note) -- anything already in flight
// keeps shifting even if 'ready' drops, so a beat is silently lost the
// cycle 'ready' is low while 'valid' is high. Hold the final consumer's
// ready high at all times so the golden-model comparison below stays
// valid; this is a workaround for a real RTL limitation, not a design
// choice this testbench is making by preference.
wire                                 out_ready = 1'b1;
wire                                 out_last;
wire [`NUM_GELU*`DATA_WIDTH-1:0]     out_data;
wire [`NUM_GELU-1:0]                 out_keep;

wire                                 fifo_overflow;

genvar gi, gj;

transformer_block_top #(
    .A_size(`A_size),
    .data_width(`DATA_WIDTH),
    .shift_width(`SHIFT_WIDTH),
    .Weight_Block_num(`Weight_Block_num),
    .IN_Feature_Block_num(`IN_Feature_Block_num),
    .OUT_Feature_Block_num(`OUT_Feature_Block_num),
    .OUT_MEM_WIDTH(`OUT_MEM_WIDTH),
    .F_length_width(`F_length_width),
    .F_width_block_num_width(`F_width_block_num_width),
    .W_width_block_num_width(`W_width_block_num_width),
    .num_gelu(`NUM_GELU),
    .GELU_FIFO_DEPTH(512)
) u_transformer_block_top (
    .clk(clk),
    .rst_n(rst_n),

    .mm_shift_in(mm_shift_in),
    .mm_F_length_in(mm_F_length_in),
    .mm_F_width_block_num_in(mm_F_width_block_num_in),
    .mm_W_width_block_num_in(mm_W_width_block_num_in),

    .mm_in_F_valid(mm_in_F_valid),
    .mm_in_F_last(mm_in_F_last),
    .mm_in_F_ready(mm_in_F_ready),
    .mm_in_F_data(mm_in_F_data),

    .mm_in_W_valid(mm_in_W_valid),
    .mm_in_W_last(mm_in_W_last),
    .mm_in_W_ready(mm_in_W_ready),
    .mm_in_W_data(mm_in_W_data),

    .softmax_scale_in(softmax_scale_in),
    .softmax_scale_out(softmax_scale_out),
    .gelu_scale(gelu_scale),

    .out_valid(out_valid),
    .out_ready(out_ready),
    .out_last(out_last),
    .out_data(out_data),
    .out_keep(out_keep),

    .softmax_to_gelu_fifo_overflow(fifo_overflow)
);

// ---------------------------------------------------------------------
// Stall monitors at the pipeline's external boundaries. mm_in_F/mm_in_W
// see real backpressure (the downsizer deasserts mm's out_data_ready
// while draining each beat -- see axis_downsizer.v), so those numbers
// are meaningful. pipe_out is trivially 0% stalled by construction (see
// the out_ready note above) -- that 0% is expected, not a sign nothing
// was exercised upstream.
// ---------------------------------------------------------------------
stall_monitor #(.NAME("mm_in_F"))  u_stall_mm_in_F  (.clk(clk), .rst_n(rst_n), .enable(1'b1), .valid(mm_in_F_valid), .ready(mm_in_F_ready));
stall_monitor #(.NAME("mm_in_W"))  u_stall_mm_in_W  (.clk(clk), .rst_n(rst_n), .enable(1'b1), .valid(mm_in_W_valid), .ready(mm_in_W_ready));
stall_monitor #(.NAME("pipe_out")) u_stall_pipe_out (.clk(clk), .rst_n(rst_n), .enable(1'b1), .valid(out_valid),    .ready(out_ready));

always @(posedge clk) begin
    if (rst_n && fifo_overflow)
        $display("%0t: TB ERROR: softmax->gelu FIFO overflow observed -- increase GELU_FIFO_DEPTH or check backpressure.", $time);
end


// ---------------------------------------------------------------------
// End-to-end latency: mm_in_F_valid first asserted -> final out_last
// ---------------------------------------------------------------------
integer pipe_latency_cycles;
reg     pipe_latency_running;
reg     pipe_started;

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        pipe_latency_cycles  <= 0;
        pipe_latency_running <= 0;
        pipe_started         <= 0;
    end
    else begin
        if (!pipe_started && mm_in_F_valid) begin
            pipe_started         <= 1;
            pipe_latency_running <= 1;
            pipe_latency_cycles  <= 0;
        end
        else if (pipe_latency_running) begin
            pipe_latency_cycles <= pipe_latency_cycles + 1;
            if (out_valid && out_ready && out_last)
                pipe_latency_running <= 0;
        end
    end
end

// ---------------------------------------------------------------------
// Tensor generation: feature matrix x[IN_ROWS_NUM][IN_COLS_NUM] and
// weight matrix y[IN_COLS_NUM][OUT_COLS_NUM] -- same streaming mechanics
// as MM_Ultra_tb.sv.
// ---------------------------------------------------------------------
integer x[`IN_ROWS_NUM-1:0][`IN_COLS_NUM-1:0];
integer y[`IN_COLS_NUM-1:0][`OUT_COLS_NUM-1:0];
integer x_flatten[`IN_ROWS_NUM * `IN_COLS_NUM - 1:0];
integer y_flatten[`IN_COLS_NUM * `OUT_COLS_NUM - 1:0];

initial begin
    automatic integer i, j, temp;
    for (i=0;i<`IN_ROWS_NUM;i=i+1) begin
        for (j=0;j<`IN_COLS_NUM;j=j+1) begin
            temp = $random % 128;
            if (temp > 127) temp = 127;
            if (temp < -128) temp = -128;
            x[i][j] = temp;
            x_flatten[i*`IN_COLS_NUM+j] = temp;
        end
    end
    for (i=0;i<`IN_COLS_NUM;i=i+1) begin
        for (j=0;j<`OUT_COLS_NUM;j=j+1) begin
            temp = $random % 128;
            if (temp > 127) temp = 127;
            if (temp < -128) temp = -128;
            y[i][j] = temp;
            y_flatten[i*`OUT_COLS_NUM+j] = temp;
        end
    end
end

// x_in_array/y_in_array used to be materialized as one wire per word, driven
// by a generate loop that unrolled one assign per scalar element (rows*cols
// of them). Only one word is ever read per cycle (indexed by in_F_addr/
// in_W_addr), so pack it on demand instead -- same fix as MM_Ultra_tb.sv,
// which is what let that testbench run at full scale without blowing up
// Xcelium's elaboration memory.
function automatic [`A_size*`DATA_WIDTH-1:0] pack_x_word(input integer word_idx);
    integer k;
    begin
        for (k = 0; k < `A_size; k = k + 1)
            pack_x_word[k*`DATA_WIDTH +: `DATA_WIDTH] = x_flatten[word_idx*`A_size + k];
    end
endfunction

function automatic [`A_size*`DATA_WIDTH-1:0] pack_y_word(input integer word_idx);
    integer k;
    begin
        for (k = 0; k < `A_size; k = k + 1)
            pack_y_word[k*`DATA_WIDTH +: `DATA_WIDTH] = y_flatten[word_idx*`A_size + k];
    end
endfunction

reg start_trans;
initial start_trans = 0;

reg [31:0] in_F_addr;
initial in_F_addr = 0;
always @(posedge clk) begin
    if (mm_in_F_last) in_F_addr <= 0;
    else if (mm_in_F_valid) in_F_addr <= in_F_addr + 1;
end
assign mm_in_F_data = pack_x_word(in_F_addr);
assign mm_in_F_last = (in_F_addr == `IN_ROWS_NUM * P_F_width_block_num - 1) ? 1'b1 : 1'b0;

always @(posedge clk) begin
    if (~rst_n) mm_in_F_valid <= 1'b0;
    else if (start_trans) mm_in_F_valid <= 1'b1;
    else if (mm_in_F_last) mm_in_F_valid <= 1'b0;
end

reg [31:0] in_W_addr;
initial in_W_addr = 0;
always @(posedge clk) begin
    if (mm_in_W_last) in_W_addr <= 0;
    else if (mm_in_W_valid) in_W_addr <= in_W_addr + 1;
end
assign mm_in_W_data = pack_y_word(in_W_addr);
assign mm_in_W_last = (in_W_addr == `IN_COLS_NUM * P_W_width_block_num - 1) ? 1'b1 : 1'b0;

always @(posedge clk) begin
    if (~rst_n) mm_in_W_valid <= 1'b0;
    else if (start_trans) mm_in_W_valid <= 1'b1;
    else if (mm_in_W_last) mm_in_W_valid <= 1'b0;
end

// ---------------------------------------------------------------------
// Output capture: unpack the num_gelu-wide beats back into a flat
// per-row/per-col array using out_keep + out_last for framing.
// ---------------------------------------------------------------------
reg signed [`DATA_WIDTH-1:0] gelu_hw_flat [`IN_ROWS_NUM * `OUT_COLS_NUM - 1:0];
integer out_row, out_col_beat;
integer cap_k;

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        out_row      <= 0;
        out_col_beat <= 0;
    end
    else if (out_valid && out_ready) begin
        for (cap_k=0; cap_k<`NUM_GELU; cap_k=cap_k+1) begin
            if (out_keep[cap_k])
                gelu_hw_flat[out_row*`OUT_COLS_NUM + out_col_beat*`NUM_GELU + cap_k] <= $signed(out_data[cap_k*`DATA_WIDTH +: `DATA_WIDTH]);
        end
        if (out_last) begin
            out_row      <= out_row + 1;
            out_col_beat <= 0;
        end
        else begin
            out_col_beat <= out_col_beat + 1;
        end
    end
end

initial clk = 0;
always #5 clk = ~clk;

// ---------------------------------------------------------------------
// Software golden model: matmul (MM_soft, same math as MM_Ultra_tb) ->
// per-row softmax (Softmax_task, same math as Softmax_top_tb) ->
// per-element real-valued GELU (gelu_ref, same math as gelu_tb) --
// chained row by row.
// ---------------------------------------------------------------------
task MM_soft(input  integer mx[`IN_ROWS_NUM-1:0][`IN_COLS_NUM-1:0],
             input  integer my[`IN_COLS_NUM-1:0][`OUT_COLS_NUM-1:0],
             input  integer scale,
             output integer mz[`IN_ROWS_NUM-1:0][`OUT_COLS_NUM-1:0]);
    begin
        automatic integer i, j, kk, temp;
        for (i=0;i<`IN_ROWS_NUM;i=i+1) begin
            for (j=0;j<`OUT_COLS_NUM;j=j+1) begin
                temp = 0;
                for (kk=0;kk<`IN_COLS_NUM;kk=kk+1)
                    temp = temp + mx[i][kk]*my[kk][j];
                if (scale > 0)
                    temp = (temp + (1<<(scale-1))) >>> scale;
                if (temp > 127) temp = 127;
                if (temp < -128) temp = -128;
                mz[i][j] = temp;
            end
        end
    end
endtask

task Softmax_task(input real sx[`OUT_COLS_NUM-1:0], output real sy[`OUT_COLS_NUM-1:0]);
    begin
        automatic integer scnt;
        automatic real smax = 0;
        automatic real esum = 0;
        automatic real sexp[`OUT_COLS_NUM];
        for (scnt=0; scnt<`OUT_COLS_NUM; scnt=scnt+1)
            if (sx[scnt] > smax) smax = sx[scnt];
        for (scnt=0; scnt<`OUT_COLS_NUM; scnt=scnt+1) begin
            sexp[scnt] = $exp(sx[scnt]-smax);
            esum = esum + sexp[scnt];
        end
        for (scnt=0; scnt<`OUT_COLS_NUM; scnt=scnt+1)
            sy[scnt] = sexp[scnt]/esum;
    end
endtask

function automatic real gelu_ref(input real gx);
    automatic real tanh_i, tanh_o, c1, c2;
    begin
        c1 = $sqrt(2.0/3.1415926535897932);
        c2 = 0.044715;
        tanh_i = c1 * (gx + c2*gx*gx*gx);
        tanh_o = $tanh(tanh_i);
        gelu_ref = 0.5 * gx * (1.0 + tanh_o);
    end
endfunction

integer z_soft[`IN_ROWS_NUM-1:0][`OUT_COLS_NUM-1:0];
real    gelu_soft[`IN_ROWS_NUM-1:0][`OUT_COLS_NUM-1:0];

initial begin
    automatic integer r, c;
    automatic real row_real[`OUT_COLS_NUM-1:0];
    automatic real row_soft[`OUT_COLS_NUM-1:0];

    mm_shift_in             = 0;
    mm_F_length_in          = 0;
    mm_F_width_block_num_in = 0;
    mm_W_width_block_num_in = 0;
    softmax_scale_in        = 0;
    softmax_scale_out       = 0;
    gelu_scale               = 0;

    rst_n = 0;
    #50 rst_n = 1;
    #50;
    #1000;

    mm_shift_in             = P_shift;
    mm_F_length_in          = P_F_length;
    mm_F_width_block_num_in = P_F_width_block_num;
    mm_W_width_block_num_in = P_W_width_block_num;
    softmax_scale_in        = P_softmax_scale_in;
    softmax_scale_out       = P_softmax_scale_out;
    gelu_scale               = P_gelu_scale;

    // Build the reference: matmul, then per-row softmax + gelu.
    MM_soft(x, y, P_shift, z_soft);
    for (r=0; r<`IN_ROWS_NUM; r=r+1) begin
        for (c=0; c<`OUT_COLS_NUM; c=c+1)
            row_real[c] = $itor(z_soft[r][c]) * $pow(2.0, -$itor(P_softmax_scale_in));
        Softmax_task(row_real, row_soft);
        for (c=0; c<`OUT_COLS_NUM; c=c+1)
            gelu_soft[r][c] = gelu_ref(row_soft[c]);
    end

    #1000 start_trans = 1;
    #10  start_trans = 0;
end

// ---------------------------------------------------------------------
// Final check: once the last row's last beat has been captured, compare
// gelu_hw_flat (converted back to real via P_gelu_scale) against
// gelu_soft. Tolerance is intentionally looser than the single-stage
// unit tests, because errors compound across two quantization stages
// (Softmax's int8 output, then GELU's int8 output).
// ---------------------------------------------------------------------
real    tol;
integer errors;
integer fr, fc;
real    hw_val, sw_val, diff;

always @(posedge clk) begin
    if (out_valid && out_ready && out_last && (out_row == `IN_ROWS_NUM - 1)) begin
        #(20 * `OUT_COLS_NUM); // let the last beat's capture write settle

        tol    = 6.0 * $pow(2.0, -$itor(P_gelu_scale)); // ~6 LSBs at the shared softmax_out/gelu scale
        errors = 0;
        for (fr=0; fr<`IN_ROWS_NUM; fr=fr+1) begin
            for (fc=0; fc<`OUT_COLS_NUM; fc=fc+1) begin
                hw_val = $itor(gelu_hw_flat[fr*`OUT_COLS_NUM+fc]) * $pow(2.0, -$itor(P_gelu_scale));
                sw_val = gelu_soft[fr][fc];
                diff   = hw_val - sw_val;
                if (diff > tol || diff < -tol) begin
                    errors = errors + 1;
                    $display("row=%0d col=%0d hw=%6.4f sw=%6.4f diff=%6.4f", fr, fc, hw_val, sw_val, diff);
                end
            end
        end

        $display("---------------------------------------------------------");
        $display("transformer_block_tb: %0d / %0d elements outside tolerance (+/-%.4f)",
                  errors, `IN_ROWS_NUM*`OUT_COLS_NUM, tol);
        $display("End-to-end pipeline latency (mm_in_F_valid -> final out_last): %0d cycles (%0d ns)",
                  pipe_latency_cycles, pipe_latency_cycles*10);
        u_stall_mm_in_F.report();
        u_stall_mm_in_W.report();
        u_stall_pipe_out.report();
        $display("---------------------------------------------------------");
        $finish();
    end
end

endmodule
