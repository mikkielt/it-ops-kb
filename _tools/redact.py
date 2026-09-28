#!/usr/bin/env python3
"""Redaction for the query log: identifier shapes to kb placeholders, before and after Haiku (stdlib only).

  redact.py [FILE]        the rules pass over FILE (default stdin), printed to stdout as UTF-8, newlines kept
  redact.py --scan [FILE] the leak scan over FILE: one `kind<TAB>value` line per hit, exit 1 when there is any

The design is kb/_self/querylog.md (Redaction). Three stages per batch of entries:
  1. redact(text)         stdlib rules: each identifier shape becomes the kb placeholder for its kind (PLACEHOLDERS)
  2. Haiku                on the rule-redacted text only: replaces person and organisation names and flags an entry
                          that still identifies someone (names_argv, names_prompt, parse_names); no NER layer
  3. finish(text)         the rules again, then the leak scan (kbcommon.leak_hits); a hit drops the entry
redact_batch(texts, haiku) runs the three: `haiku` is a callable from rule-redacted texts to [(text, identifying)], and
the tests supply a stub. querylog.py's distill stores no text Haiku writes: it runs redact() and finish() on the kb's
own question and starts its judging Haiku call with names_argv (querylog.md, Distill).

What stays (querylog.md): well-known SIDs (only an `S-1-5-21-*` domain identifier names an organisation), anything the
public root already contains (Graph app ids, CSP GUIDs, vendor hosts: known(), read from kb/public at run time), the
documentation ranges and names (192.0.2.0/24, 2001:db8::/32, example.com), and the placeholders themselves, so that
redact(redact(x)) == redact(x). A user is matched both as a UPN or e-mail and as a down-level `DOMAIN\\name`, with no
suffix allowlist: an explicit UPN suffix need not be the DNS domain (reuse/pseudonymization-tokenization.md:43-48, DOC
and DER S-h2cmbqvf, S-dcjdn73r).
"""
import collections, functools, ipaddress, json, math, re, shutil, sys
from pathlib import Path

import kbcommon

ENTROPY_MIN_LEN = 20  # characters: shorter random-looking strings are mostly words and ids the kb names
ENTROPY_MIN_BITS = 3.5  # bits per character: keys and tokens sit above it

# The kb placeholder of each kind (kb/_self/content-rules.md, and querylog.md for the kinds it adds).
PLACEHOLDERS = {
    "guid": "00000000-0000-0000-0000-000000000000",
    "guid_bare": "00000000000000000000000000000000",
    "ipv4": "192.0.2.10",
    "ipv6": "2001:db8::10",
    "sid": "S-1-5-21-0-0-0",  # the domain identifier; the RID stays (500, 512, 513 are fixed)
    "email": "jan.kowalski@corp.example.com",
    "logon": "CORP\\jan.kowalski",
    "user": "jan.kowalski",
    "host": "corp.example.com",
    "server": "PL-SRV-0042",
    "computer": "PL-LT-00123",
    "unc": "\\\\PL-SRV-0042",
    "path": "PL-PATH",
    "org": "CORP",
    "secret": "<secret>",
}
_PL_WORDS = {w for v in PLACEHOLDERS.values() for w in re.findall(r"[a-z0-9]+", v.lower())}

