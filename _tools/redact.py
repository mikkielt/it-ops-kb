#!/usr/bin/env python3
"""Redaction for the query log: identifier shapes to kb placeholders, before and after Haiku (stdlib only).

A stub: kb/_self/querylog.md (Redaction) is the design, and the Query log items of kb/_self/work-left.md build it.
Until then every call prints this text and exits 2; -h prints it and exits 0.
"""
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
