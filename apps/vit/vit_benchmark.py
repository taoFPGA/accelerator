"""
ViT benchmark for the PYNQ-Z2: a real, correct, pure-NumPy ViT-Tiny
software inference baseline, plus a separate hardware kernel throughput
benchmark for TransformerAccelerator at ViT-Tiny-representative matrix
shapes.

SCOPE, READ THIS FIRST: transformer_block_axi_top's fixed pipeline is
matmul -> per-row softmax -> GELU, fused as one inseparable hardware
stage. No real ViT operation has that exact sequence -- attention has
matmuls and one softmax but no GELU; the MLP has a matmul and GELU but
no softmax in between. There is therefore no way to substitute this
accelerator into a real ViT layer and get numerically correct attention
or MLP results; the AXI-Stream output is always post-softmax-post-GELU,
with no way to tap the raw matmul result.

Given that, this script deliberately does NOT claim an end-to-end
hardware-accelerated ViT speedup. It reports two honestly separate
things:
  1. SOFTWARE BASELINE -- a real, validated ViT-Tiny forward pass
     (matches the reference PyTorch model to ~1e-5, see
     export_vit_weights.py/vit_numpy.py) run entirely on the ARM
     Cortex-A9, timed for latency/throughput on the real sample image.
  2. HARDWARE KERNEL BENCHMARK -- TransformerAccelerator's throughput on
     synthetic int8 data at matrix shapes sized to match ViT-Tiny's real
     dimensions (embed_dim=192, mlp_hidden=768, seq_len=197), compared
     against an equivalent CPU computation of the *same fused* three ops
     (mm_soft -> softmax_ref -> gelu_ref from golden_model.py) at the
     identical shape -- a fair, direct kernel-level speedup number.

The kernel speedup in part 2 does NOT transfer to an end-to-end ViT
speedup claim -- see the printed disclaimer at the end.

Run from the same Jupyter folder as design.bit/design.hwh/MM.py/
golden_model.py, with assets/ (vit_tiny_weights.npz, vit_input.npy,
imagenet_classes.txt) alongside this script.
"""
import os
import time

import numpy as np

from MM import TransformerAccelerator, DEFAULT_SHIFT, DEFAULT_SOFTMAX_SCALE_IN
from golden_model import mm_soft, softmax_ref, gelu_ref
from vit_numpy import vit_forward, EMBED_DIM

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

N_RUNS_SOFTWARE_VIT = 5
N_RUNS_KERNEL = 10

# Representative ViT-Tiny matrix shapes, in the hardware's terms. Row count
# (seq_len) has no A_size tiling constraint -- only the two column counts
# do (both already multiples of A_size=16 here). Both shapes' block counts
# are comfortably inside the regime report/project_story.md Section 29
# confirmed correct on real hardware (F_width_block_num=6/
# W_width_block_num=10 passed cleanly); nowhere near the small-block-count
# edge case (Section 29) that's still an open bug.
#
# MLP_SHAPE's out_cols is capped at 320, NOT the real MLP hidden dim (768):
# this design's 3 AXI DMA cores were synthesized with c_sg_length_width=16
# (prj.tcl), capping any single transfer at 65536 bytes. The real MLP
# weight buffer (192*768=147456 bytes) exceeds that. Splitting it into
# multiple smaller DMA transfers is NOT a safe software workaround here --
# MM_in_buffer.v's write-address counters reset to 0 on the stream's
# tlast, and this design's direct-register DMA mode asserts tlast at the
# end of *every* transfer issued, not just a true final one; two chunked
# transfers would each look like "the last beat" to the RTL and the
# second would silently overwrite the first. A real fix (larger
# c_sg_length_width, or real Scatter-Gather DMA) needs re-synthesis, not
# a driver patch -- see report/project_story.md Section 31.
SEQ_LEN = 197           # ViT-Tiny token count (196 patches + 1 cls token)
MLP_HIDDEN_CAPPED = 320  # largest multiple of A_size keeping all 3 buffers <= 65536 bytes at EMBED_DIM=192/SEQ_LEN=197
PROJECTION_SHAPE = (SEQ_LEN, EMBED_DIM, EMBED_DIM)          # projection-sized kernel (192 -> 192)
MLP_SHAPE = (SEQ_LEN, EMBED_DIM, MLP_HIDDEN_CAPPED)         # MLP-shaped, DMA-limited to 320 (real MLP hidden dim is 768)


def software_vit_baseline():
    weights = dict(np.load(os.path.join(ASSETS, "vit_tiny_weights.npz")))
    img = np.load(os.path.join(ASSETS, "vit_input.npy"))
    with open(os.path.join(ASSETS, "imagenet_classes.txt")) as f:
        classes = [line.strip() for line in f]

    # one untimed warm-up run (page faults / first-touch cost shouldn't
    # count against the measured latency)
    logits = vit_forward(img, weights)

    latencies = []
    for _ in range(N_RUNS_SOFTWARE_VIT):
        t0 = time.perf_counter()
        logits = vit_forward(img, weights)
        latencies.append(time.perf_counter() - t0)

    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    top5 = np.argsort(probs)[::-1][:5]

    return {
        "latencies_s": latencies,
        "mean_latency_s": float(np.mean(latencies)),
        "std_latency_s": float(np.std(latencies)),
        "top5": [(classes[i], float(probs[i])) for i in top5],
    }


