import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lib import makemkv, naming

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
raw = makemkv.run_info(idx)

print("=== RAW MakeMKV info ===")
print(raw)
print("\n=== CINFO-picked title ===")
print(repr(naming.pick_cinfo_title(raw)))

print("\n=== Gathered candidates (raw -> cleaned -> noisy?) ===")
cands = naming.gather_raw_title_candidates(raw, drive_label=None, parsed_titles=None)
for src, val in cands:
    clean = naming.clean_title_string(val)
    noisy = naming.is_noisy_title(clean)
    print(f"{src:8} | {val!r} -> {clean!r} | noisy={noisy}")

print("\n=== Scored candidates ===")
scored = naming.score_and_prioritise_candidates(cands)
for cand, score in scored:
    print(f"{score:3}  {cand!r}")

print("\n=== End ===")