# --- shapes -------------------------------------------------------------------------------------------------------
GUID = re.compile(r"(?<![\w-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?![\w-])")
GUID_BARE = re.compile(r"(?<![\w-])[0-9A-Fa-f]{32}(?![\w-])")
IPV4 = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?![\w]|\.\d)")
IPV6 = re.compile(r"(?<![\w:.\]])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
SID = re.compile(r"(?<![\w-])S-1-5-21-(\d+)-(\d+)-(\d+)((?:-\d+)?)(?![\w-])")
EMAIL = re.compile(r"(?<![\w.%+-])[A-Za-z0-9._%+-]+@(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|[A-Z][A-Z0-9-]{1,14}\b)(?![\w-])")
EXAMPLE_HOST = re.compile(r"(?i)(?:^|\.)(?:example\.(?:com|net|org)|example|test|invalid|localhost)$|^localhost$")
LOGON = re.compile(r"(?<![\w\\/:.%$@-])([A-Za-z0-9][A-Za-z0-9-]{0,14})\\([A-Za-z0-9._$-]*[A-Za-z0-9_$])(?![\w\\/-]|\.\w)")
# down-level domains that are Windows authorities, not organisations, and registry roots written like one
AUTHORITIES = ("nt authority", "builtin", "nt service", "nt virtual machine", "iis apppool", "window manager",
               "font driver host", "application package authority", "nt task")
REGISTRY_ROOTS = ("hklm", "hkcu", "hkcr", "hku", "hkcc")
TLDS = ("com net org edu gov mil int info biz io ai co me dev app cloud ms tv us uk de pl eu fr nl be ch at se no dk "
        "fi cz sk es it pt ie ca au nz jp cn in ru ua br mx za sg hk kr tw il tr gr hu ro bg hr si lt lv ee lu is "
        "local lan corp internal intra home arpa example test invalid localhost site online tech xyz").split()
HOST = re.compile(r"(?<![\w.@/\\-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:" + "|".join(TLDS) +
                  r")(?![\w-]|\.[A-Za-z0-9])", re.I)
PASCAL = re.compile(r"(?:^|\.)[A-Z][a-z]")  # System.IO, Microsoft.Graph.Beta: .NET names, not hosts
UNC = re.compile(r"(?<![\w\\])\\\\(?![?.]\\)([A-Za-z0-9._$-]+)((?:\\[^\\\s\"'<>|*?:]+)*)")
DRIVE = re.compile(r"(?<![\w])[A-Za-z]:((?:[\\/]{1,2}[^\\/\r\n\t\"'<>|*?:]+(?=[\\/]))*(?:[\\/]{1,2}[^\\/\s\"'<>|*?:,;)]*)?)")
HOME = re.compile(r"(?<![\w.])/(?:Users|home)/([^/\s\"'<>|]+)((?:/[^/\s\"'<>|]+)*)")
COMPUTER = re.compile(r"(?<![\w.\\/@-])[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){0,3}(?![\w.\\-])")
SERVERISH = re.compile(r"SRV|SVR|SERVER|SQL|EXCH|DC\d|FS\d")
ID_LIKE = re.compile(r"CVE-\d{4}-\d+|KB\d+|RFC\d+|MS\d\d-\d+|PL-[A-Z]+-\d+|S(?:-\d+)+")
TOKEN = re.compile(r"(?<![A-Za-z0-9+_=])[A-Za-z0-9+_]{%d,}={0,2}(?![A-Za-z0-9+_=])" % ENTROPY_MIN_LEN)
WORD_PIECES = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
SECRETS = [re.compile(f"(?i:{p[4:]})" if p.startswith("(?i)") else p) for p in kbcommon.SECRETS]


def entropy(s):
    """Shannon entropy of `s`, in bits per character."""
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in collections.Counter(s).values()) if n else 0.0


# --- what the public root already contains ------------------------------------------------------------------------
Known = collections.namedtuple("Known", "guids ips hosts emails logons computers tokens words")
TEXT_SUFFIXES = {".md", ".csv", ".txt", ".json", ".yaml", ".yml", ".xml", ".ts", ".proto"}


def scan_known(texts):
    """The identifiers found in `texts` by the same shapes the rules use, lowercased: what stays when a lookup names it."""
    k = Known(*(set() for _ in Known._fields))
    for t in texts:
        low = t.lower()
        k.guids.update(g.replace("-", "") for g in GUID.findall(low))
        k.guids.update(GUID_BARE.findall(low))
        k.ips.update(m.group(0) for m in IPV4.finditer(low))
        k.ips.update(m.group(0) for m in IPV6.finditer(low))
        k.hosts.update(m.group(0).lower() for m in HOST.finditer(t))
        k.emails.update(m.group(0).lower() for m in EMAIL.finditer(t))
        k.logons.update(m.group(0).lower() for m in LOGON.finditer(t))
        k.computers.update(m.group(0).lower() for m in COMPUTER.finditer(t))
        k.tokens.update(m.group(0).lower() for m in TOKEN.finditer(t))
        k.words.update(re.findall(r"[a-z0-9]+", low))
    k.words.update(_PL_WORDS)
    return k


@functools.lru_cache(maxsize=None)
def known(root=None):
    """scan_known over every text file of the public root (never an internal one: those name real tenants), read once
    per process. Deriving it at run time keeps one owner: an id an article adds is kept from its next run on."""
    base = Path(root or kbcommon.PUBLIC)
    texts = []
    for p in sorted(base.rglob("*")):
        if p.suffix.lower() in TEXT_SUFFIXES and p.is_file():
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
    return scan_known(texts)


