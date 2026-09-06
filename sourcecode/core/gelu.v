`timescale 1ns / 1ps
//latency=4+4
// ===========================================================================
// gelu.v -- one scalar int8 GELU lane   (latency = 8 clocks: 4 here + 4 in lin.v)
//
// Computes y = GELU(x) for a single int8 activation, matching the tanh
// approximation used by PyTorch's F.gelu(x, approximate='tanh') and by
// apps/golden_model.py's gelu_ref(). EightGelus.v instantiates `num_gelu` of
// these in parallel, one per output lane.
//
// `in_scale` (0..14) is the caller's Q-point for x: the block first
// re-scales x into an internal Q7 (x_in_8Q7) by shifting left/right by
// (7 - in_scale), does the math in fixed Q7, then shifts the result back by
// the same amount so y comes out in the caller's scale.
//
// Datapath:
//   * hard clamps first: if x < 0 and x <= -2.5  -> y = 0
//                        if x > 0 and x >=  2.5  -> y = x   (GELU ~ identity)
//   * otherwise  y = 0.5 * (L + 1) * x   where L = lin.v( (3/4)*x ), the
//     even quadratic tanh-shape kernel.
// The many *_regN ladders are just pipeline delays so x, in_scale and the
// intermediate products all arrive at the final mux on the same cycle.
// ===========================================================================
module gelu(
	input                           clk,
    input [3:0]                     in_scale,   // Q-point of x (fraction bits)
    input signed [7:0]              x,
    output reg signed [7:0]         y_reg1      // GELU(x), same scale as x
);
reg signed [7:0] x_reg1;
reg signed [7:0] x_reg2;
reg signed [7:0] x_reg3;
reg signed [7:0] x_reg4;
reg signed [7:0] x_reg5;
reg signed [7:0] x_reg6;
reg signed [7:0] x_reg7;

reg [3:0] in_scale_reg1;
reg [3:0] in_scale_reg2;
reg [3:0] in_scale_reg3;
reg [3:0] in_scale_reg4;
reg [3:0] in_scale_reg5;
reg [3:0] in_scale_reg6;
reg [3:0] in_scale_reg7;
always@(posedge clk)begin
	in_scale_reg1<=in_scale;
	in_scale_reg2<=in_scale_reg1;
	in_scale_reg3<=in_scale_reg2;
	in_scale_reg4<=in_scale_reg3;
	in_scale_reg5<=in_scale_reg4;
	in_scale_reg6<=in_scale_reg5;
	in_scale_reg7<=in_scale_reg6;
end
always@(posedge clk)begin
	x_reg1<=x;
	x_reg2<=x_reg1;
	x_reg3<=x_reg2;
	x_reg4<=x_reg3;
	x_reg5<=x_reg4;
	x_reg6<=x_reg5;
	x_reg7<=x_reg6;
end
reg signed [7:0]  y;
reg signed [15:0] x_in_8Q7;
reg signed [15:0] x_in_8Q7_reg1;
reg signed [15:0] x_in_8Q7_reg2;
reg signed [15:0] x_in_8Q7_reg3;
reg signed [15:0] x_in_8Q7_reg4;
reg signed [15:0] x_in_8Q7_reg5;
reg signed [15:0] x_in_8Q7_reg6;
reg signed [15:0] x_in_8Q7_reg7;
always @(*) begin
    if (in_scale < 7) begin
        x_in_8Q7 = $signed(x) <<< (4'd7 - in_scale);
    end
    else if (in_scale == 7) begin
        x_in_8Q7 = x;
    end
    else begin // in_scale > 7
        x_in_8Q7 = $signed(x) >>> (in_scale - 4'd7);
    end
end
always@(posedge clk)begin
	x_in_8Q7_reg1<=x_in_8Q7;
	x_in_8Q7_reg2<=x_in_8Q7_reg1;
	x_in_8Q7_reg3<=x_in_8Q7_reg2;
	x_in_8Q7_reg4<=x_in_8Q7_reg3;
	x_in_8Q7_reg5<=x_in_8Q7_reg4;
	x_in_8Q7_reg6<=x_in_8Q7_reg5;
	x_in_8Q7_reg7<=x_in_8Q7_reg6;
end
wire signed [9:0] c_2_5_2Q7 =  10'b0_10_1000_000;
wire signed [9:0] _c_2_5_2Q7 = 10'b1_01_1000_000;
wire signed [18:0] out_3Q15;
reg  signed [18:0] out_3Q15_reg1;
wire signed [10:0] y_3Q7;


wire signed [11:0] x_in_L_2Q9;
reg  signed [11:0] x_in_L_2Q9_reg1;
assign x_in_L_2Q9 = $signed(x_in_8Q7_reg1[9:0]) * 3'sb011; 
//                      <2.5           3/4
always@(posedge clk)begin
	x_in_L_2Q9_reg1<=x_in_L_2Q9;
end
wire signed [8:0] L_1Q7;
lin u_lin(//latency = 4
	.clk(clk),
    .x_in_L_2Q9(x_in_L_2Q9_reg1),
    .L_1Q7(L_1Q7) 
);
wire signed [9:0] L_2Q7_1 = L_1Q7 + 10'sb001_000_0000;
wire signed [9:0] half_L_1Q8 = L_2Q7_1;
assign out_3Q15 = half_L_1Q8 *  $signed(x_in_8Q7_reg6[9:0]);
always@(posedge clk)begin
	out_3Q15_reg1<=out_3Q15;
end
assign y_3Q7= out_3Q15_reg1[18:8]; 

always @(*) begin
    if(x_reg7[7]==1'b1 && x_in_8Q7_reg7<=_c_2_5_2Q7)begin
        y = 0;
    end
    else if(x_reg7[7]==1'b0 && x_in_8Q7_reg7 >= c_2_5_2Q7)begin
        y = x_reg7;
    end
    else if (in_scale_reg7 <= 7) begin
        y = (y_3Q7 >>> (4'd7 - in_scale_reg7));
    end
    else begin // in_scale_reg7 > 7
        y = (y_3Q7 <<< (in_scale_reg7 - 4'd7));
    end
end
always@(posedge clk)begin
	y_reg1 <= y;
end
endmodule
