#!/usr/bin/env python3
"""Stress and robustness tests of the kb tools: runs test_stress.py with pytest (see tests.py). Exit 1 on any failure.

  stress_test.py                 run every case (throwaway copies of the kb; the kb itself is never modified)
  stress_test.py --scale 20      the corpus-scaling case searches a corpus copied 20 times (default 5; KB_STRESS_SCALE)
  stress_test.py -k search       run only cases whose name matches (pytest -k)
"""
import argparse, os, sys

import tests


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=int, default=5, help="corpus multiplier for the scaling case (default 5)")
    ap.add_argument("-k", dest="filter", default="", help="run only cases whose name matches (pytest -k)")
    a, rest = ap.parse_known_args()
    args = [os.path.join(tests.TOOLS, "test_stress.py"), "-m", "stress"] + (["-k", a.filter] if a.filter else []) + rest
    return tests.run_pytest(args, {"KB_STRESS_SCALE": str(a.scale)}, dist="load")  # independent cases: spread them all


if __name__ == "__main__":
    sys.exit(main())
