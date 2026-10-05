# Re-runs kb/_self/reports/windows-fresh-host.md on a Windows host: a temporary local standard account goes from no
# Python to every /kb-setup step that needs no Claude Code sign-in, by the steps' own commands.
#
#   powershell -ExecutionPolicy Bypass -File _tools\cleanhost-run.ps1 [-Short] [-KeepAccount] [-Out DIR]
#
# Run it elevated, from a clone whose main is origin/main. It creates the account kb-cleanhost (Users only, a random
# password held as a SecureString and never printed), bundles main into C:\Users\Public\kb-cleanhost (Administrators,
# SYSTEM and the account only), runs this script again as that account through Start-Process -Credential (no user
# rights changed), copies its results.txt and one log per step to -Out (default _cache\cleanhost, never committed),
# then deletes the account, its profile and the work folder. -Short leaves out tests.py and adds the step 4 and 5 commands that need no sign-in. -KeepAccount keeps the account and the
# folder for a look afterwards; delete them by hand. Exit 0 when every step exited 0, 1 when one did not, 2 when the
# run could not start. The results name no host or user: profile paths print as %USERPROFILE%.
param([switch]$Short, [switch]$KeepAccount, [string]$Out, [switch]$AsAccount)
$ProgressPreference = 'SilentlyContinue'
$name = 'kb-cleanhost'
$root = 'C:\Users\Public\kb-cleanhost'

if ($AsAccount) {
    # the account's part: record the host, install Python, run the steps; each step's exit code and last line
    $ErrorActionPreference = 'Continue'
    $work = "$root\out"
    New-Item -ItemType Directory -Force $work | Out-Null
    $res = "$work\results.txt"
    function Rec($step, $code, $last) { "$step | exit $code | $last" | Add-Content $res -Encoding utf8 }
    function Refresh-Path {
        $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User')
    }
    function OnPath($n) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { $c.Source -replace [regex]::Escape($env:USERPROFILE), '%USERPROFILE%' } else { 'not found' }
    }
    function Step($step, [scriptblock]$sb) {
        $log = "$work\$($step -replace '[^\w.-]', '_').log"
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $o = & $sb 2>&1 | ForEach-Object { "$_" -replace [regex]::Escape($env:USERPROFILE), '%USERPROFILE%' }
        $code = $LASTEXITCODE
        $sw.Stop()
        $o | Set-Content $log -Encoding utf8
        $last = ($o | Where-Object { $_ -and $_.Trim() } | Select-Object -Last 1)
        Rec $step $code ("{0} ({1:N0} s)" -f $last, $sw.Elapsed.TotalSeconds)
    }
    "# started $(Get-Date -Format s)" | Set-Content $res -Encoding utf8
    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $os = Get-CimInstance Win32_OperatingSystem
    Rec 'host windows' 0 "$($os.Caption) $($cv.DisplayVersion) build $($cv.CurrentBuild).$($cv.UBR), $env:PROCESSOR_ARCHITECTURE"
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    Rec 'host account' 0 "standard user (Administrators member: $admin)"
    Rec 'host PATH git dirs' 0 ((($env:PATH -split ';') | Where-Object { $_ -match 'Git' }) -join '; ')
    Rec 'host git' 0 ((& git --version) 2>&1)
    foreach ($n in 'python', 'python3', 'py', 'uv') { Rec "before: $n on PATH" 0 (OnPath $n) }

    # the kb, from the bundle (the account has no git credentials)
    Step 'clone' { git clone -q --branch main "$root\it-ops-kb.bundle" "$env:USERPROFILE\it-ops-kb"; git -C "$env:USERPROFILE\it-ops-kb" log --oneline -1 }
    Set-Location "$env:USERPROFILE\it-ops-kb"
    Step 'install-python.ps1 -CheckOnly' { powershell -NoProfile -ExecutionPolicy Bypass -File .\_tools\install-python.ps1 -CheckOnly }
    Step 'install-python.ps1' { powershell -NoProfile -ExecutionPolicy Bypass -File .\_tools\install-python.ps1 }
    Refresh-Path
    foreach ($n in 'python', 'python3', 'py', 'uv') { Rec "after: $n on PATH" 0 (OnPath $n) }

    # /kb-setup by its commands (.claude/skills/kb-setup/SKILL.md)
    Step 'kb-setup 1: python3 --version' { python3 --version }
    Step 'kb-setup 1: uv --version' { uv --version }
    Step 'kb-setup 2: check.py' { python3 _tools/check.py }
    Step 'kb-setup 2: fetch.py --offline' { python3 _tools/fetch.py --offline }
    Step 'kb-setup 2: rag.py eval' { python3 _tools/rag.py eval }
    Step 'kb-setup 2: rag.py pack kerberos delegation' { python3 _tools/rag.py pack "kerberos delegation" }
    Step 'kb-setup 3: kbgit.py install-hooks' { python3 _tools/kbgit.py install-hooks }
    if ($Short) {
        Step 'kb-setup 4: kb_mcp.py --status' { python3 _tools/kb_mcp.py --status }
        Step 'kb-setup 5: querylog.py where' { python3 _tools/querylog.py where }
    } else {
        Step 'kb-setup 2: tests.py' { python3 _tools/tests.py }
    }
    "# finished $(Get-Date -Format s)" | Add-Content $res -Encoding utf8
    exit 0
}

