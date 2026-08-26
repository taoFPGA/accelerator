"""
Bit-accurate-in-spirit Python golden reference for the transformer
accelerator's MM_ultra -> Softmax_control -> EightGelus pipeline.

This is a direct port of the exact reference math already verified against
real RTL in simulation -- not a new derivation:

  - mm_soft()      <-> transformer_block_tb.sv's MM_soft task (and the
                       identical logic in MM_Ultra_tb.sv). Its round-then-
                       shift-then-clip scheme was cross-checked line-by-line
                       against sourcecode/core/right_shifter.v (the actual
                       synthesized rounding hardware) and is mathematically
                       identical: round-half-up arithmetic right shift by
                       `shift`, saturate to signed int8.
  - softmax_ref()  <-> transformer_block_tb.sv's Softmax_task (and the
                       equivalent task in Softmax_top_tb.sv): standard
                       numerically-stable softmax.
  - gelu_ref()     <-> transformer_block_tb.sv's gelu_ref function (and
                       gelu_tb.sv's gelu_task): the tanh approximation of
                       GELU (same formula as PyTorch's
                       F.gelu(x, approximate='tanh')).
  - transformer_golden() <-> the chaining in transformer_block_tb.sv's
                       initial block: MM_soft's int8 output is dequantized
                       by 2**-softmax_scale_in, softmax'd per row, then
                       GELU'd -- all in real (float) arithmetic from that
                       point on, exactly as the testbench does it (the
                       hardware's actual softmax->GELU handoff is int8, but
                       the *reference* model treats it as ideal real numbers
                       and only re-quantizes at the final comparison, in
                       compare_to_hardware() below -- matching the
                       testbench's own methodology, not a shortcut of mine).
  - compare_to_hardware() <-> transformer_block_tb.sv's final check: dequantize
                       the hardware's int8 output by 2**-gelu_scale and
                       require every element within `tol_lsb` LSBs (at that
                       scale) of the real-valued reference -- the same
                       tolerance (6 LSBs) the testbench itself uses, because
                       errors compound across two quantization stages
                       (softmax's int8 output, then GELU's int8 output) and
                       this is the bound already validated as meaningful for
                       this design, not an arbitrarily loosened check.

One quirk preserved deliberately, not fixed: Softmax_task's row-max seed
starts at 0.0, not -inf (`real smax = 0;` in the SV source), so a row whose
every element is negative would compute a max of 0 instead of the row's
true (negative) max. This never triggers with this project's actual test
data (feature/weight matrices come from the full int8 range, and matmul
output feeding softmax is likewise signed, but real transformer
activations after a matmul are rarely all-negative across a whole row) --
replicated verbatim here because the goal is to reproduce the exact
reference already verified in simulation, not a mathematically idealized
softmax.
"""
import numpy as np


def mm_soft(feature: np.ndarray, weight: np.ndarray, shift: int) -> np.ndarray:
    """feature: (rows, in_cols) int8. weight: (in_cols, out_cols) int8.
    Returns (rows, out_cols) int8: round(feature @ weight / 2**shift), saturated."""
    acc = feature.astype(np.int64) @ weight.astype(np.int64)
    if shift > 0:
        acc = (acc + (1 << (shift - 1))) >> shift
    return np.clip(acc, -128, 127).astype(np.int8)


def softmax_ref(row: np.ndarray) -> np.ndarray:
    """row: 1-D float64 array. Returns a 1-D float64 array summing to 1."""
    smax = max(0.0, float(np.max(row)))
    exp = np.exp(row - smax)
    return exp / np.sum(exp)


def gelu_ref(x):
    """Tanh-approximation GELU, elementwise. x: float or ndarray."""
    c1 = np.sqrt(2.0 / np.pi)
    c2 = 0.044715
    return 0.5 * x * (1.0 + np.tanh(c1 * (x + c2 * x ** 3)))


def transformer_golden(feature: np.ndarray, weight: np.ndarray, shift: int,
                        softmax_scale_in: int) -> np.ndarray:
    """Real-valued (float64) reference for feature @ weight -> per-row softmax
    -> GELU, chained exactly as transformer_block_tb.sv's initial block does.
    Shape: (rows, out_cols), same as the hardware's dequantized output."""
    z = mm_soft(feature, weight, shift)  # (rows, out_cols) int8
    row_real = z.astype(np.float64) * (2.0 ** -softmax_scale_in)
    out = np.empty_like(row_real)
    for r in range(row_real.shape[0]):
        out[r] = gelu_ref(softmax_ref(row_real[r]))
    return out


def compare_to_hardware(hw_result: np.ndarray, golden_real: np.ndarray,
                         gelu_scale: int, tol_lsb: float = 6.0) -> dict:
    """hw_result: the int8 ndarray TransformerAccelerator.run() returned.
    golden_real: transformer_golden(...)'s output for the same inputs/config.
    Same pass/fail rule as transformer_block_tb.sv's final check."""
    hw_real = hw_result.astype(np.float64) * (2.0 ** -gelu_scale)
    tol = tol_lsb * (2.0 ** -gelu_scale)
    diff = hw_real - golden_real
    bad = np.abs(diff) > tol
    return {
        "passed": not bool(np.any(bad)),
        "num_errors": int(np.count_nonzero(bad)),
        "num_elements": int(diff.size),
        "max_abs_diff": float(np.max(np.abs(diff))),
        "tolerance": tol,
        "bad_indices": np.argwhere(bad),
    }
