# Copyright (c) 2023, DeepLink.

import torch
import deeplink_ext.cpp_extensions as ext

assert hasattr(ext, "mha_fwd") and hasattr(ext, "mha_bwd")


class DeepLinkMultiHeadAttentionQKVPackedFunc(torch.autograd.Function):
    @staticmethod
    def forward(ctx, qkv, dropout_p, softmax_scale, causal, return_softmax):
        if softmax_scale is None:
            softmax_scale = qkv.shape[-1] ** (-0.5)
        out, softmax_lse, rng, S_dmask = ext.mha_fwd(
            qkv[:, :, 0],
            qkv[:, :, 1],
            qkv[:, :, 2],
            dropout_p,
            causal,
            return_softmax and dropout_p > 0,
            softmax_scale,
        )
        ctx.save_for_backward(qkv, out, softmax_lse, rng.get_state())
        ctx.dropout_p = dropout_p
        ctx.softmax_scale = softmax_scale
        ctx.causal = causal
        return out if not return_softmax else (out, softmax_lse, S_dmask)

    @staticmethod
    def backward(ctx, dout):
        qkv, out, softmax_lse, rng_state = ctx.saved_tensors
        dqkv = torch.empty_like(qkv)
        rng = torch.Generator(device=qkv.device)
        rng.set_state(rng_state)
        ext.mha_bwd(
            dout,
            qkv[:, :, 0],
            qkv[:, :, 1],
            qkv[:, :, 2],
            out,
            softmax_lse,
            ctx.dropout_p,
            ctx.causal,
            rng,
            ctx.softmax_scale,
            dqkv[:, :, 0],
            dqkv[:, :, 1],
            dqkv[:, :, 2],
        )
        return dqkv, None, None, None, None
