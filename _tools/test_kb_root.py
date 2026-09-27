#!/usr/bin/env python3
"""KB_ROOT: the tools serve a second kb with the same layout (a team's own facts, never committed here).

A tiny kb in a temporary directory is built, checked and searched with KB_ROOT set; it answers its own question and
not it-ops-kb's; kb_status and the server's texts name it; and its index shares CLAUDE_PLUGIN_DATA with this
repository's without either pruning the other's file.
"""
import csv, glob, json, os, subprocess, sys

import kbcommon, kbid
from conftest import KB, TOOLS

URL = "https://docs.example.com/print/queue-retention"
SID = kbid.source_id(URL)
ARTICLE = f"""---
topic: team/print-queues
priority: P1
applies_to: "PL-SRV-0042 print servers"
retrieved_utc: 2026-09-26
sources: [{SID}]
status: complete
---

# Print queue retention on the team's print servers

## Summary
How long the team's print servers keep finished jobs.

## Facts
- Finished print jobs are kept for 14 days on the spooler of PL-SRV-0042, then purged by a nightly task. [DOC {SID}]
- Queue names follow the pattern `PQ-<floor>-<room>`. [DOC {SID}]

## Reference

## Examples
"""


FILLER = [("badge-readers", "Badge readers at the lobby log every swipe to the access controller for 90 days."),
          ("meeting-rooms", "Meeting room displays reboot every Sunday at 03:00 to apply firmware."),
          ("vpn-profiles", "The VPN profile uses split tunnelling for the corporate subnets only."),
          ("backup-windows", "File server backups run between 22:00 and 04:00 with a weekly full copy."),
          ("desk-phones", "Desk phones take their extension from the switch port's voice VLAN."),
          ("guest-wifi", "Guest wifi vouchers expire after eight hours and allow two devices.")]


def make_kb(root):
    """One article to find and six unrelated ones: the verdict counts a word as key only when under a fifth of the
    kb's lines hold it, so a kb of a single article can never be `good`."""
    os.makedirs(os.path.join(root, "team"))
    with open(os.path.join(root, "team", "print-queues.md"), "w", encoding="utf-8") as f:
        f.write(ARTICLE)
    for slug, fact in FILLER:
        text = ARTICLE.split("# Print")[0].replace("team/print-queues", f"team/{slug}").replace("PL-SRV-0042 print servers", "the office")
        with open(os.path.join(root, "team", f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write(f"{text}# {slug.replace('-', ' ').capitalize()}\n\n## Summary\nOffice notes.\n\n## Facts\n- {fact} [DOC {SID}]\n")
    with open(os.path.join(root, "_sources.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "url", "title", "publisher", "licence", "retrieved_utc", "version_or_date", "artifact_sha256",
                    "used_in", "superseded_by"])
        w.writerow([SID, URL, "Print queue retention", "corp.example.com", "internal", "2026-09-26", "", "", "", ""])
    files = {"_artifacts.csv": "path,source_id,sha256,zip_member\n", "_answers.md": "# Answers\n",
             "_gaps.md": "# Gaps\n", "_conflicts.md": "# Conflicts\n",
             "README.md": "# team kb\n\n<!-- coverage:start -->\n<!-- coverage:end -->\n"}
    for name, text in files.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write(text)


def run(tool, *args, root=None, data=None):
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOT", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    if root:
        env["KB_ROOT"] = root
    if data:
        env["CLAUDE_PLUGIN_DATA"] = data
    else:
        env["KB_INDEX"] = "0"
    p = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True, cwd=KB,
                       env=env, timeout=120)
    return p.returncode, p.stdout + p.stderr


def test_second_kb_is_built_checked_and_searched(tmp_path):
    root = str(tmp_path / "team-kb")
    make_kb(root)
    code, out = run("build_index.py", root=root)
    assert code == 0 and "topics=7" in out, out
    assert run("build_index.py", "--check", root=root)[0] == 0
    with open(os.path.join(root, "_sources.csv"), encoding="utf-8") as f:
        assert "team/print-queues.md" in f.read(), "used_in is generated for the second kb"
    code, out = run("check.py", root=root)
    assert code == 0 and "errors=0" in out, out

    code, out = run("rag.py", "pack", "How long are finished print jobs kept on the spooler?", root=root)
    assert out.startswith("coverage: good") and "team/print-queues.md:" in out and URL in out, out
    code, out = run("rag.py", "pack", "What is the default Windows LAPS password length?", root=root)
    assert out.startswith("coverage: none"), "the second kb holds only its own facts: " + out[:300]

    code, out = run("kb_mcp.py", "--status", root=root)
    assert f"kb_root: {os.path.abspath(root)}" in out and "topics: 7" in out, out
    code, out = run("kb_mcp.py", "--status")
    assert f"kb_root: {kbcommon.PUBLIC}" in out, "without KB_ROOT the tools serve this repository's public root: " + out


def test_server_texts_name_the_second_kb(tmp_path):
    root = str(tmp_path / "team-kb")
    make_kb(root)
    code = ("import json, kb_mcp; print(json.dumps([kb_mcp.INSTRUCTIONS, kb_mcp.server_info()['title'], "
            "[t['description'] for t in kb_mcp.TOOL_LIST]]))")
    env = {**os.environ, "KB_ROOT": root}
    p = subprocess.run([sys.executable, "-c", code], cwd=TOOLS, capture_output=True, text=True, env=env, timeout=60)
    instructions, title, descriptions = json.loads(p.stdout)
    assert instructions.startswith("A kb with it-ops-kb's layout at ") and "Call kb_pack" in instructions
    assert "Windows endpoint management" not in instructions, "it-ops-kb's domain list does not describe a team kb"
    assert "(KB_ROOT)" in title
    assert all(d.startswith(f"Documentation facts from the kb at {os.path.abspath(root)}") for d in descriptions)


def test_index_files_of_two_roots_share_a_directory(tmp_path):
    root, data = str(tmp_path / "team-kb"), str(tmp_path / "plugin-data")
    make_kb(root)
    os.makedirs(data)
    q = "print job retention"
    run("rag.py", "pack", q, root=root, data=data)
    run("rag.py", "pack", q, data=data)
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(data, "kbindex-*.sqlite")))
    assert len(names) == 2 and sum(n.startswith("kbindex-r") for n in names) == 1, names
    with open(os.path.join(root, "team", "print-queues.md"), "a", encoding="utf-8") as f:
        f.write("\n")  # a new fingerprint: the second kb rebuilds and prunes only its own old file
    run("rag.py", "pack", q, root=root, data=data)
    after = sorted(os.path.basename(p) for p in glob.glob(os.path.join(data, "kbindex-*.sqlite")))
    assert len(after) == 2 and [n for n in names if not n.startswith("kbindex-r")][0] in after, (names, after)
