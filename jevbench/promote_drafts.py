"""Move validated drafts from data/drafts/ into data/ (only after the user signs off the GT).
  python -m jevbench.promote_drafts --yes-gt-validated"""
import argparse
import shutil

from .battery import DATA

FILES = ["adversarial3_cases.json", "triage_ext_cases.json", "adversarial4_cases.json", "adversarial5_cases.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes-gt-validated", action="store_true", required=True)
    ap.parse_args()
    for f in FILES:
        src, dst = DATA / "drafts" / f, DATA / f
        if dst.exists():
            print(f"{f}: already promoted, skipping")
            continue
        shutil.copy2(src, dst)
        print(f"{f}: promoted")


if __name__ == "__main__":
    main()
