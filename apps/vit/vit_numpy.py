"""
Pure-NumPy forward pass for timm's vit_tiny_patch16_224 (no PyTorch/timm
required -- this is what actually runs on the PYNQ-Z2's ARM Cortex-A9,
which has no PyTorch wheels available for its 32-bit architecture).

Architecture (matches the exported state_dict exactly -- see
export_vit_weights.py): patch embed (Conv2d(3,192,16,16), equivalent to
a per-patch Linear) -> prepend cls token -> add positional embedding ->
12x pre-norm transformer blocks (LayerNorm -> multi-head self-attention
-> residual, LayerNorm -> MLP w/ GELU -> residual) -> final LayerNorm ->
linear classification head. embed_dim=192, num_heads=3, head_dim=64,
mlp_hidden=768, depth=12, patch=16, img_size=224 (196 patches + 1 cls
token = 197 tokens).
"""
import numpy as np

EMBED_DIM = 192
NUM_HEADS = 3
HEAD_DIM = EMBED_DIM // NUM_HEADS
DEPTH = 12
PATCH_SIZE = 16
IMG_SIZE = 224
GRID = IMG_SIZE // PATCH_SIZE  # 14
LN_EPS = 1e-6


def erf(x):
    """Vectorized erf via Abramowitz & Stegun 7.1.26 (max abs error ~1.5e-7)
    -- avoids a scipy dependency the ARM board may not have installable."""
    sign = np.sign(x)
    x = np.abs(x)
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * np.exp(-x * x)
    return sign * y


def gelu_exact(x):
    """PyTorch's default nn.GELU() (approximate='none'): 0.5*x*(1+erf(x/sqrt(2)))."""
    return 0.5 * x * (1.0 + erf(x / np.sqrt(2.0)))


def layer_norm(x, weight, bias, eps=LN_EPS):
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps) * weight + bias


def linear(x, weight, bias):
    """weight is PyTorch nn.Linear convention: (out_features, in_features)."""
    return x @ weight.T + bias


def patch_embed(img, weight, bias):
    """img: (3, 224, 224) float32. weight: (192, 3, 16, 16). Returns (196, 192)."""
    c, h, w = img.shape
    patches = (img.reshape(c, GRID, PATCH_SIZE, GRID, PATCH_SIZE)
                  .transpose(1, 3, 0, 2, 4)          # (grid_h, grid_w, C, ph, pw)
                  .reshape(GRID * GRID, c * PATCH_SIZE * PATCH_SIZE))
    w_flat = weight.reshape(weight.shape[0], -1)      # (192, 3*16*16)
    return patches @ w_flat.T + bias


def multi_head_attention(x, qkv_w, qkv_b, proj_w, proj_b):
    """x: (N, C). Returns (N, C)."""
    n, c = x.shape
    qkv = linear(x, qkv_w, qkv_b)                      # (N, 3C)
    qkv = qkv.reshape(n, 3, NUM_HEADS, HEAD_DIM).transpose(1, 2, 0, 3)  # (3,H,N,D)
    q, k, v = qkv[0], qkv[1], qkv[2]                    # each (H,N,D)
    scale = HEAD_DIM ** -0.5
    attn = (q @ k.transpose(0, 2, 1)) * scale           # (H,N,N)
    attn = attn - attn.max(axis=-1, keepdims=True)
    attn = np.exp(attn)
    attn = attn / attn.sum(axis=-1, keepdims=True)
    out = attn @ v                                       # (H,N,D)
    out = out.transpose(1, 0, 2).reshape(n, c)           # (N,C)
    return linear(out, proj_w, proj_b)


def vit_forward(img, weights):
    """img: (1,3,224,224) or (3,224,224) float32 preprocessed input.
    weights: dict loaded from vit_tiny_weights.npz.
    Returns (1000,) logits."""
    if img.ndim == 4:
        img = img[0]

    x = patch_embed(img, weights["patch_embed.proj.weight"], weights["patch_embed.proj.bias"])
    cls_token = weights["cls_token"].reshape(1, EMBED_DIM)
    x = np.concatenate([cls_token, x], axis=0)           # (197, 192)
    x = x + weights["pos_embed"][0]

    for i in range(DEPTH):
        p = f"blocks.{i}."
        normed1 = layer_norm(x, weights[p + "norm1.weight"], weights[p + "norm1.bias"])
        attn_out = multi_head_attention(
            normed1,
            weights[p + "attn.qkv.weight"], weights[p + "attn.qkv.bias"],
            weights[p + "attn.proj.weight"], weights[p + "attn.proj.bias"],
        )
        x = x + attn_out

        normed2 = layer_norm(x, weights[p + "norm2.weight"], weights[p + "norm2.bias"])
        h = linear(normed2, weights[p + "mlp.fc1.weight"], weights[p + "mlp.fc1.bias"])
        h = gelu_exact(h)
        h = linear(h, weights[p + "mlp.fc2.weight"], weights[p + "mlp.fc2.bias"])
        x = x + h

    x = layer_norm(x, weights["norm.weight"], weights["norm.bias"])
    cls_out = x[0]
    logits = linear(cls_out, weights["head.weight"], weights["head.bias"])
    return logits
