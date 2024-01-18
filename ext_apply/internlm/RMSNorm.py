import torch
from torch import nn
import torch_dipu
import dipu_ext.ext_ as deeplink_ext
import copy


class InternLMRMSNorm(nn.Module):
    def __init__(self, hidden_size, eps=1e-6):
        """
        InternLMRMSNorm is equivalent to T5LayerNorm
        """
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.variance_epsilon = eps

    def forward(self, hidden_states):
        variance = hidden_states.to(torch.float32).pow(2).mean(-1, keepdim=True)
        hidden_states = hidden_states * torch.rsqrt(variance + self.variance_epsilon)

        # convert into half-precision if necessary
        if self.weight.dtype in [torch.float16, torch.bfloat16]:
            hidden_states = hidden_states.to(self.weight.dtype)

        return self.weight * hidden_states


# 定义自定义的autograd函数
class _DeeplinkRMSNormFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, hidden_states, weight, bias, eps):
        output, inv_rms = deeplink_ext.rms_norm(
            hidden_states,
            None,
            weight,
            bias,
            eps
        )

        ctx.save_for_backward(hidden_states, inv_rms, weight, bias, torch.tensor(eps))
        return output

    @staticmethod
    def backward(ctx, grad_output):
        hidden_states, inv_rms, weight, bias, eps_tensor = ctx.saved_tensors
        eps = eps_tensor.item()
        grad_input, *others = deeplink_ext.rms_norm_backward(
            hidden_states,
            grad_output,
            inv_rms,
            None,
            weight,
            bias,
            eps
        )
        if isinstance(others, (list, tuple)) and len(others) == 2:
            grad_weight, grad_bias = others
        else:
            grad_weight, grad_bias = others[0], None
        return grad_input, grad_weight, grad_bias, None
    
class _DeeplinkRMSNormFunction_WithNormalizedShape(torch.autograd.Function):
    @staticmethod
    def forward(ctx, hidden_states, weight, bias, eps, normalized_shape):
        output, inv_rms = deeplink_ext.rms_norm(
            hidden_states.float(),
            normalized_shape,
            weight.float(),
            bias.float(),
            eps
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
        grad_input, *others = deeplink_ext.rms_norm_backward(
            hidden_states,
            grad_output,
            inv_rms,
            normalized_shape,
            weight,
            bias,
            eps
        )
        if isinstance(others, (tuple, list)) and len(others) == 2:
            grad_weight, grad_bias = others
        else:
            grad_weight = others[0]
            grad_bias = None

        grad_output = grad_output.half()
        hidden_states = hidden_states.half()
        inv_rms = inv_rms.half()
        weight = weight.half()
        bias = bias.half()
        return grad_input, grad_weight, grad_bias, None, None


# 定义一个nn.Module包裹这个自定义函数
class DeeplinkRMSNorm(nn.Module):

    def __init__(self, hidden_size, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.bias = torch.zeros(hidden_size).cuda()
        self.variance_epsilon = eps

    def forward(self, hidden_states):
        return _DeeplinkRMSNormFunction.apply(hidden_states, self.weight, self.bias, self.variance_epsilon)
    
class DeeplinkRMSNorm_WithNormalizedShape(nn.Module):

    def __init__(self, hidden_size, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.bias = torch.zeros(hidden_size).cuda()
        self.variance_epsilon = eps

    def forward(self, hidden_states):
        return _DeeplinkRMSNormFunction_WithNormalizedShape.apply(hidden_states, self.weight, self.bias, self.variance_epsilon, self.weight.size())
