`timescale 1ns / 1ps
// ===========================================================================
// AdderS.v -- SIMD saturating signed adder
//
// Purpose: element-wise C = saturate(A + B) over `A_size` lanes packed into
// one flat bus, each lane `data_width` bits signed. Used by MM_out_buffer.v
// to accumulate the current matmul output tile (A) into the running
// per-output-column sum already held in the output BRAM (B) without letting
// a lane wrap around silently.
//
// Combinational. Per lane: sign-extend both operands by one bit, add in
// (data_width+1) bits, then look at the top two bits of the result --
//   2'b01 -> positive overflow  -> clamp to  +2^(data_width-1)-1  (0x7F..)
//   2'b10 -> negative overflow  -> clamp to  -2^(data_width-1)    (0x80..)
//   else  -> in range, take the low data_width bits.
// C_array_display is a debug-only unpacked view of C for waveform viewing.
// ===========================================================================
module AdderS
#(
    parameter integer A_size = 4,       // number of parallel lanes
    parameter integer data_width = 8    // signed bits per lane
)(
    input  [A_size * data_width - 1 : 0] A,
    input  [A_size * data_width - 1 : 0] B,
    output reg [A_size * data_width - 1 : 0] C
);
wire [(data_width + 1)-1:0] temp [A_size-1:0]; // one guard bit above the sign so the 2-bit MSB pair flags +/- overflow
wire [data_width - 1:0] C_array_display [A_size-1:0];
genvar i;

generate
    for(i=0;i<A_size;i=i+1)begin
        assign C_array_display[i] = C[i*data_width +: data_width];
    end
endgenerate

generate
    for(i=0;i<A_size;i=i+1)begin
        assign temp[i] = {A[(i+1)*data_width-1],A[i *data_width +: data_width]} 
                       + {B[(i+1)*data_width-1],B[i *data_width +: data_width]};
    end
endgenerate
generate
    for(i=0;i<A_size;i=i+1)begin
        always @(*) begin
            case (temp[i][data_width:data_width-1])
                2'b01: C[i * data_width +: data_width] = {1'b0,{(data_width-1){1'b1}}};   
                2'b10: C[i * data_width +: data_width] = {1'b1,{(data_width-1){1'b0}}};   
                default: C[i * data_width +: data_width] = temp[i][data_width-1:0];
            endcase
         
        end
    end
endgenerate
endmodule
