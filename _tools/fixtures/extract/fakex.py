"""A synthetic extractor for test_fetch_extract.py: `fakex.py x IN -oOUT`. What it does is named by the first line of IN:
`ok` writes a text file, a binary file and the environment it was started with; `link` leaves a symbolic link; `many`
leaves ten files; `deep` leaves nested folders; `hang` sleeps. Nothing here reads a real archive."""
import json, os, sys

src = sys.argv[2]
out = next(a[2:] for a in sys.argv[3:] if a.startswith("-o"))
mode = open(src, encoding="utf-8").readline().strip()
if mode == "ok":
    os.makedirs(os.path.join(out, "sub"))
    open(os.path.join(out, "sub", "note.txt"), "w", encoding="utf-8").write("synthetic note\n")
    open(os.path.join(out, "blob.bin"), "wb").write(b"\0\1\2 Synthetic.Package.Name \0")
    open(os.path.join(out, "env.json"), "w", encoding="utf-8").write(json.dumps(sorted(os.environ)))
    open(os.path.join(out, "proxy.txt"), "w", encoding="utf-8").write(os.environ.get("HTTPS_PROXY", ""))
elif mode == "link":
    os.symlink(src, os.path.join(out, "escape"))
elif mode == "many":
    for n in range(10):
        open(os.path.join(out, "f%d.txt" % n), "w", encoding="utf-8").write("x\n")
elif mode == "deep":
    os.makedirs(os.path.join(out, *["d"] * 5))
    open(os.path.join(out, *["d"] * 5, "x.txt"), "w", encoding="utf-8").write("x\n")
elif mode == "hang":
    import time
    time.sleep(30)
else:
    sys.exit(3)
