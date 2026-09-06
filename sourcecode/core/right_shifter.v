`timescale 1ns / 1ps
// ===========================================================================
// right_shifter.v -- rounding, saturating arithmetic right shift (requantize)
//
// Purpose: take a wide accumulator value (`before_data_width` bits, signed)
// and bring it back down to `after_data_width` bits by shifting right
// `shift` places, with round-half-up and signed saturation. This is the
// requantization step that turns a matmul partial sum back into an int8
// activation. Instantiated once per output lane by MM_out_buffer.v; the same
// round-then-shift-then-clip scheme is mirrored in software by
// apps/golden_model.py's mm_soft() and the testbenches' MM_soft task.
//
// Combinational (no clock). Behaviour:
//   temp1 = data_in >>> shift            (arithmetic shift, sign-extending)
//   temp2 = temp1 + data_in[shift-1]     (round half up: add the bit that
//                                         was shifted past the new LSB)
//   out   = saturate(temp2) to signed [after_data_width]
//           i.e. clamp to +2^(after-1)-1 / -2^(after-1)
// The shift == 0 path is handled separately because `data_in[shift-1]`
// would index bit [-1]; there it just saturates data_in with no rounding.
// under_min / over_max detect that the value no longer fits in the narrow
// signed range by checking that the bits above the new sign bit are not a
// clean sign extension.
// ===========================================================================
module right_shifter
#(
    parameter before_data_width = 32,   // width of the incoming accumulator
    parameter after_data_width = 8,     // width of the requantized result
    parameter shift_width = 5           // width of the `shift` amount port
)
(
    shift,
    data_in,
    data_out
);

input wire [shift_width-1:0]shift;
input wire signed [before_data_width-1:0] data_in;
output reg signed[after_data_width-1:0] data_out;

wire signed [before_data_width-1:0] temp1_out;
wire signed [before_data_width-1:0] temp2_out;

assign temp1_out = data_in >>> shift;
assign temp2_out = data_in[shift-1] ? temp1_out + 1 : temp1_out;

wire under_min = temp2_out[before_data_width-1] & (~(& temp2_out[before_data_width-2:after_data_width-1]));
wire over_max = (~temp2_out[before_data_width-1]) & (|temp2_out[before_data_width-2:after_data_width-1]);

wire under_min_S0 = data_in[before_data_width-1] & (~(& data_in[before_data_width-2:after_data_width-1]));
wire over_max_S0 = (~data_in[before_data_width-1]) & (|data_in[before_data_width-2:after_data_width-1]);

always @(*) begin
    if(shift == 0)
        case ({under_min_S0,over_max_S0})
            2'b10: data_out = {1'b1,{(after_data_width-1){1'b0}}};//data_out = 8'b1000_0000;
            2'b01: data_out = {1'b0,{(after_data_width-1){1'b1}}};//8'b0111_1111;
            default: data_out = data_in;
        endcase
    else begin
        case ({under_min,over_max})
            2'b10: data_out = {1'b1,{(after_data_width-1){1'b0}}};//data_out = 8'b1000_0000;
            2'b01: data_out = {1'b0,{(after_data_width-1){1'b1}}};//8'b0111_1111;
            default: data_out = temp2_out[after_data_width-1:0];
        endcase
    end
end

endmodule

