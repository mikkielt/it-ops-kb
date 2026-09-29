"""A fake `go` and `cargo` for test_kbingest.py: `fakelang go|cargo ARGS...` (a shim on PATH named go or cargo runs it).

It answers only the exact argument lists the Go and Cargo mappers may run, exits 64 for any other, and appends one
JSON line per call (arguments, working directory, the environment variables that matter) to the file KB_FAKE_LOG.
KB_FAKE_MODE picks a planted misbehaviour: `fail` (exit 101), `array` (go list prints an array), `garbage` (go list
prints a truncated object after a good one), `outside` (a package directory outside the worktree)."""
import json
import os
import sys
from pathlib import Path

tool, args = sys.argv[1], sys.argv[2:]
mode = os.environ.get("KB_FAKE_MODE", "")
here = Path.cwd()
WATCH = ("GOTOOLCHAIN", "GOPROXY", "GOFLAGS", "CARGO_NET_OFFLINE", "HTTPS_PROXY", "http_proxy", "KB_TEST_API_TOKEN")
log = os.environ.get("KB_FAKE_LOG")
if log:
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"tool": tool, "args": args, "cwd": str(here),
                            "env": {k: os.environ.get(k) for k in WATCH}}) + "\n")

GO_MOD = {
    "Module": {"Path": "corp.example.com/app"}, "Go": "1.22", "Toolchain": "go1.22.3",
    "Require": [{"Path": "corp.example.com/lib", "Version": "v1.0.0"},
                {"Path": "example.org/x", "Version": "v0.3.0", "Indirect": True}],
    "Exclude": None, "Replace": None, "Retract": None,
}


def go_pkg(rel, name, imports, **extra):
    return {"Dir": str(here / rel) if rel else str(here), "ImportPath": "corp.example.com/app" + ("/" + rel if rel else ""),
            "Name": name, "GoFiles": ["a.go"], "Imports": imports, "Module": {"Path": "corp.example.com/app", "Main": True},
            "FutureField": {"ignored": True}, **extra}


def go_list():
    pkgs = [go_pkg("", "main", ["fmt", "corp.example.com/app/internal/util"]),
            go_pkg("internal/util", "util", ["strings"]),
            go_pkg("cmd/tool", "main", ["os"]),
            go_pkg("broken", "broken", [], Error={"Err": "broken/b.go:1:1: expected 'package'\nsecond line"})]
    if mode == "outside":
        pkgs.append({"Dir": str(here.parent / "elsewhere"), "ImportPath": "example.org/elsewhere", "Name": "e"})
    if mode == "array":
        return json.dumps(pkgs)
    text = "".join(json.dumps(p, indent="\t") + "\n" for p in pkgs)  # objects with nothing between them
    return text + '{"ImportPath": "corp.example.com/app/tr' if mode == "garbage" else text


def cargo_metadata():
    def member(name, folder, targets, deps):
        return {"name": name, "version": "0.4.0", "id": f"path+file:///{name}#0.4.0",
                "manifest_path": str(here / folder / "Cargo.toml"),
                "targets": targets, "dependencies": [{"name": d, "kind": None, "req": "^1"} for d in deps]}

    def target(kind, name, src):
        return {"kind": [kind], "crate_types": [kind], "name": name, "src_path": str(here / src)}

    return json.dumps({
        "packages": [member("app", ".", [target("bin", "app", "src/main.rs"), target("lib", "app", "src/lib.rs")],
                            ["serde", "anyhow"]),
                     member("core", "crates/core", [target("lib", "core", "crates/core/src/lib.rs")], [])],
        "workspace_members": [], "resolve": None, "workspace_root": str(here), "version": 1,
    })


if mode == "fail" and args[:1] not in (["version"], ["--version"]):
    sys.stderr.write("error: the lock file needs to be updated but --locked was passed\nsecond line\n")
    sys.exit(101)
elif tool == "go" and args == ["version"]:
    print("go version go1.22.3 fake/amd64")
elif tool == "go" and args == ["mod", "edit", "-json"]:
    print(json.dumps(GO_MOD, indent="\t"))
elif tool == "go" and args == ["list", "-e", "-json", "./..."]:
    sys.stdout.write(go_list())
elif tool == "cargo" and args == ["--version"]:
    print("cargo 1.80.0 (fake 2026-01-01)")
elif tool == "cargo" and args == ["metadata", "--format-version", "1", "--no-deps", "--offline", "--locked"]:
    print(cargo_metadata())
else:
    sys.stderr.write("fakelang: unexpected arguments: " + " ".join(args) + "\n")
    sys.exit(64)
