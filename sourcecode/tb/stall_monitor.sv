`timescale 1ns / 1ps
// Reusable valid/ready handshake monitor for AXI-stream-style interfaces.
// Instantiate once per interface you want to characterize; call report()
// (or read the counters directly) once the simulation window of interest
// has ended.
//
// Classification per clock, while 'enable' is high and rst_n is high:
//   transfer_cycles     : valid & ready   (a beat actually moved)
//   valid_stall_cycles  : valid & ~ready  (producer ready, consumer not -> backpressure stall)
//   ready_stall_cycles  : ~valid & ready  (consumer ready, producer not -> starvation/bubble)
//   idle_cycles         : ~valid & ~ready (interface quiescent)
//
// stall_pct() reports (valid_stall + ready_stall) / total_cycles * 100,
// i.e. the fraction of the observed window where a transfer *could not*
// complete on that interface, in either direction.
module stall_monitor #(
    parameter string NAME = "iface"
)(
    input  logic clk,
    input  logic rst_n,
    input  logic enable,   // gate the measurement window; tie to 1'b1 to measure the whole run
    input  logic valid,
    input  logic ready
);

    longint unsigned total_cycles;
    longint unsigned transfer_cycles;
    longint unsigned valid_stall_cycles;
    longint unsigned ready_stall_cycles;
    longint unsigned idle_cycles;

    initial begin
        total_cycles        = 0;
        transfer_cycles     = 0;
        valid_stall_cycles  = 0;
        ready_stall_cycles  = 0;
        idle_cycles         = 0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            total_cycles        <= 0;
            transfer_cycles     <= 0;
            valid_stall_cycles  <= 0;
            ready_stall_cycles  <= 0;
            idle_cycles         <= 0;
        end
        else if (enable) begin
            total_cycles <= total_cycles + 1;
            case ({valid, ready})
                2'b11:   transfer_cycles    <= transfer_cycles + 1;
                2'b10:   valid_stall_cycles <= valid_stall_cycles + 1;
                2'b01:   ready_stall_cycles <= ready_stall_cycles + 1;
                default: idle_cycles        <= idle_cycles + 1;
            endcase
        end
    end

    function automatic real stall_pct();
        longint unsigned stalled;
        stalled = valid_stall_cycles + ready_stall_cycles;
        return (total_cycles > 0) ? (100.0 * real'(stalled) / real'(total_cycles)) : 0.0;
    endfunction

    function automatic real utilization_pct();
        return (total_cycles > 0) ? (100.0 * real'(transfer_cycles) / real'(total_cycles)) : 0.0;
    endfunction

    task automatic report();
        $display("[stall_monitor:%0s] total=%0d transfer=%0d valid_stall=%0d ready_stall=%0d idle=%0d | stall=%.2f%% util=%.2f%%",
            NAME, total_cycles, transfer_cycles, valid_stall_cycles, ready_stall_cycles, idle_cycles,
            stall_pct(), utilization_pct());
    endtask

endmodule
