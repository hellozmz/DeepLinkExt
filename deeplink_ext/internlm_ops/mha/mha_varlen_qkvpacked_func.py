# Copyright (c) 2023, DeepLink.

import torch
import deeplink_ext.cpp_extensions as ext

assert hasattr(ext, "mha_varlen_fwd") and hasattr(ext, "mha_varlen_bwd")


class DeepLinkMultiHeadAttentionVarLenQKVPackedFunc(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx,
        qkv,
        cu_seqlens,
        max_seqlen,
        dropout_p,
        softmax_scale,
        causal,
        return_softmax,
    ):
        if softmax_scale is None:
            softmax_scale = qkv.shape[-1] ** (-0.5)
        out, softmax_lse, rng, S_dmask = ext.mha_varlen_fwd(
            qkv[:, 0],
            qkv[:, 1],
            qkv[:, 2],
            cu_seqlens,
            cu_seqlens,
            max_seqlen,
            max_seqlen,
            dropout_p,
            causal,
            return_softmax and dropout_p > 0,
            softmax_scale,
        )
        ctx.save_for_backward(qkv, out, softmax_lse, cu_seqlens, rng.get_state())
        ctx.dropout_p = dropout_p
        ctx.max_seqlen = max_seqlen
        ctx.softmax_scale = softmax_scale
        ctx.causal = causal
        return out if not return_softmax else (out, softmax_lse, S_dmask)

    @staticmethod
    def backward(ctx, dout):
        qkv, out, softmax_lse, cu_seqlens, rng_state = ctx.saved_tensors
        dqkv = torch.empty_like(qkv)
        rng = torch.Generator(device=qkv.device)
        rng.set_state(rng_state)
        ext.mha_varlen_bwd(
            dout,
            qkv[:, 0],
            qkv[:, 1],
            qkv[:, 2],
            out,
            softmax_lse,
            cu_seqlens,
            cu_seqlens,
            ctx.max_seqlen,
            ctx.max_seqlen,
            ctx.dropout_p,
            ctx.causal,
            rng,
            ctx.softmax_scale,
            dqkv[:, 0],
            dqkv[:, 1],
            dqkv[:, 2],
        )
        return dqkv, None, None, None, None, None, None, None, None
