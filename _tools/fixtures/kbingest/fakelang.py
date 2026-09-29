"""A fake `go`, `cargo`, `dotnet`, `npm`, `tsc` and `npx` for test_kbingest.py: `fakelang TOOL ARGS...` (a shim on PATH
named TOOL runs it).

It answers only the exact argument lists the mappers may run, exits 64 for any other (`dotnet msbuild -target:Build`,
`dotnet msbuild` without `-noAutoResponse`, any `dotnet package list`, `npm ls` without
`--package-lock-only`, any `npx` call), and appends one JSON line per call (arguments, working directory, the environment variables that matter) to the file KB_FAKE_LOG.
KB_FAKE_MODE picks a planted misbehaviour: `fail` (exit 101), `array` (go list prints an array), `garbage` (go list
prints a truncated object after a good one), `outside` (a package directory or a project reference outside the
worktree), `problems` (npm ls prints its tree and exits 1)."""
import json
import os
import sys
from pathlib import Path

tool, args = sys.argv[1], sys.argv[2:]
mode = os.environ.get("KB_FAKE_MODE", "")
here = Path.cwd()
WATCH = ("GOTOOLCHAIN", "GOPROXY", "GOFLAGS", "CARGO_NET_OFFLINE", "RUSTUP_AUTO_INSTALL", "HTTPS_PROXY", "http_proxy",
         "KB_TEST_API_TOKEN", "npm_config_offline", "npm_config_ignore_scripts", "COREPACK_ENABLE_NETWORK",
         "DOTNET_CLI_TELEMETRY_OPTOUT", "DOTNET_NOLOGO", "MSBUILDDISABLENODEREUSE")
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


PROPS = "-getProperty:TargetFrameworkMoniker,LangVersion"
ITEMS = "-getItem:PackageReference,ProjectReference"
PROJECT_EXTS = (".csproj", ".fsproj", ".vbproj")


def msbuild_eval(project):
    """MSBuild's `-getProperty -getItem` JSON for PROJECT, a file of the working directory."""
    if project == "Lib.csproj":
        return {"Properties": {"TargetFrameworkMoniker": ".NETStandard,Version=v2.0", "LangVersion": ""},
                "Items": {"PackageReference": [], "ProjectReference": []}}
    refs = ["..\\..\\..\\other\\Other.csproj"] if mode == "outside" else ["..\\Lib\\Lib.csproj"]
    return {"Properties": {"TargetFrameworkMoniker": ".NETCoreApp,Version=v8.0", "LangVersion": "12.0"},
            "Items": {"PackageReference": [{"Identity": "Newtonsoft.Json", "Version": "13.0.1", "FullPath": "x"},
                                           {"Identity": "Serilog", "Version": "3.1.1"}],
                      "ProjectReference": [{"Identity": r, "FullPath": "y"} for r in refs]}}


def npm_tree():
    tree = {"version": "1.2.0", "name": "web", "dependencies": {
        "express": {"version": "4.19.2", "resolved": "https://registry.example.com/express",
                    "dependencies": {"accepts": {"version": "1.3.8"}}},
        "left-pad": {"version": "1.3.0", "overridden": False}}}
    if mode == "problems":
        tree["problems"] = ["missing: ghost@^1.0.0, required by web@1.2.0"]
    return tree


def tsc_config():
    return {"compilerOptions": {"target": "es2022", "module": "esnext", "moduleResolution": "bundler", "strict": True,
                                "outDir": "./dist"}, "files": ["./src/a.ts"], "include": ["src"]}


def tsc_files():
    lines = [here / "src" / "a.ts", here / "src" / "b.ts", here / "node_modules" / "left-pad" / "index.d.ts",
             Path(sys.executable).parent / "typescript-install" / "lib.es2022.d.ts"]
    return "".join(str(x) + "\n" for x in lines)


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
elif tool == "dotnet" and args == ["--version"]:
    print("10.0.100")
elif (tool == "dotnet" and len(args) == 5 and args[:2] == ["msbuild", "-noAutoResponse"] and args[3:] == [PROPS, ITEMS]
      and args[2].endswith(PROJECT_EXTS) and (here / args[2]).is_file()):
    print(json.dumps(msbuild_eval(args[2]), indent=2))
elif tool == "npm" and args == ["--version"]:
    print("10.8.2")
elif tool == "npm" and args == ["ls", "--all", "--json", "--package-lock-only"] and (here / "package-lock.json").is_file():
    print(json.dumps(npm_tree(), indent=2))
    sys.exit(1 if mode == "problems" else 0)  # npm ls prints the tree, then exits 1 for the problems in it
elif tool == "tsc" and args == ["--version"]:
    print("Version 5.6.2")
elif tool == "tsc" and args == ["--showConfig"] and (here / "tsconfig.json").is_file():
    print(json.dumps(tsc_config(), indent=4))
elif tool == "tsc" and args == ["--listFilesOnly"] and (here / "tsconfig.json").is_file():
    sys.stdout.write(tsc_files())
else:
    sys.stderr.write("fakelang: unexpected arguments: " + " ".join(args) + "\n")
    sys.exit(64)
