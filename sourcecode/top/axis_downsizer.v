`timescale 1ns / 1ps
// Single-buffer AXI-stream downsizer: LANES*DATA_WIDTH wide beat in ->
// LANES sequential DATA_WIDTH beats out (lane 0 first).
//
// Used to bridge MM_ultra's out_data (A_size parallel lanes/cycle) into
// Softmax_control's serial, one-scalar-per-cycle top_data_in.
//
// Simplification (documented, not hidden): this is a single-entry buffer,
// so in_ready deasserts for the whole LANES-cycle drain of a beat -- i.e.
// it trades throughput for simplicity. A double-buffered version would
// let the wide side keep accepting while the previous beat drains, at
// the cost of a second LANES*DATA_WIDTH register and a small amount of
// extra control logic.
module axis_downsizer #(
    parameter integer LANES      = 16,
    parameter integer DATA_WIDTH = 8
)(
    input                               clk,
    input                               rst_n,

    // wide (parallel) side
    input                                in_valid,
    output                               in_ready,
    input                                in_last,
    input      [LANES*DATA_WIDTH-1:0]    in_data,

    // narrow (serial) side
    output                                out_valid,
    input                                 out_ready,
    output                                out_last,
    output     [DATA_WIDTH-1:0]           out_data
);

localparam integer CNT_WIDTH = $clog2(LANES+1);

reg [LANES*DATA_WIDTH-1:0] data_shift;
reg                        beat_last;
reg [CNT_WIDTH-1:0]        lane_idx;
reg                        draining;

assign in_ready  = ~draining;
assign out_valid = draining;
assign out_data  = data_shift[DATA_WIDTH-1:0];
assign out_last  = draining & beat_last & (lane_idx == LANES-1);

always @(posedge clk) begin
    if (~rst_n) begin
        draining   <= 1'b0;
        lane_idx   <= {CNT_WIDTH{1'b0}};
        beat_last  <= 1'b0;
        data_shift <= {(LANES*DATA_WIDTH){1'b0}};
    end
    else if (!draining) begin
        if (in_valid && in_ready) begin
            data_shift <= in_data;
            beat_last  <= in_last;
            lane_idx   <= {CNT_WIDTH{1'b0}};
            draining   <= 1'b1;
        end
    end
    else begin
        if (out_valid && out_ready) begin
            data_shift <= data_shift >> DATA_WIDTH;
            if (lane_idx == LANES-1) begin
                draining <= 1'b0;
                lane_idx <= {CNT_WIDTH{1'b0}};
            end
            else begin
                lane_idx <= lane_idx + 1'b1;
            end
        end
    end
end

endmodule
