# Copyright (c) 2024, DeepLink.

import torch
import deeplink_ext.cpp_extensions as ext

assert hasattr(ext, "rms_norm")


# 定义自定义的 autograd 函数
class _DeepLinkRMSNormFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, hidden_states, weight, bias, eps):
        output, inv_rms = ext.rms_norm(hidden_states, None, weight, bias, eps)

        ctx.save_for_backward(hidden_states, inv_rms, weight, bias, torch.tensor(eps))
        return output

    @staticmethod
    def backward(ctx, grad_output):
        hidden_states, inv_rms, weight, bias, eps_tensor = ctx.saved_tensors
        eps = eps_tensor.item()
        grad_input, grad_weight, grad_bias = ext.rms_norm_backward(
            hidden_states, grad_output, inv_rms, None, weight, bias, eps
        )
        return grad_input, grad_weight, grad_bias, None


class _DeepLinkRMSNormFunctionWithNormalizedShape(torch.autograd.Function):
    @staticmethod
    def forward(ctx, hidden_states, weight, bias, eps, normalized_shape):
        output, inv_rms = ext.rms_norm(
            hidden_states.float(), normalized_shape, weight.float(), bias.float(), eps
        )
        output = output.half()
        inv_rms = inv_rms.half()
        ctx.save_for_backward(hidden_states, inv_rms, weight, bias, torch.tensor(eps))
        hidden_states = hidden_states.half()
        weight = weight.half()
        bias = bias.half()
        ctx.intermediate_results = normalized_shape
        return output

    @staticmethod
    def backward(ctx, grad_output):
        hidden_states, inv_rms, weight, bias, eps_tensor = ctx.saved_tensors
        eps = eps_tensor.item()
        normalized_shape = ctx.intermediate_results
        hidden_states = hidden_states.float()
        inv_rms = inv_rms.float()
        weight = weight.float()
        bias = bias.float()
        grad_output = grad_output.float()
        grad_input, grad_weight, grad_bias = ext.rms_norm_backward(
            hidden_states, grad_output, inv_rms, normalized_shape, weight, bias, eps
        )
        grad_output = grad_output.half()
        hidden_states = hidden_states.half()
        inv_rms = inv_rms.half()
        weight = weight.half()
        bias = bias.half()
        return grad_input, grad_weight, grad_bias, None, None


# 定义一个 nn.Module 包裹这个自定义函数
class DeepLinkRMSNorm(torch.nn.Module):
    def __init__(self, hidden_size, eps=1e-6):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(hidden_size))
        self.bias = torch.zeros(hidden_size).cuda()
        self.variance_epsilon = eps

    def forward(self, hidden_states):
        return _DeepLinkRMSNormFunction.apply(
            hidden_states, self.weight, self.bias, self.variance_epsilon
        )


class DeepLinkRMSNormWithNormalizedShape(torch.nn.Module):
    def __init__(self, hidden_size, eps=1e-6):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(hidden_size))
        self.bias = torch.zeros(hidden_size).cuda()
        self.variance_epsilon = eps

    def forward(self, hidden_states):
        return _DeepLinkRMSNormFunctionWithNormalizedShape.apply(
            hidden_states,
            self.weight,
            self.bias,
            self.variance_epsilon,
            self.weight.size(),
        )
