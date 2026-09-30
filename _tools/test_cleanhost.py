r"""Tests of _tools/cleanhost-run.ps1, the clean-account re-run of kb/_self/reports/windows-fresh-host.md
(`python3 _tools/tests.py -k clean_account_script`). The run itself creates a local account, so no test runs it.

  test_clean_account_script_parses  Windows: the PowerShell parser reads the script with no error (planted: an
                                    unclosed brace is reported)
  test_clean_account_script_keeps_the_password_secret
                                    every OS: the random password is made inside ConvertTo-SecureString and never
                                    held, converted back or printed as plain text (planted: a plain-text variable,
                                    GetNetworkCredential and ConvertFrom-SecureString are each reported)
"""
import json, os, re, shutil, subprocess

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(TOOLS, "cleanhost-run.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

PARSE = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(), "
         "[ref]$null, [ref]$e); $e | ForEach-Object { $_.Message } | ConvertTo-Json -Compress")


def parse_errors(text):
    r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", PARSE], input=text,
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    if not out:
        return []
    got = json.loads(out)
    return [got] if isinstance(got, str) else got


def secret_problems(text):
    """What would put the account's password in plain text somewhere it could be read or printed."""
    bad = []
    for m in re.finditer(r"ConvertTo-SecureString\s+(.+?)\s+-AsPlainText", text):
        if "$" in re.sub(r"\$bytes\b", "", m.group(1)):
            bad.append(f"plain text from a variable: {m.group(0)}")
    for pat in ("GetNetworkCredential", "ConvertFrom-SecureString", "SecureStringToBSTR", "PtrToString"):
        if pat in text:
            bad.append(f"converted back: {pat}")
    for m in re.finditer(r"^\s*\$(\w+)\s*=\s*\[Convert\]::ToBase64String", text, re.M):
        bad.append(f"plain text held in ${m.group(1)}")
    return bad


def read():
    with open(SCRIPT, encoding="utf-8") as f:
        return f.read()


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="PowerShell's parser: Windows")
def test_clean_account_script_parses():
    text = read()
    assert parse_errors(text) == []
    assert parse_errors(text.replace("if ($AsAccount) {", "if ($AsAccount) { {", 1)) != []


def test_clean_account_script_keeps_the_password_secret():
    text = read()
    assert secret_problems(text) == []
    assert "Write-Output" in text and "-AsPlainText" in text
    held = text.replace("$secret = ConvertTo-SecureString ([Convert]::ToBase64String($bytes) + 'a1!') -AsPlainText",
                        "$pw = [Convert]::ToBase64String($bytes)\n$secret = ConvertTo-SecureString $pw -AsPlainText", 1)
    assert held != text
    assert len(secret_problems(held)) == 2
    assert secret_problems(text + "\nWrite-Output $cred.GetNetworkCredential().Password\n") == ["converted back: GetNetworkCredential"]
    assert secret_problems(text + "\n$secret | ConvertFrom-SecureString\n") == ["converted back: ConvertFrom-SecureString"]
