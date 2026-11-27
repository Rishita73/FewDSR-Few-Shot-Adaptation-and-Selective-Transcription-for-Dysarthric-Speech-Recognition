"""Build data/manifest.json from the Hugging Face dataset `abnerh/TORGO-database`
(short words + restricted sentences only; fields: audio, transcription, speech_status, gender, duration).

    python -m experiments.prepare_data_hf --wav-dir /content/torgo_wav --out data/manifest.json [--mic headMic]

* Speaker / session / mic are parsed from the file name  <speaker>_<session>_<mic>_<utt>.wav
  (speaker like F04, M01 for dysarthric, FC01/MC01 for controls).
* Audio is NOT decoded: the stored wav bytes are written straight to --wav-dir, so no torchcodec/ffmpeg is needed.
* Controls are skipped by default (adapters are only meaningful for dysarthric speakers).
* The manifest has exactly the same format as experiments.prepare_data, so every later step is unchanged.
* This dataset contains no non-word or unrestricted-sentence prompts; many prompts are single words and are
  repeated heavily, so some K budgets will be infeasible for some speakers (reported, never faked)."""
from __future__ import annotations
import argparse, collections, os, re
from typing import Iterable, List, Optional, Sequence

from core import data as D
from core.metrics import normalize_text
from experiments.common import feasible_budgets
from fewdsr_config import CFG

NAME = re.compile(r"^(?P<spk>[FM]C?\d{2})_(?P<sess>\d+)_(?P<mic>headMic|arrayMic)_(?P<utt>\d+)\.wav$", re.I)


def rows_to_manifest(rows: Iterable[dict], wav_dir: str, mic: str = "headMic", include_controls: bool = False,
                     speakers: Optional[Sequence[str]] = None, limit: Optional[int] = None):
    """rows: dicts with audio={'path': filename, 'bytes': wav bytes} and transcription=str.
    Returns (utts, stats). Writes the wav files."""
    want = {s.upper() for s in speakers} if speakers else None
    utts: List[D.Utt] = []
    st = collections.Counter()
    for ex in rows:
        a = ex["audio"]
        fn = os.path.basename(a.get("path") or "")
        m = NAME.match(fn)
        if not m:
            st["skipped_unparseable_name"] += 1
            if not fn:
                raise ValueError("a row has no audio path: cannot recover the speaker (dataset version changed?)")
            continue
        spk, sess, rmic = m["spk"].upper(), m["sess"], m["mic"]
        is_ctl = spk.startswith("FC") or spk.startswith("MC")
        if rmic.lower() != mic.lower():
            st["skipped_other_mic"] += 1; continue
        if is_ctl and not include_controls:
            st["skipped_control"] += 1; continue
        if want and spk not in want:
            st["skipped_other_speaker"] += 1; continue
        text = (ex.get("transcription") or "").strip()
        if not D._usable_prompt(text):
            st["skipped_unusable_prompt"] += 1; continue
        if not a.get("bytes"):
            st["skipped_no_audio_bytes"] += 1; continue
        sdir = os.path.join(wav_dir, spk, f"Session{sess}", rmic)
        os.makedirs(sdir, exist_ok=True)
        path = os.path.join(sdir, fn)
        with open(path, "wb") as f:
            f.write(a["bytes"])
        sev = "control" if is_ctl else CFG.torgo_severity.get(spk, "unknown")
        utts.append(D.Utt(spk, f"Session{sess}", path, text, is_ctl, sev, rmic))
        st["kept"] += 1
        if limit and len(utts) >= limit:
            break
    return utts, st


def main(argv=None, rows=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="abnerh/TORGO-database")
    ap.add_argument("--wav-dir", default="/content/torgo_wav", help="where wav files are written (local disk is faster than Drive)")
    ap.add_argument("--out", default="data/manifest.json")
    ap.add_argument("--mic", default="headMic", choices=["headMic", "arrayMic"])
    ap.add_argument("--speakers", nargs="*")
    ap.add_argument("--include-controls", action="store_true")
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None, help="smoke runs only")
    a = ap.parse_args(argv)
    if rows is None:
        from datasets import Audio, load_dataset
        ds = load_dataset(a.dataset, split="train").cast_column("audio", Audio(decode=False))
        rows = ds
    utts, st = rows_to_manifest(rows, a.wav_dir, a.mic, a.include_controls, a.speakers, a.limit)
    print(dict(st))
    if not utts:
        raise SystemExit("No usable utterances. Check --mic / --speakers (speaker ids look like F04, M01).")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    D.save_manifest(utts, a.out)
    by = collections.defaultdict(list)
    for u in utts:
        by[u.speaker].append(u)
    print(f"{'speaker':8} {'severity':9} {'utts':>6} {'unique prompts':>15}  feasible K")
    for spk, L in sorted(by.items()):
        uniq = len({normalize_text(u.text) for u in L})
        print(f"{spk:8} {L[0].severity:9} {len(L):6d} {uniq:15d}  {feasible_budgets(utts, spk, a.n_val)}")
    print(f"saved {len(utts)} utterances -> {a.out}")
    return utts


if __name__ == "__main__":
    main()
