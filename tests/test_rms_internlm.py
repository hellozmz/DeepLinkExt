# Copyright (c) 2023, DeepLink.

import torch
import numpy as np
import deeplink_ext.internlm_ops.rms_norm as ext


def test_rms_norm(BaseRmsNorm, DeeplinkRmsNorm, rtol=1e-4, atol=1e-3):
    x_base = torch.randn(5, 5, requires_grad=True).cuda()
    x_base.retain_grad()

    x_intern = x_base.clone()
    x_intern.retain_grad()

    hidden_szie = 5

    model_base = BaseRmsNorm(hidden_szie).cuda()
    out_base = model_base(x_base)
    out_base.backward(torch.ones_like(x_base))
    grad_x_base = x_base.grad.cpu().numpy()

    model_deeplink = DeeplinkRmsNorm(hidden_szie).cuda()
    out_deeplink = model_deeplink(x_intern)
    out_deeplink.backward(torch.ones_like(x_base))
    grad_x_intern = x_intern.grad.cpu().numpy()

    return np.allclose(grad_x_base, grad_x_intern, rtol, atol, True)


print(
    "Test case: normalized_shape == None: grad_inputs closed ? ",
    test_rms_norm(ext.fallback.RMSNorm, ext.DeepLinkRMSNorm),
)
print(
    "Test case: normalized_shape == weight.size(): grad_inputs closed ? ",
    test_rms_norm(ext.fallback.RMSNorm, ext.DeepLinkRMSNormWithNormalizedShape),
)