# --- the rules ------------------------------------------------------------------------------------------------------
def _secret(m):
    s = m.group(0)
    q = re.search(r"([\"'])([^\"']*)\1$", s)
    if q:
        return s[:q.start(2)] + PLACEHOLDERS["secret"] + s[q.end(2):]
    if "=" in s:  # AccountKey=..., ?sig=...: keep the name
        return s[:s.index("=") + 1] + PLACEHOLDERS["secret"]
    return PLACEHOLDERS["secret"]


def _segment(seg, k):
    """A path segment made only of words the public root uses stays; any other becomes PL-PATH."""
    words = re.findall(r"[a-z0-9]+", seg.lower())
    return seg if all(w in k.words for w in words) else PLACEHOLDERS["path"]


def _path(tail, k, users_first):
    """Redact the segments of a path tail (`\\a\\b` or `/a/b`), separators kept; with `users_first`, a tail starting
    at `Users\\<name>` gets the placeholder user."""
    parts = re.split(r"([\\/]+)", tail)
    out, seen = [], []
    for p in parts:
        if not p or re.fullmatch(r"[\\/]+", p):
            out.append(p)
            continue
        if users_first and len(seen) == 1 and seen[0].lower() == "users":
            p = p if p.lower() in kbcommon.HOME_GENERIC else PLACEHOLDERS["user"]
        else:
            p = _segment(p, k)
        seen.append(p)
        out.append(p)
    return "".join(out)


def _logon(m, k):
    dom, s = m.group(1).lower(), m.group(0)
    before = m.string[max(0, m.start() - 40):m.start()].lower() + dom
    if dom in REGISTRY_ROOTS or dom.startswith("hkey_") or s.lower() in k.logons \
            or any(before.endswith(a) for a in AUTHORITIES):
        return s
    return PLACEHOLDERS["logon"]


