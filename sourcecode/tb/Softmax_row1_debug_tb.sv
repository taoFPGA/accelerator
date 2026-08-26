`timescale 1ns / 1ps

// ===========================================================================
// Softmax_row1_debug_tb.sv
//
// Standalone Softmax_control debug testbench. NOT part of the regular
// verification suite -- built specifically to root-cause a real hardware
// finding: the very first PYNQ-Z2 run of the full pipeline (see
// report/project_story.md's hardware bring-up section) showed 2 of 32
// elements in one row coming back as exactly 0 from real silicon, when the
// software golden model expected small-but-nonzero softmax probabilities.
//
// This feeds the EXACT 32 matmul-output values (z, i.e. MM_ultra's int8
// output before softmax) from that failing row -- IN_ROWS=8/IN_COLS=32/
// OUT_COLS=32, np.random.seed(0), shift=9, softmax_scale_in=6,
// softmax_scale_out=7 -- through Softmax_control ALONE, and $display-dumps
// every internal pipeline signal every cycle, tagged with the source
// column index, so the exact point of divergence from the expected math
// can be read directly off the log instead of inferred by hand.
//
// The two columns that failed on real hardware are col=10 (z=90, the
// row's rank-2 value) and col=19 (z=127, the row's UNIQUE max -- not a
// tie with any other column). Expected Softmax_control int8 outputs
// (scale_out=7, i.e. probability*128) for those two: col10 ~= 12,
// col19 ~= 22 -- both real hardware outputs came back as exactly 0.
//
// Run (from sourcecode/sim/): make run_softmax_row1_debug
// ===========================================================================

module Softmax_row1_debug_tb;

localparam LENGTH = 32;
localparam signed [4:0] SCALE_IN = 6;
localparam [3:0] SCALE_OUT = 7;

reg clk;
reg rst_n;

reg [9:0]        length;
reg signed [4:0] scale_in;
reg [3:0]        scale_out;

reg signed [7:0] x_hard [LENGTH-1:0];
reg signed [7:0] y_hard [LENGTH-1:0];

wire signed [7:0] top_data_in;
reg               top_valid_in;
wire              top_ready_in;
reg               top_last_in;

wire [7:0] top_data_out;
wire       top_valid_out;
wire       top_last_out;

Softmax_control u_Softmax_control (
    .clk(clk),
    .rst_n(rst_n),
    .length_input(length),
    .scale_in_input(scale_in),
    .scale_out_input(scale_out),

    .top_data_in(top_data_in),
    .top_valid_in(top_valid_in),
    .top_ready_in(top_ready_in),
    .top_last_in(top_last_in),

    .top_data_out(top_data_out),
    .top_valid_out(top_valid_out),
    .top_last_out(top_last_out)
);

reg [9:0] cnt;
assign top_data_in  = x_hard[cnt];
assign top_last_in  = (cnt == LENGTH - 1);

always @(posedge clk or negedge rst_n) begin
    if (~rst_n)
        cnt <= 0;
    else if (top_valid_in && top_ready_in) begin
        if (cnt == LENGTH - 1)
            cnt <= 0;
        else
            cnt <= cnt + 1;
    end
end

reg [9:0] y_cnt;
always @(posedge clk or negedge rst_n) begin
    if (~rst_n)
        y_cnt <= 0;
    else if (top_valid_out) begin
        y_hard[y_cnt] <= $signed(top_data_out);
        y_cnt <= (y_cnt == LENGTH - 1) ? 0 : y_cnt + 1;
    end
end

initial clk = 0;
always #5 clk = ~clk;

// ---------------------------------------------------------------------
// Full internal pipeline trace, every cycle, tagged with cnt_in/
// cnt_stage/out_addr so col10's and col19's exact processing cycles in
// every one of Softmax_control's 3 internal passes can be grep'd
// straight out of the log (search for "out_addr=10" / "out_addr=19").
// ---------------------------------------------------------------------
always @(posedge clk) begin
    if (rst_n)
        $display("t=%0t cnt_in=%0d cnt_stage=%0d out_addr=%0d data_in_max=%0d x_max_S9Q10=%0d e_sum_U8Q12=%0d ln_U3Q10=%0d x_max_ln_S9Q10=%0d exp1_U0Q25=%0d exp2_U0Q25_out=%0d valid_out=%0b data_out=%0d",
            $time,
            u_Softmax_control.cnt_in,
            u_Softmax_control.cnt_stage,
            u_Softmax_control.out_addr,
            u_Softmax_control.u_Softmax.data_in_max,
            u_Softmax_control.u_Softmax.x_max_S9Q10,
            u_Softmax_control.u_Softmax.e_sum_U8Q12,
            u_Softmax_control.u_Softmax.ln_U3Q10,
            u_Softmax_control.u_Softmax.x_max_ln_S9Q10,
            u_Softmax_control.u_Softmax.exp_U0Q25,
            u_Softmax_control.u_Softmax.exp_U0Q25_out,
            top_valid_out,
            $signed(top_data_out));
end

integer i;
initial begin
    rst_n        = 0;
    top_valid_in = 0;
    length       = LENGTH;
    scale_in     = SCALE_IN;
    scale_out    = SCALE_OUT;

    // Row 1's exact 32 MM_ultra output values from the first PYNQ-Z2
    // hardware run (np.random.seed(0), IN_ROWS=8/IN_COLS=32/OUT_COLS=32,
    // shift=9) -- reconstructed via golden_model.mm_soft() on the host,
    // not re-typed by hand from a printout.
    x_hard[0]  = -86;  x_hard[1]  = 53;   x_hard[2]  = -48;  x_hard[3]  = -82;
    x_hard[4]  = -4;   x_hard[5]  = 18;   x_hard[6]  = -109; x_hard[7]  = 20;
    x_hard[8]  = -74;  x_hard[9]  = -15;  x_hard[10] = 90;   x_hard[11] = -2;
    x_hard[12] = -8;   x_hard[13] = -1;   x_hard[14] = 0;    x_hard[15] = -25;
    x_hard[16] = -43;  x_hard[17] = 23;   x_hard[18] = -65;  x_hard[19] = 127;
    x_hard[20] = -26;  x_hard[21] = 36;   x_hard[22] = 16;   x_hard[23] = -50;
    x_hard[24] = 50;   x_hard[25] = 25;   x_hard[26] = -55;  x_hard[27] = -128;
    x_hard[28] = 46;   x_hard[29] = -16;  x_hard[30] = 69;   x_hard[31] = 60;

    #350 rst_n = 1;
    #50  top_valid_in = 1;

    // Same safe-margin idiom Softmax_top_tb.sv already uses: 5*length
    // cycles of slack (this core has no output-side ready/backpressure,
    // so there's no other completion signal to wait on).
    for (i = 0; i < 5 * LENGTH; i = i + 1)
        #100;

    $display("---------------------------------------------------------");
    for (i = 0; i < LENGTH; i = i + 1)
        $display("col=%0d x=%0d y_hard=%0d", i, x_hard[i], y_hard[i]);
    $display("---------------------------------------------------------");
    $display("col10 (expected ~12, real hardware returned 0): y_hard=%0d", y_hard[10]);
    $display("col19 (expected ~22, real hardware returned 0): y_hard=%0d", y_hard[19]);
    $display("---------------------------------------------------------");
    $finish();
end

endmodule
