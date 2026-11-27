import os
import torch
from transformers import WhisperConfig, WhisperForConditionalGeneration, WhisperProcessor


def convert_openai_whisper_to_hf(pt_path: str, out_dir: str):
    print(f"Loading OpenAI Whisper checkpoint: {pt_path}")
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=True)
    dims = ckpt["dims"]
    orig_state = ckpt["model_state_dict"]

    config = WhisperConfig(
        vocab_size=dims["n_vocab"],
        d_model=dims["n_audio_state"],
        encoder_layers=dims["n_audio_layer"],
        encoder_attention_heads=dims["n_audio_head"],
        encoder_ffn_dim=dims["n_audio_state"] * 4,
        decoder_layers=dims["n_text_layer"],
        decoder_attention_heads=dims["n_text_head"],
        decoder_ffn_dim=dims["n_text_state"] * 4,
        num_mel_bins=dims["n_mels"],
        max_source_positions=dims["n_audio_ctx"],
        max_target_positions=dims["n_text_ctx"],
        suppress_tokens=[],
    )

    hf_state = {}
    for k, v in orig_state.items():
        new_k = k
        if new_k == "encoder.positional_embedding":
            new_k = "model.encoder.embed_positions.weight"
        elif new_k == "decoder.positional_embedding":
            new_k = "model.decoder.embed_positions.weight"
        elif new_k == "decoder.token_embedding.weight":
            new_k = "model.decoder.embed_tokens.weight"
        elif new_k == "encoder.ln_post.weight":
            new_k = "model.encoder.layer_norm.weight"
        elif new_k == "encoder.ln_post.bias":
            new_k = "model.encoder.layer_norm.bias"
        elif new_k == "decoder.ln.weight":
            new_k = "model.decoder.layer_norm.weight"
        elif new_k == "decoder.ln.bias":
            new_k = "model.decoder.layer_norm.bias"
        else:
            new_k = "model." + new_k
            new_k = new_k.replace(".blocks.", ".layers.")
            new_k = new_k.replace(".attn.query.", ".self_attn.q_proj.")
            new_k = new_k.replace(".attn.key.", ".self_attn.k_proj.")
            new_k = new_k.replace(".attn.value.", ".self_attn.v_proj.")
            new_k = new_k.replace(".attn.out.", ".self_attn.out_proj.")
            new_k = new_k.replace(".attn_ln.", ".self_attn_layer_norm.")
            new_k = new_k.replace(".cross_attn.query.", ".encoder_attn.q_proj.")
            new_k = new_k.replace(".cross_attn.key.", ".encoder_attn.k_proj.")
            new_k = new_k.replace(".cross_attn.value.", ".encoder_attn.v_proj.")
            new_k = new_k.replace(".cross_attn.out.", ".encoder_attn.out_proj.")
            new_k = new_k.replace(".cross_attn_ln.", ".encoder_attn_layer_norm.")
            new_k = new_k.replace(".mlp.0.", ".fc1.")
            new_k = new_k.replace(".mlp.2.", ".fc2.")
            new_k = new_k.replace(".mlp_ln.", ".final_layer_norm.")

        hf_state[new_k] = v

    # Tie proj_out.weight to embed_tokens.weight
    hf_state["proj_out.weight"] = hf_state["model.decoder.embed_tokens.weight"]

    model = WhisperForConditionalGeneration(config)
    missing, unexpected = model.load_state_dict(hf_state, strict=False)
    print(f"Loaded state_dict. Missing: {missing}, Unexpected: {unexpected}")

    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)

    # Save processor/tokenizer from openai/whisper-base metadata
    processor = WhisperProcessor.from_pretrained("openai/whisper-base")
    processor.save_pretrained(out_dir)
    print(f"Successfully saved HuggingFace Whisper-Base model & processor to: {out_dir}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pt_file = os.path.join(base_dir, "models", "base.pt")
    out_folder = os.path.join(base_dir, "models", "whisper-base-hf")
    convert_openai_whisper_to_hf(pt_file, out_folder)
