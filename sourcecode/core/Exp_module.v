`timescale 1ns / 1ps
// ===========================================================================
// Exp_module.v -- fixed-point exp(x) for x <= 0   (latency = 3 clocks)
//
// Evaluates e^x for non-positive x, as needed by the softmax numerator
// (Softmax.v subtracts the row max first, so its argument is always <= 0).
// Method: change base to 2, split the exponent into integer + fraction, do
// the integer part as a barrel shift and the fraction with a 1st-order
// (1 + 0.5*f) approximation, then multiply.
//
//   x_log2e = x * 23/16      (23 = round(log2(e) * 16), so this is x*log2(e)
//                             in ...Q14 -> result is <= 0)
//   take |x_log2e|; integer part -> x_int (clamped to 12), fraction -> frac
//   e^x ~= 2^-x_int * (1 - 0.5*frac)
//        = (1<<11 >> x_int)  *  (1 - frac/2)      -> temp_y, unsigned Q25
//   saturate to 25'h1FFFFFF if the >1.0 guard bit is set.
//
// Ports (see sourcecode/README.md for SxQy): x_S9Q10 in, y_U0Q25 out
// (unsigned, 0..~1). Registered at the input mul, the two temp products,
// and the output.
// ===========================================================================
module Exp_module(//latency = 3
	input 					clk,
    input  signed [19:0]    x_S9Q10, // argument, <= 0
    output reg signed [24:0]    y_U0Q25_reg1 // e^x, unsigned 0..1
);

wire signed [24:0] x_log2e_S10Q14; // x*log2(e); <= 0
reg  signed [24:0] x_log2e_S10Q14_reg1;
assign x_log2e_S10Q14  = x_S9Q10 * 6'sd23; // 23/16 ~= log2(e)

always@(posedge clk)begin
	x_log2e_S10Q14_reg1 <= x_log2e_S10Q14;
end

wire [23:0] x_log2e_U10Q14_abs; 
assign x_log2e_U10Q14_abs = ~x_log2e_S10Q14_reg1+1;

wire [9:0] x_int_10Q0 = x_log2e_U10Q14_abs[23:14];

wire [13:0] x_decimal_0Q14 = x_log2e_U10Q14_abs[13:0];

wire [14:0] temp_1Q14 = 15'b100_0000_0000_0000 - {2'b0,x_decimal_0Q14[13:1]};//1+0.5*x_decimal,unsigned
reg  [14:0] temp_1Q14_reg1;
wire [3:0] x_int_4Q0;//unsigned
assign x_int_4Q0 = (x_int_10Q0 > 12)? 4'd12 : x_int_10Q0;//to 12bits

wire [11:0] temp_2_int_1Q11; 
reg  [11:0] temp_2_int_1Q11_reg1; 
assign temp_2_int_1Q11 = 12'b1000_0000_0000 >> x_int_4Q0;
always@(posedge clk)begin
	temp_2_int_1Q11_reg1<=temp_2_int_1Q11;
	temp_1Q14_reg1<=temp_1Q14;
end

wire [26:0] temp_y_2Q25 = temp_2_int_1Q11_reg1 * temp_1Q14_reg1;//unsigned


// wire signed [11:0] y_U0Q12;
// assign y_U0Q12 = temp_y_2Q25[25] == 1'b1 ? 12'b1111_1111_1111:temp_y_2Q25[24:13];
wire signed [24:0] y_U0Q25;
assign y_U0Q25 = temp_y_2Q25[25] == 1'b1 ? 25'h1FF_FFFF:temp_y_2Q25[24:0];

always@(posedge clk)begin 
	y_U0Q25_reg1<=y_U0Q25;
end

endmodule
