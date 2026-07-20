`timescale 1ns / 1ps
// Elastic FIFO + upsizer bridging Softmax_control's output to EightGelus's
// input.
//
// Why this exists: Softmax_control's output side (top_data_out/valid_out/
// last_out) has NO ready/backpressure input at all in this core -- it is
// an unconditional, fixed-rate producer that must be sampled every cycle
// it asserts valid, or the sample is lost. EightGelus, on the other hand,
// expects a normal valid/ready handshake on its input. Those two contracts
// are incompatible without a buffer in between, so this module:
//   1) writes every Softmax output sample into a FIFO unconditionally
//      (in_valid has no ready -- writes can never be refused mid-cycle),
//   2) packs LANES consecutive scalar samples (or fewer, if 'last' arrives
//      early) into one LANES*DATA_WIDTH beat for EightGelus, using
//      'out_keep' to mark which lanes are valid on a partial final beat,
//   3) presents that beat on a normal valid/ready handshake.
//
// Safety net: 'in_overflow' pulses (and a $display fires) if the FIFO is
// written while full, which would silently drop a Softmax sample. Size
// FIFO_DEPTH generously relative to the softmax row length in use so this
// never triggers in practice; treat it as an assertion, not a designed
// code path.
module axis_upsizer_fifo #(
    parameter integer LANES      = 4,
    parameter integer DATA_WIDTH = 8,
    parameter integer FIFO_DEPTH = 512
)(
    input                                 clk,
    input                                 rst_n,

    // narrow serial input side: unconditional producer, no ready signal exists upstream
    input                                 in_valid,
    input                                 in_last,
    input      [DATA_WIDTH-1:0]           in_data,
    output reg                            in_overflow,

    // wide parallel output side: normal valid/ready/last/keep handshake
    output                                 out_valid,
    input                                  out_ready,
    output                                 out_last,
    output     [LANES*DATA_WIDTH-1:0]      out_data,
    output     [LANES-1:0]                 out_keep
);

localparam integer FIFO_AW = $clog2(FIFO_DEPTH);
localparam integer CNT_W   = $clog2(LANES+1);

// ---- unconditional-write circular FIFO, {last,data} per entry ----
reg [DATA_WIDTH:0] fifo_mem [0:FIFO_DEPTH-1];
reg [FIFO_AW-1:0]  wr_ptr, rd_ptr;
reg [FIFO_AW:0]    fifo_count;

wire fifo_full  = (fifo_count == FIFO_DEPTH);
wire fifo_empty = (fifo_count == 0);
wire fifo_wr_en = in_valid && !fifo_full;
wire fifo_rd_en;   // driven by the packer FSM below

wire                  fifo_rd_last = fifo_mem[rd_ptr][DATA_WIDTH];
wire [DATA_WIDTH-1:0] fifo_rd_data = fifo_mem[rd_ptr][DATA_WIDTH-1:0];

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        wr_ptr      <= {FIFO_AW{1'b0}};
        rd_ptr      <= {FIFO_AW{1'b0}};
        fifo_count  <= {(FIFO_AW+1){1'b0}};
        in_overflow <= 1'b0;
    end
    else begin
        in_overflow <= in_valid && fifo_full;

        if (fifo_wr_en) begin
            fifo_mem[wr_ptr] <= {in_last, in_data};
            wr_ptr <= wr_ptr + 1'b1;
        end
        if (fifo_rd_en)
            rd_ptr <= rd_ptr + 1'b1;

        case ({fifo_wr_en, fifo_rd_en})
            2'b10:   fifo_count <= fifo_count + 1'b1;
            2'b01:   fifo_count <= fifo_count - 1'b1;
            default: fifo_count <= fifo_count; // 00: idle, 11: one in one out, net zero
        endcase
    end
end

always @(posedge clk) begin
    if (rst_n && in_overflow)
        $display("%0t: ERROR %m: axis_upsizer_fifo overflow -- a Softmax output sample was dropped! Increase FIFO_DEPTH.", $time);
end

// ---- packer FSM: accumulate up to LANES samples (or stop early on 'last') into one wide beat ----
reg [LANES*DATA_WIDTH-1:0] cur_data;
reg [LANES-1:0]            cur_keep;
reg                        cur_last;
reg                        fsm_hold;      // 1 = a completed beat is waiting on out_ready
reg [CNT_W-1:0]            fill_idx;

assign fifo_rd_en = !fifo_empty && !fsm_hold;

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        cur_data <= {(LANES*DATA_WIDTH){1'b0}};
        cur_keep <= {LANES{1'b0}};
        cur_last <= 1'b0;
        fsm_hold <= 1'b0;
        fill_idx <= {CNT_W{1'b0}};
    end
    else if (fsm_hold) begin
        if (out_valid && out_ready) begin
            cur_data <= {(LANES*DATA_WIDTH){1'b0}};
            cur_keep <= {LANES{1'b0}};
            cur_last <= 1'b0;
            fsm_hold <= 1'b0;
            fill_idx <= {CNT_W{1'b0}};
        end
    end
    else if (fifo_rd_en) begin
        cur_data[fill_idx*DATA_WIDTH +: DATA_WIDTH] <= fifo_rd_data;
        cur_keep[fill_idx]                          <= 1'b1;
        fill_idx <= fill_idx + 1'b1;
        if (fifo_rd_last || fill_idx == LANES-1) begin
            fsm_hold <= 1'b1;
            cur_last <= fifo_rd_last;
        end
    end
end

assign out_valid = fsm_hold;
assign out_data  = cur_data;
assign out_keep  = cur_keep;
assign out_last  = cur_last;

endmodule
