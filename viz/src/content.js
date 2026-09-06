/* content.js -- guided-tour script. Edit the copy here; run
   `python viz/build.py` to repackage the single-file bundle.
   Global consumed by app.js: STAGES. */
var STAGES = [
  { s:"Stage 1", t:"Ingestion & staging",
    view:"logic", cam:[ -6, 5.5, 9 ], tgt:[ -3, 0.6, 0 ],
    emph:["dma0","dma1","cv0","cv1","mm"],
    html:"<b>PS7 → AXI-DMA → MM_in_buffer.</b> The Cortex-A9 kicks two <span class='mono'>MM2S</span> DMA engines; each reads an operand tile from DDR through a SmartConnect HP port and emits an AXI4-Stream. A width converter matches it to the accelerator's <span class='mono'>128-bit</span> ingress — 16 lanes × 8-bit, one lane per array column. Tiles land in <b>29 × RAMB36</b> of MM_in_buffer as a ping-pong: the array drains tile A while a DMA fills tile B, so the systolic wavefront never stalls on DDR latency. Aggregate stream demand is <span class='mono'>3.6 GB/s</span> — comfortably under the PS 32-bit DDR3 ceiling (~4.3 GB/s), so this config is not memory-bound. <i>Tip: single-click any block for its system role, double-click the accelerator to dive inside.</i>",
    dia:"ingest" },
  { s:"Stage 2", t:"Systolic MAC propagation",
    view:"core", cam:null, tgt:null,
    emph:["mm"],
    html:"<b>u_PE_array — 16 × 16, 192 × DSP48E1.</b> Weights are pre-loaded and held stationary in each PE's B register. Activations enter the west edge and shift east one column per cycle (<span class='mono'>A_in → A_out</span>); partial sums propagate south (<span class='mono'>P → row+1</span>). Inputs are skewed by the <b>348 SRL delay lines</b> so every PE on an anti-diagonal computes the same output index in lock-step — a moving wavefront. The DSP48E1 MACC is a <b>3-cycle pipeline</b> (A/B → M → P register); an activation crosses all 16 columns in 16 cycles, so the first result lands after <span class='mono'>2·N + 3 ≈ 35</span> cycles (≈ 0.35 µs at 100 MHz), then one result column per cycle. Only the first 12 rows get a DSP — the device is one DSP column short, so the last 4 rows are LUT MACs. Peak: <span class='mono'>205 · 2 · 100 MHz = 41.0 GOP/s</span> — watch the telemetry panel fill as the wavefront propagates.",
    dia:"pe" },
  { s:"Stage 3", t:"Drain & writeback",
    view:"core", cam:[ 0, 6, -12 ], tgt:[0,0.4,-2],
    emph:["mm","cv2","dma2"],
    html:"<b>MM_out_buffer → LayerNorm → Softmax → GELU → S2MM DMA → DDR.</b> The result wavefront leaves the array's south edge still diagonally skewed; <b>37.5 RAMB36-equiv</b> in MM_out_buffer absorb it and un-skew it into dense rows for the post-MatMul stages. The final GELU output is a <span class='mono'>32-bit</span> stream (4 lanes × 8-bit); a width converter matches it to the <span class='mono'>S2MM</span> DMA, which writes to DDR with AXI back-pressure — if the HP port stalls, <span class='mono'>tready</span> deasserts and the drain buffer holds.",
    dia:"drain" },
  { s:"Stage 4", t:"Post-MatMul pipeline",
    view:"phases",
    emph:["mm"],
    html:"<b>The full transformer block, on chip.</b> <span class='mono'>transformer_block_top.v</span> wires three streaming stages onto the MatMul output. <b>axis_downsizer</b> serialises each 128-bit beat into 16 scalars and — being single-buffered — backpressures MM_ultra for ~16 cycles per beat, so <i>this bridge</i>, not the PE array, sets the sustained throughput. <b>Softmax_control</b> (Exp_module + AdderS + right_shifter) normalises each score row with no output backpressure, so <b>axis_upsizer_fifo</b> (depth 512) must buffer it before <b>EightGelus</b> applies GELU on 4 lanes. All on the same <span class='mono'>clk_fpga_0</span> — one clock, zero CDC. Placed &amp; routed footprint: downsizer <span class='mono'>133 LUT</span>, Softmax <span class='mono'>630 LUT / 4 DSP</span>, upsizer FIFO <span class='mono'>198 LUT</span>, GELU <span class='mono'>1.4k LUT / 4 DSP</span>.",
    dia:"future" }
];
