import math
import torch
import torch.nn as nn


class LoRALinear(nn.Module):
    """
    Low-Rank Adaptation (LoRA) linear layer:
        W = W0 + (alpha / r) * (B @ A)
    Freezes the pre-trained base weight W0 and trains only low-rank matrices A and B.
    """
    def __init__(self, base_layer: nn.Linear, r: int = 8, alpha: int = 16):
        super().__init__()
        self.base_layer = base_layer
        self.r = r
        self.alpha = alpha
        self.scaling = alpha / r

        # Freeze pre-trained weights
        for param in self.base_layer.parameters():
            param.requires_grad = False

        in_features = base_layer.in_features
        out_features = base_layer.out_features

        # Low-rank trainable matrices
        self.lora_A = nn.Parameter(torch.empty(r, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, r))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = self.base_layer(x)
        lora_out = (x @ self.lora_A.t() @ self.lora_B.t()) * self.scaling
        return base_out + lora_out


def inject_cross_attention_lora(model, r: int = 8, alpha: int = 16):
    """
    Freezes all parameters of Whisper and injects LoRA adapters strictly into
    the decoder cross-attention (encoder_attn) Query and Value projections.
    """
    # 1. Freeze entire base model
    for param in model.parameters():
        param.requires_grad = False

    # 2. Inject LoRA into decoder cross-attention q_proj and v_proj
    injected_layers = 0
    for layer in model.model.decoder.layers:
        if hasattr(layer, "encoder_attn"):
            if isinstance(layer.encoder_attn.q_proj, nn.Linear):
                layer.encoder_attn.q_proj = LoRALinear(layer.encoder_attn.q_proj, r=r, alpha=alpha)
                injected_layers += 1
            if isinstance(layer.encoder_attn.v_proj, nn.Linear):
                layer.encoder_attn.v_proj = LoRALinear(layer.encoder_attn.v_proj, r=r, alpha=alpha)
                injected_layers += 1

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params = total_params - trainable_params
    trainable_pct = (trainable_params / total_params) * 100.0 if total_params > 0 else 0.0

    return {
        "injected_projections": injected_layers,
        "rank_r": r,
        "alpha": alpha,
        "total_params": total_params,
        "trainable_params": trainable_params,
        "frozen_params": frozen_params,
        "trainable_pct": round(trainable_pct, 4),
    }


def reset_lora_weights(model):
    """Resets LoRA B matrices to zero (restoring exact zero-shot Whisper behavior)."""
    for module in model.modules():
        if isinstance(module, LoRALinear):
            nn.init.zeros_(module.lora_B)
