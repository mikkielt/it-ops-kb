"""A fake toolchain for test_kbingest.py: `fakemap STEP` behaves as the step says (a shim on PATH runs it)."""
import json, os, sys, time

step = sys.argv[1] if len(sys.argv) > 1 else ""
if step == "--version":
    print("fakemap 1.2.3 (fake toolchain)")
elif step == "list":
    print(json.dumps({
        "packages": [{"name": "app", "path": "src"}],
        "imports": {"src/a.fake": ["y", "x", "x"], "src/b.fake": []},
        "entry_points": [{"path": "src/a.fake", "kind": "main", "name": "app"}],
        "future_field": {"ignored": True},
    }))
elif step == "sleep":
    time.sleep(60)
elif step == "garbage":
    print("this is { not json")
elif step == "fail":
    sys.stderr.write("boom: cannot read the project\nsecond line\n")
    sys.exit(3)
elif step == "env":
    keys = ("HTTPS_PROXY", "http_proxy", "GOTOOLCHAIN", "GOPROXY", "CARGO_NET_OFFLINE", "npm_config_offline",
            "KB_TEST_API_TOKEN", "KB_TEST_KEEP")
    print(json.dumps({"env": {k: os.environ.get(k) for k in keys},
                      "files": sorted(n for n in os.listdir(".") if not n.startswith(".git"))}))
else:
    sys.exit(64)
