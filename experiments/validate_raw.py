"""Validate results/raw/*.jsonl against docs/CONTRACTS.md.
python -m experiments.validate_raw results/raw     (exit code 1 on any error)"""
import glob, math, os, re, sys
from collections import defaultdict
from experiments import common as C

REQ = ["speaker", "k", "condition", "split", "wav", "ref", "hyp", "audio_s", "latency_s", "words"]
NAME = re.compile(r"^(?P<spk>.+)_K(?P<k>\d+)_(?P<cond>baseline|lora)\.jsonl$")


def validate_file(path, topk=C.TOPK):
    errs, stats = [], {"words": 0, "override": 0}
    m = NAME.match(os.path.basename(path))
    if not m:
        return [f"{path}: filename must be <spk>_K<k>_<baseline|lora>.jsonl"], stats
    try:
        recs = C.read_jsonl(path)
    except Exception as e:
        return [f"{path}: unreadable ({e})"], stats
    if not recs:
        errs.append(f"{path}: empty")
    for i, r in enumerate(recs):
        tag = f"{os.path.basename(path)}[{i}]"
        miss = [k for k in REQ if k not in r]
        if miss:
            errs.append(f"{tag}: missing keys {miss}"); continue
        if r["speaker"] != m["spk"] or r["k"] != int(m["k"]) or r["condition"] != m["cond"]:
            errs.append(f"{tag}: speaker/k/condition disagree with filename")
        if (r["condition"] == "baseline") != (r["k"] == 0):
            errs.append(f"{tag}: baseline <=> K=0 violated")
        if r["split"] not in ("val", "test"):
            errs.append(f"{tag}: bad split {r['split']!r}")
        for key in ("audio_s", "latency_s"):
            if not isinstance(r[key], (int, float)) or not math.isfinite(r[key]) or r[key] < 0:
                errs.append(f"{tag}: bad {key}")
        for j, w in enumerate(r["words"]):
            z = w.get("topk_logits")
            if not isinstance(z, list) or len(z) != topk:
                errs.append(f"{tag}.words[{j}]: topk_logits must have {topk} entries"); continue
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in z):
                errs.append(f"{tag}.words[{j}]: non-finite logit"); continue
            if any(z[a] < z[a + 1] for a in range(1, topk - 1)):
                errs.append(f"{tag}.words[{j}]: entries 1..K-1 must be descending")
            nl = w.get("null_logit")
            if not isinstance(nl, (int, float)) or not math.isfinite(nl):
                errs.append(f"{tag}.words[{j}]: null_logit must be finite (raw logits, not suppressed scores)")
            stats["words"] += 1
            stats["override"] += int(z[0] < z[1])
        if " ".join(w["word"] for w in r["words"]) != r["hyp"]:
            errs.append(f"{tag}: hyp != join(words)")
    return errs, stats


def validate_dir(d):
    files = sorted(glob.glob(os.path.join(d, "*.jsonl")))
    errs, tot = [], {"words": 0, "override": 0}
    if not files:
        return ["no .jsonl files found"], tot
    tests = defaultdict(dict)
    for f in files:
        e, s = validate_file(f)
        errs += e
        tot["words"] += s["words"]; tot["override"] += s["override"]
        if not e:
            recs = C.read_jsonl(f)
            for split in ("val", "test"):
                tests[(recs[0]["speaker"], split)][os.path.basename(f)] = sorted(r["wav"] for r in recs if r["split"] == split)
    for (spk, split), per in tests.items():            # identical val/test sets across conditions
        ref = next(iter(per.values()))
        for name, wavs in per.items():
            if wavs != ref:
                errs.append(f"{spk}: {split} set of {name} differs from other conditions")
    return errs, tot


def main(argv=None):
    d = (argv or sys.argv[1:] or ["results/raw"])[0]
    errs, tot = validate_dir(d)
    if tot["words"]:
        print(f"{tot['words']} words checked; emitted token != raw argmax for "
              f"{tot['override']} ({100 * tot['override'] / tot['words']:.2f}%)")
    for e in errs[:50]:
        print("ERROR", e)
    print("VALID" if not errs else f"{len(errs)} problem(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