# the operator's part, elevated
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Out) { $Out = Join-Path $repo '_cache\cleanhost' }
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Write-Output 'run it elevated: it creates and deletes a local account'; exit 2 }
if (Get-LocalUser -Name $name -ErrorAction SilentlyContinue) { Write-Output "the account $name exists: a previous run was not cleaned up"; exit 2 }
if (Test-Path $root) { Write-Output "$root exists: a previous run was not cleaned up"; exit 2 }
if ((git -C $repo rev-parse main) -ne (git -C $repo rev-parse origin/main)) { Write-Output 'main is not origin/main: run it on the pushed main'; exit 2 }

New-Item -ItemType Directory $root | Out-Null
$ErrorActionPreference = 'Continue'
git -C $repo bundle create "$root\it-ops-kb.bundle" main 2>&1 | Out-Null
$ErrorActionPreference = 'Stop'
if (-not (Test-Path "$root\it-ops-kb.bundle")) { Remove-Item -Recurse -Force $root; Write-Output 'the bundle was not written'; exit 2 }
Copy-Item $MyInvocation.MyCommand.Path "$root\cleanhost-run.ps1"

$bytes = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = ConvertTo-SecureString ([Convert]::ToBase64String($bytes) + 'a1!') -AsPlainText -Force
[Array]::Clear($bytes, 0, $bytes.Length)
New-LocalUser -Name $name -Password $secret -PasswordNeverExpires -AccountNeverExpires -Description 'temporary: it-ops-kb clean-host run' | Out-Null
Add-LocalGroupMember -Group (Get-LocalGroup -SID 'S-1-5-32-545').Name -Member $name
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in 'S-1-5-32-544', 'S-1-5-18') {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier $sid), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
}
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule("$env:COMPUTERNAME\$name", 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
Set-Acl $root $acl
Write-Output "account $name created; work folder $root; mode $(if ($Short) { 'short' } else { 'full' })"

try {
    $cred = New-Object Management.Automation.PSCredential("$env:COMPUTERNAME\$name", $secret)
    $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\cleanhost-run.ps1", '-AsAccount')
    if ($Short) { $argv += '-Short' }
    $p = Start-Process powershell.exe -Credential $cred -LoadUserProfile -WorkingDirectory $root -WindowStyle Hidden -Wait -PassThru -ArgumentList $argv
    Write-Output "account run exit: $($p.ExitCode)"
} finally {
    New-Item -ItemType Directory -Force $Out | Out-Null
    Copy-Item "$root\out\*" $Out -Force -ErrorAction SilentlyContinue
    if (-not $KeepAccount) {
        $usid = (Get-LocalUser -Name $name).SID.Value
        Get-CimInstance Win32_UserProfile | Where-Object { $_.SID -eq $usid } | Remove-CimInstance
        Remove-LocalUser -Name $name
        Remove-Item -Recurse -Force $root
        Write-Output "account, profile and $root deleted"
    }
}
$results = Join-Path $Out 'results.txt'
if (-not (Test-Path $results)) { Write-Output 'no results: the account run did not start'; exit 1 }
Get-Content $results
$failed = @(Get-Content $results | Where-Object { $_ -match '\| exit (\S+) \|' -and $Matches[1] -ne '0' })
if ($failed) { exit 1 }
exit 0
