"""Run on a machine with torch+peft+transformers:  python -m experiments.check_lora
Prints the wrapped modules and the MEASURED trainable-parameter percentage."""
from transformers import WhisperForConditionalGeneration
from core.lora import build_lora_model, count_trainable
from fewdsr_config import CFG

base = WhisperForConditionalGeneration.from_pretrained(CFG.base_model)
model = build_lora_model(base)                      # raises if not exactly 2 x decoder_layers cross-attn modules
from peft.tuners.lora import LoraLayer
names = [n for n, m in model.named_modules() if isinstance(m, LoraLayer)]
print(f"{len(names)} LoRA-wrapped modules, e.g.:"); [print("  ", n) for n in names[:4]]
tr, tot, pct = count_trainable(model)
print(f"trainable {tr:,} / total {tot:,} = {pct:.4f} %   (synopsis claimed <0.02 %; arithmetic predicts ~0.12 %)")
assert all(("lora_" in n) for n, p in model.named_parameters() if p.requires_grad), "non-LoRA param is trainable!"
print("OK: only LoRA params are trainable")