def hardware_kernel_benchmark(acc, shape, label):
    rows, in_cols, out_cols = shape
    acc.configure(rows, in_cols, out_cols)

    np.random.seed(0)
    feature = np.random.randint(-128, 128, size=(rows, in_cols)).astype(np.int8)
    weight = np.random.randint(-128, 128, size=(in_cols, out_cols)).astype(np.int8)

    acc.run(feature, weight)  # warm-up (also primes the DMA buffers)

    hw_latencies = []
    for _ in range(N_RUNS_KERNEL):
        t0 = time.perf_counter()
        acc.run(feature, weight)
        hw_latencies.append(time.perf_counter() - t0)

    sw_latencies = []
    for _ in range(N_RUNS_KERNEL):
        t0 = time.perf_counter()
        z = mm_soft(feature, weight, DEFAULT_SHIFT)
        row_real = z.astype(np.float64) * (2.0 ** -DEFAULT_SOFTMAX_SCALE_IN)
        out = np.empty_like(row_real)
        for r in range(row_real.shape[0]):
            out[r] = gelu_ref(softmax_ref(row_real[r]))
        sw_latencies.append(time.perf_counter() - t0)

    ops = 2 * rows * in_cols * out_cols  # multiply-add pairs in the matmul
    hw_mean = float(np.mean(hw_latencies))
    sw_mean = float(np.mean(sw_latencies))

    return {
        "label": label,
        "shape": shape,
        "hw_mean_latency_s": hw_mean,
        "hw_std_latency_s": float(np.std(hw_latencies)),
        "hw_throughput_gops": ops / hw_mean / 1e9,
        "sw_mean_latency_s": sw_mean,
        "sw_throughput_gops": ops / sw_mean / 1e9,
        "kernel_speedup": sw_mean / hw_mean,
    }


def main():
    print("=" * 70)
    print("PART 1: Software ViT-Tiny baseline (real, validated, on ARM CPU)")
    print("=" * 70)
    sw = software_vit_baseline()
    print(f"Mean latency:  {sw['mean_latency_s']*1000:8.1f} ms  (std {sw['std_latency_s']*1000:.1f} ms, n={N_RUNS_SOFTWARE_VIT})")
    print(f"Throughput:    {1.0/sw['mean_latency_s']:8.3f} images/sec")
    print("Top-5 classification (validates this run against the known-correct reference):")
    for name, prob in sw["top5"]:
        print(f"  {name:30s} {prob*100:5.2f}%")

    print()
    print("=" * 70)
    print("PART 2: Hardware kernel benchmark (TransformerAccelerator, synthetic data)")
    print("=" * 70)
    acc = TransformerAccelerator("design.bit")
    results = []
    for shape, label in [(PROJECTION_SHAPE, "projection-sized (192x192)"),
                          (MLP_SHAPE, f"MLP-shaped, DMA-limited (192x{MLP_HIDDEN_CAPPED}, real MLP hidden dim is 768)")]:
        r = hardware_kernel_benchmark(acc, shape, label)
        results.append(r)
        print(f"\n{r['label']}  rows={shape[0]} in_cols={shape[1]} out_cols={shape[2]}")
        print(f"  Hardware: {r['hw_mean_latency_s']*1000:7.3f} ms  (std {r['hw_std_latency_s']*1000:.3f} ms)  "
              f"{r['hw_throughput_gops']:6.3f} GOP/s")
        print(f"  CPU:      {r['sw_mean_latency_s']*1000:7.3f} ms  "
              f"{r['sw_throughput_gops']:6.3f} GOP/s")
        print(f"  Kernel speedup (CPU/HW, same fused matmul+softmax+GELU op): {r['kernel_speedup']:.2f}x")

    print()
    print("=" * 70)
    print("SCOPE DISCLAIMER -- read before citing a \"speedup\" number")
    print("=" * 70)
    print("""The kernel speedup above compares the SAME fused matmul+softmax+GELU
operation on hardware vs. CPU, at ViT-Tiny-representative matrix shapes.
It is NOT an end-to-end ViT inference speedup: transformer_block_axi_top's
fixed matmul->softmax->GELU pipeline does not match any real ViT
operation's actual computation (attention has no GELU; the MLP has no
softmax between its matmul and GELU), so this accelerator cannot be
substituted into a real ViT layer and produce correct attention or MLP
results. The software latency/throughput above is a real, validated,
end-to-end ViT-Tiny inference number; the hardware number is a kernel
throughput measurement at a representative size, not a measured
accelerated ViT run. See apps/vit/vit_benchmark.py's module docstring
and report/project_story.md for the full reasoning.""")


if __name__ == "__main__":
    main()
