/* content.js -- guided-tour script. Edit the copy here; run
   `python viz/build.py` to repackage the single-file bundle.
   Global consumed by app.js: STAGES. */
var STAGES = [
  { s:"Stage 1", t:"Ingestion & staging",
    view:"logic", cam:[ -6, 5.5, 9 ], tgt:[ -3, 0.6, 0 ],
    emph:["dma0","dma1","cv0","cv1","mm"],
    html:"<b>PS7 → AXI-DMA → MM_in_buffer.</b> The Cortex-A9 kicks two <span class='mono'>MM2S</span> DMA engines; each reads an operand tile from DDR through a SmartConnect HP port and emits an AXI4-Stream. A width converter packs it to <span class='mono'>384-bit</span> — 24 lanes × 16-bit, one lane per array column. Tiles land in <b>43 × RAMB36</b> arranged as a ping-pong: the array drains buffer A while DMA fills buffer B, so the systolic pipeline never stalls on memory latency.",
    dia:"ingest" },
  { s:"Stage 2", t:"Systolic MAC propagation",
    view:"core", cam:null, tgt:null,
    emph:["mm"],
    html:"<b>u_PE_array — 24 × 24, 220 × DSP48E1.</b> Weights are pre-loaded and held stationary in each PE's B register. Activations enter the west edge and shift east one column per cycle (<span class='mono'>A_in → A_out</span>); partial sums propagate south (<span class='mono'>P → row+1</span>). Inputs are skewed by the <b>609 SRL delay lines</b> so every PE on an anti-diagonal computes the same output index in lock-step — a moving wavefront. The DSP48E1 MACC is a <b>3-cycle pipeline</b> (A/B → M → P register); an activation crosses all 24 columns in 24 cycles, so the first result lands after <span class='mono'>2·N + 3 ≈ 51</span> cycles (≈ 0.51 µs at 100 MHz), then one result column per cycle. At full occupancy that is <span class='mono'>220 · 2 · 100 MHz = 44.0 GOP/s</span> — watch the telemetry panel fill as the wavefront propagates.",
    dia:"pe" },
  { s:"Stage 3", t:"Drain & writeback",
    view:"core", cam:[ 0, 6, -12 ], tgt:[0,0.4,-2],
    emph:["mm","cv2","dma2"],
    html:"<b>MM_out_buffer → S2MM DMA → DDR.</b> The result wavefront leaves the array's south edge still diagonally skewed; <b>56 × RAMB36</b> absorb it and un-skew it back into dense rows. A width converter narrows <span class='mono'>384→</span> the DMA word and the <span class='mono'>S2MM</span> engine writes back to DDR with AXI back-pressure — if the HP port stalls, <span class='mono'>tready</span> deasserts and the drain buffer holds. End-to-end latency from first multiply to last drained element ≈ <span class='mono'>2·N + fill</span> cycles per tile.",
    dia:"drain" },
  { s:"Stage 4", t:"Transformer extension (RTL)",
    view:"logic", cam:[ 12, 6, 12 ], tgt:[ 7, 0.6, 0 ], ghost:true,
    emph:["mm"],
    html:"<b>Where it continues in the full design.</b> This bitstream stops at the matmul core; <span class='mono'>transformer_block_top.v</span> wires three more streaming stages onto <span class='mono'>mm_out_data</span> (shown ghosted). <b>axis_downsizer</b> serialises each wide MM beat and — being single-buffered — backpressures the array, so <i>it</i>, not the PEs, caps transformer throughput. <b>Softmax_control</b> (Exp + AdderS + right_shifter) normalises each score row with no output backpressure, so <b>axis_upsizer_fifo</b> (depth 512) must buffer it before <b>EightGelus</b> applies GELU on <span class='mono'>num_gelu</span> lanes. All on the same <span class='mono'>clk_fpga_0</span> — no new clock, no CDC. Full 16-lane RTL synth: <span class='mono'>10.5k LUT · 205 DSP · 71 BRAM36</span>.",
    dia:"future" }
];
