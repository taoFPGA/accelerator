`timescale 1ns / 1ps
// ===========================================================================
// PE.v -- one processing element of the systolic array
//
// A single weight-stationary multiply-accumulate cell. On `set_w` it latches
// its weight; every cycle it computes psum_out = psum_in + x_in*reg_w and
// passes x_in on to its right neighbour (x_out) one cycle later. array_n of
// these form a PE_line; array_m lines form the PE_array. USE_DSP only
// changes the physical mapping (DSP48E1 vs LUT/CARRY4) -- see the parameter
// note below.
// ===========================================================================
module PE
#(
    parameter data_width = 8,
    parameter array_m = 16,
    parameter array_n = 16,
    parameter log2_array_m = 4,
    // Selects whether this PE's multiply-accumulate is forced into a
    // DSP48E1 hard macro (1) or left LUT/CARRY4-mapped (0). Purely a
    // physical-implementation choice -- the multiply-accumulate semantics
    // and cycle timing are identical either way. See PE_array.v's
    // NUM_DSP_ROWS for the array-wide DSP/LUT split and its rationale.
    parameter integer USE_DSP = 1
)
(
    input                                                   clk,
    input                                                   set_w,
    input                                                   rst_n,
    input signed [data_width-1:0]                           x_in,
    input signed [data_width-1:0]                           w,
    input signed [2*data_width+log2_array_m-1:0]            psum_in,
    output reg signed [data_width-1:0]                      x_out,
    output signed [2*data_width+log2_array_m-1:0]           psum_out
);
reg signed [data_width-1:0] reg_w;

// use_dsp must be attached to the register DECLARATION that holds the
// multiply-accumulate result (per Xilinx UG901), not to the enclosing
// 'always' block -- an attribute on the procedural block itself is not
// recognized by synthesis and silently has no effect (verified: an
// earlier version of this file placed it on the always block, and
// synthesis produced byte-identical LUT/DSP/CARRY4 counts regardless of
// USE_DSP, i.e. it was a no-op). psum_out is therefore a wire here, driven
// by a per-branch internal reg that carries the attribute.
generate
if (USE_DSP) begin : g_dsp_mapped
    (* use_dsp = "yes" *) reg signed [2*data_width+log2_array_m-1:0] psum_out_r;
    assign psum_out = psum_out_r;
    always @(posedge clk) begin
        if(~rst_n)begin
            psum_out_r <= 0;
            reg_w <= 0;
            x_out <= 0;
        end
        else begin
            if(set_w)
                reg_w <=w;
            psum_out_r <= psum_in + x_in*reg_w;
            x_out <= x_in;
        end
    end
end
else begin : g_lut_mapped
    (* use_dsp = "no" *) reg signed [2*data_width+log2_array_m-1:0] psum_out_r;
    assign psum_out = psum_out_r;
    always @(posedge clk) begin
        if(~rst_n)begin
            psum_out_r <= 0;
            reg_w <= 0;
            x_out <= 0;
        end
        else begin
            if(set_w)
                reg_w <=w;
            psum_out_r <= psum_in + x_in*reg_w;
            x_out <= x_in;
        end
    end
end
endgenerate
endmodule