def _ip(m, k):
    s = m.group(0)
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return s
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or (s.lower() in k.ips and ip.is_global):
        return s  # a private or link-local address the kb shows is an example there, but a network in a question
    if ip.version == 4:
        if any(ip in ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")):
            return s
        bits = int(ip)
        if bits and (bits | (bits - 1)) == 0xFFFFFFFF:  # a netmask: contiguous ones
            return s
        return PLACEHOLDERS["ipv4"]
    return s if ip in ipaddress.ip_network("2001:db8::/32") else PLACEHOLDERS["ipv6"]


def _host(m, k):
    s = m.group(0)
    if PASCAL.search(s) or s.lower() in k.hosts or EXAMPLE_HOST.search(s):
        return s
    return PLACEHOLDERS["host"]


def _computer(m, k):
    s = m.group(0)
    if len(s) > 15 or not re.search(r"\d", s) or len(re.findall(r"[A-Z]", s)) < 2 or ID_LIKE.fullmatch(s) \
            or s.lower() in k.computers or s.lower() in k.words:
        return s
    return PLACEHOLDERS["server"] if SERVERISH.search(s) else PLACEHOLDERS["computer"]


def _token(m, k):
    s = m.group(0)
    low = s.lower()
    if low in k.tokens or not (re.search(r"\d", s) and re.search(r"[A-Za-z]", s)) or entropy(s) < ENTROPY_MIN_BITS:
        return s
    pieces = WORD_PIECES.findall(s.strip("="))
    if all(p.isdigit() or (len(p) >= 3 and p.lower() in k.words) for p in pieces):
        return s  # made of words the kb uses, split at case and digit changes: a name (Win32LobAppPowerShellScript1)
    return PLACEHOLDERS["secret"]


def redact(text, k=None):
    """The rules pass: every identifier shape in `text` becomes its kb placeholder; what the public root contains, the
    well-known and documentation values and the placeholders stay. Idempotent."""
    k = k or known()
    for rx in SECRETS:
        text = rx.sub(_secret, text)
    text = UNC.sub(lambda m: PLACEHOLDERS["unc"] + _path(m.group(2), k, False), text)
    text = DRIVE.sub(lambda m: m.group(0)[:2] + _path(m.group(1), k, True), text)
    text = HOME.sub(lambda m: m.group(0)[:m.start(1) - m.start(0)] + (
        m.group(1) if m.group(1).lower() in kbcommon.HOME_GENERIC else PLACEHOLDERS["user"]) + _path(m.group(2), k, False),
                    text)
    text = EMAIL.sub(lambda m: m.group(0) if m.group(0).lower() in k.emails
                     or EXAMPLE_HOST.search(m.group(0).split("@", 1)[1]) else PLACEHOLDERS["email"], text)
    text = LOGON.sub(lambda m: _logon(m, k), text)
    text = SID.sub(lambda m: m.group(0) if m.group(1, 2, 3) == ("0", "0", "0") else PLACEHOLDERS["sid"] + m.group(4), text)
    text = GUID.sub(lambda m: m.group(0) if m.group(0).lower().replace("-", "") in k.guids
                    or kbcommon.GUID_OK.fullmatch(m.group(0).lower()) else PLACEHOLDERS["guid"], text)
    text = GUID_BARE.sub(lambda m: m.group(0) if m.group(0).lower() in k.guids
                         or not re.search(r"[1-9a-f]", m.group(0).lower()) else PLACEHOLDERS["guid_bare"], text)
    text = IPV6.sub(lambda m: _ip(m, k), text)
    text = IPV4.sub(lambda m: _ip(m, k), text)
    text = HOST.sub(lambda m: _host(m, k), text)
    text = COMPUTER.sub(lambda m: _computer(m, k), text)
    return TOKEN.sub(lambda m: _token(m, k), text)


def scan(text, k=None):
    """The leak scan (kbcommon.leak_hits) with what the public root contains allowed: [(kind, value)]."""
    k = k or known()
    allow = {"guid": {f"{g[:8]}-{g[8:12]}-{g[12:16]}-{g[16:20]}-{g[20:]}" for g in k.guids}, "email": k.emails}
    return kbcommon.leak_hits(text, allow)


def finish(text, k=None):
    """Stage 3 on Haiku's output: the rules again, then the leak scan; None (drop the entry) on any hit."""
    k = k or known()
    out = redact(text, k)
    return None if scan(out, k) else out


# --- the Haiku stage ------------------------------------------------------------------------------------------------
NAMES_TASK = (
    "Each entry below is a question or note from an IT administrator, already stripped of addresses, ids and paths. "
    "Replace every person's name with jan.kowalski and every organisation's own name (the company, a customer, a team) "
    "with CORP. Keep product, vendor and technology names (Microsoft, Intune, Entra ID, GitLab), placeholders "
    "(PL-..., corp.example.com, <secret>) and everything else as written. Set identifying to true when the entry would "
    "still identify a person or an organisation after that. Reply with only a JSON array, one object per entry, in "
    'order: [{"i": 0, "text": "...", "identifying": false}, ...].')


def names_argv(model):
    """The `claude -p` argument list of the Haiku stage: the pipeline never logs itself (disableAllHooks), no tools, no
    user plugins or MCP servers (as kb_ask.py's lean reader). The prompt goes on stdin (no command-line length limit)."""
    return [shutil.which("claude") or "claude", "-p", "--model", model, "--tools", "", *kbcommon.NO_HOOKS,
            "--setting-sources", "project,local", "--strict-mcp-config", "--no-session-persistence"]


def names_prompt(texts):
    """The prompt of one batch: the task, then the rule-redacted entries as a JSON array."""
    return NAMES_TASK + "\n\n" + json.dumps([{"i": i, "text": t} for i, t in enumerate(texts)], ensure_ascii=False)


def parse_names(reply, n):
    """[(text, identifying)] of a Haiku reply for n entries; ValueError when it is not that JSON."""
    a, b = reply.find("["), reply.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON array in the reply")
    rows = json.loads(reply[a:b + 1])
    if not isinstance(rows, list) or len(rows) != n:
        raise ValueError(f"expected {n} entries")
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict) or r.get("i") != i or not isinstance(r.get("text"), str) \
                or not isinstance(r.get("identifying"), bool):
            raise ValueError(f"entry {i} is malformed")
        out.append((r["text"], r["identifying"]))
    return out


def redact_batch(texts, haiku, k=None):
    """The three stages over one batch: [redacted text, or None when the entry is dropped]. An entry Haiku flags, or
    one the last leak scan catches, is dropped; a reply `haiku` cannot give (ValueError, OSError) drops the batch."""
    k = k or known()
    first = [redact(t, k) for t in texts]
    try:
        named = haiku(first)
        if len(named) != len(texts):
            raise ValueError("wrong entry count")
    except (ValueError, OSError):
        return [None] * len(texts)
    return [None if flagged else finish(t, k) for t, flagged in named]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    do_scan = argv[:1] == ["--scan"]
    args = argv[1:] if do_scan else argv
    if len(args) > 1 or (args and args[0].startswith("-")):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    raw = Path(args[0]).read_bytes() if args else sys.stdin.buffer.read()
    text = raw.decode("utf-8", errors="replace")
    if do_scan:
        found = scan(text)
        for kind, value in found:
            print(f"{kind}\t{value}")
        return 1 if found else 0
    sys.stdout.buffer.write(redact(text).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
