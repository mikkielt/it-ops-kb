"""Where and as whom a job runs: kbjob.py place asks an OPA placement policy (stdlib only; kb/_self/coordination.md, section "Operation jobs").

`place(op, subject, url, ...)` builds the input {op, subject, roots, root_groups, operator, groups, host,
capabilities: {paid, push}} (the capabilities describe the operation: `paid` for one that spends model calls, `push` for one
that pushes to a remote, read from `PAID_OPS` and `PUSH_OPS`, never from the environment), sends it as `POST URL/v1/data/kbjobs/placement` and returns the one decision
{executor, identity, fallback, fallback_after_s, budget_cap_usd, decided_by, reason}. Any failure to answer, an unreachable
OPA, a reply with no `result`, or a field outside the tables of `coord` (executor workstation|server|ci, identity
none|group-bot|operator, fallback null or an executor, the two numbers null or 0 and up), decides the workstation with
identity none and a reason that names the cause: a job is never refused or lost because a policy could not be asked.
"""
import json
import os
import platform
import re
import urllib.error
import urllib.parse
import urllib.request

import coord

PATH = "/v1/data/kbjobs/placement"
TIMEOUT_S = 5
ENV_URL = "KB_OPA_URL"
FALLBACK_DECISION = {"executor": "workstation", "identity": "none", "fallback": None, "fallback_after_s": 0,
                     "budget_cap_usd": None, "decided_by": "default"}


def refused(reason):
    """The decision of a policy that gave none: the workstation, no identity, REASON naming the cause."""
    return {**FALLBACK_DECISION, "reason": reason}


def roots_of():
    """(names, {name: group path}) of the roots this clone serves; the groups only of roots that name one (a bare team is read as the group of that name)."""
    import kbcommon
    served = kbcommon.roots()
    return [r.name for r in served], {r.name: kbcommon.pointer_group(r) for r in served if kbcommon.pointer_group(r)}


PAID_OPS = ("bench", "dispatch", "begin")  # the operations that spend model calls
PUSH_OPS = ("land", "sync-push")  # the operations that push to a remote


def capabilities_of(op):
    """{paid, push} of the operation OP, not of the host: `paid` when OP spends model calls, `push` when it pushes to a remote.
    Read from the two tables above, never from the environment or a remote, so no credential is touched."""
    return {"paid": op in PAID_OPS, "push": op in PUSH_OPS}


def group_paths(operator_path):
    """The groups of the operator `G1/.../OPERATOR`: `G1`, `G1/G2`, ... (coord's group scopes), [] for a flat operator."""
    parts = [p for p in (operator_path or "").split("/") if p]
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def build_input(op, subject, operator=None, groups=None):
    """The OPA input for OP on SUBJECT: what the policy decides from."""
    names, root_groups = roots_of()
    return {"op": op, "subject": subject or "", "roots": names, "root_groups": root_groups, "operator": operator or "",
            "groups": list(groups or []), "host": platform.node(), "capabilities": capabilities_of(op)}


