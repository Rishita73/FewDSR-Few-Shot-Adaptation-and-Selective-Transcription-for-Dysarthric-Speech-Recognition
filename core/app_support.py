"""Pure helpers for the dashboard (no streamlit import) so they can be unit-tested."""
from __future__ import annotations
import glob, importlib.util, json, os, re
from typing import Dict, List, Optional, Tuple


def load_summary(results_dir: str) -> Optional[dict]:
    p = os.path.join(results_dir, "summary.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def torch_available() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def adapter_options(adapters_dir: str) -> List[str]:
    """Adapter directory names that actually contain adapter weights/config."""
    out = []
    for d in sorted(glob.glob(os.path.join(adapters_dir, "*"))):
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "adapter_config.json")):
            out.append(os.path.basename(d))
    return out


def condition_for_adapter(name: Optional[str]) -> str:
    """'F04_K10' -> 'lora_K10'; None (zero-shot) -> 'baseline'."""
    if not name:
        return "baseline"
    m = re.search(r"_K(\d+)$", name)
    if not m:
        raise ValueError(f"adapter name {name!r} does not end in _K<number>")
    return f"lora_K{m.group(1)}"


def params_for(summary: Optional[dict], condition: str) -> Tuple[Optional[Dict[str, float]], str]:
    """(params, message). params = {'T','gamma','tau'} fitted on pooled VALIDATION words, or None."""
    if summary is None:
        return None, "No results/summary.json yet: only unfitted default parameters are available."
    dp = (summary.get("deploy_params") or {}).get(condition)
    if not dp:
        return None, f"No fitted parameters for condition '{condition}' in summary.json."
    if any(dp.get(k) is None for k in ("T", "gamma", "tau")):
        return None, f"Fitted parameters for '{condition}' are incomplete."
    tau = dp["tau"]
    return {"T": float(dp["T"]), "gamma": float(dp["gamma"]), "tau": float(tau)}, \
        f"T, gamma, tau fitted on pooled validation words of all evaluated speakers ({condition})."


def test_utterances(manifest_path: str, speaker: str, n_val: int = 10, max_test: int = 100, limit: int = 50):
    """Test-split utterances of a speaker, built with the SAME splitter as the experiments."""
    from core import data as D
    from experiments import common as C
    utts = D.load_manifest(manifest_path)
    return C.speaker_splits(utts, speaker, n_val, max_test)[0].test[:limit]