def number_or_none(value):
    """VALUE when it is a number of 0 or more (not a bool), None when null, ValueError otherwise."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value:
        raise ValueError(f"{value!r} is no number of 0 or more")
    return value


def checked(result):
    """The decision RESULT (the `result` member of OPA's reply) holds, or a refused one naming the field outside its table."""
    if not isinstance(result, dict):
        return refused("the policy's result is no object")
    for name, table in (("executor", coord.PLACEMENT_EXECUTORS), ("identity", coord.PLACEMENT_IDENTITIES)):
        if result.get(name) not in table:
            return refused(f"the policy's {name} {str(result.get(name))[:40]!r} is none of {', '.join(table)}")
    fallback = result.get("fallback")
    if fallback is not None and fallback not in coord.PLACEMENT_EXECUTORS:
        return refused(f"the policy's fallback {str(fallback)[:40]!r} is none of null, {', '.join(coord.PLACEMENT_EXECUTORS)}")
    try:
        after = number_or_none(result.get("fallback_after_s", 0))
        cap = number_or_none(result.get("budget_cap_usd"))
    except ValueError as error:
        return refused(f"the policy's fallback_after_s or budget_cap_usd is wrong: {error}")
    decided_by, reason = result.get("decided_by"), result.get("reason")
    return {"executor": result["executor"], "identity": result["identity"], "fallback": fallback,
            "fallback_after_s": 0 if after is None else after, "budget_cap_usd": cap,
            "decided_by": decided_by if isinstance(decided_by, str) and decided_by else "policy",
            "reason": reason if isinstance(reason, str) and reason else "the policy's decision"}


def ask(url, body):
    """The decision OPA at URL gives for the input BODY, or a refused one when it cannot be asked or does not answer."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return refused(f"the policy url {url[:60]!r} is no http or https url")
    request = urllib.request.Request(url.rstrip("/") + PATH, data=json.dumps({"input": body}).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:
            data = json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return refused(f"the policy answered HTTP {error.code}")
    except (OSError, ValueError) as error:  # URLError and timeouts are OSErrors; a body that is no JSON a ValueError
        return refused(f"the policy could not be asked: {type(error).__name__}: {str(error)[:100]}")
    if not isinstance(data, dict) or "result" not in data:
        return refused("the policy returned no result")
    return checked(data["result"])


def place(op, subject, url=None, operator=None, groups=None):
    """The decision for OP on SUBJECT: the policy at URL, else the one KB_OPA_URL names, else the workstation (reason `no policy`)."""
    url = url or os.environ.get(ENV_URL, "")
    if not url:
        return refused("no policy: no --opa and no KB_OPA_URL")
    return ask(url, build_input(op, subject, operator, groups))


BUNDLES = ("kbjobs", "kbjobs-overrides")  # the two bundles `coord.py serve` answers at GET /v1/bundles/NAME.tar.gz
SIGNING_KEYID = "kbjobs"  # the keyid of the signature in each bundle
OPA_CONFIG_PATH = "/etc/opa/kbjobs.yaml"  # where `opa_config` says to save the configuration
OPA_ENV_PATH = "/etc/opa/kbjobs.env"  # where it says to keep the one environment line that holds the key
OPA_STATE_DIR = "/var/lib/opa-kbjobs"  # the persistence directory (systemd's StateDirectory=opa-kbjobs)
OPA_ADDR = "127.0.0.1:8181"  # the loopback address OPA serves on, the one `KB_OPA_URL` names


def opa_config(url, token_file, key_env, plain_http=False):
    """The OPA configuration (YAML) and the systemd unit that runs `opa run --server` with it, as one text. The configuration has one
    service at URL with the bearer `token_path` TOKEN_FILE (an absolute path, never read), the bundles of BUNDLES polled and persisted,
    verified against the signing keyid and the HS256 key `${KEY_ENV}`, which `opa run` replaces from its environment. Nothing is read
    or written: neither the token's nor the key's text is known here. A refusal (`ValueError`) names a url that is no http(s) url, a plain
    http url beyond loopback without PLAIN_HTTP, a relative token file and an environment name no variable has."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"--url {url[:60]!r} is no http or https url")
    if parts.scheme == "http" and not plain_http and not coord.is_loopback(parts.hostname):
        raise ValueError(f"--url host {parts.hostname} is not loopback and OPA would send the token over plain http, in the clear: "
                         "use an https url, or pass --plain-http to accept the risk")
    if not token_file.startswith("/"):
        raise ValueError(f"--token-file {token_file[:60]!r} is not an absolute path: OPA reads it from the working directory of its service")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
        raise ValueError(f"--key-env {key_env[:40]!r} is no environment variable name")
    quote = json.dumps  # a JSON string is a YAML string
    bundles = "".join(f"""  {name}:
    service: kb
    resource: {quote("v1/bundles/" + name + ".tar.gz")}
    persist: true
    polling:
      min_delay_seconds: 10
      max_delay_seconds: 60
    signing:
      keyid: {SIGNING_KEYID}
""" for name in BUNDLES)
    config = f"""# Save as {OPA_CONFIG_PATH}. `opa run` replaces ${{{key_env}}} from its environment (the unit's EnvironmentFile).
services:
  kb:
    url: {quote(url.rstrip("/"))}
    credentials:
      bearer:
        token_path: {quote(token_file)}
bundles:
{bundles}keys:
  {SIGNING_KEYID}:
    key: "${{{key_env}}}"
    algorithm: HS256
persistence_directory: {quote(OPA_STATE_DIR)}
"""
    unit = f"""# Save as /etc/systemd/system/opa-kbjobs.service, then run: systemctl enable --now opa-kbjobs.service
# {OPA_ENV_PATH} (mode 0600) holds the one line {key_env}=<the bytes of the file that coord.py serve --bundle-key names>
[Unit]
Description=OPA placement policy of the it-ops-kb job queue
After=network-online.target

[Service]
EnvironmentFile={OPA_ENV_PATH}
ExecStart=/usr/local/bin/opa run --server --addr {OPA_ADDR} --config-file {OPA_CONFIG_PATH}
StateDirectory=opa-kbjobs
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    return config + "\n" + unit
