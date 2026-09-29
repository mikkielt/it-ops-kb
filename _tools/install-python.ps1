<#
.SYNOPSIS
  it-ops-kb: download the pinned official CPython installer from python.org and the pinned uv from its GitHub
  release, verify them, install them per user.

.DESCRIPTION
  For a Windows machine with no Python (kb/_self/maintaining.md, Setup step 1). No winget, no Store.
  1. Preflight: looks for what the install would conflict with on this host (below). A CONFLICT stops the script
     with exit 3 before anything is downloaded or installed, unless -AcceptConflicts; -CheckOnly runs only this.
  2. Downloads python-<version>-<arch>.exe from https://www.python.org/ftp/python/<version>/.
  3. Verifies its SHA-256 against the pin below; a mismatch deletes the file and stops.
  4. Verifies its Authenticode signature (valid, signed by the Python Software Foundation).
  5. Installs quietly for the current user (no admin): python.exe and the py launcher, on the user PATH.
  6. Adds python3.exe beside python.exe (a hard link), because the python.org installer ships none and every
     skill and permission rule in this repository runs `python3`; without it `python3` reaches the Store stub.
  7. uv (unless -SkipUv): downloads uv-<arch>-pc-windows-msvc.zip of the pinned uv from
     https://github.com/astral-sh/uv/releases/download/<version>/, verifies its SHA-256 against the pin, puts uv.exe,
     uvx.exe and uvw.exe in %USERPROFILE%\.local\bin (the folder uv's own installer uses) and adds that folder to
     the user PATH. The tests run through uv (_tools/tests.py); pip is not used.
  8. Reports which python, python3, py and uv a new session will start.

  Preflight findings, one line each, prefixed for whoever reads the output (an agent relays them to the user):
    CONFLICT: the install would replace, shadow or be shadowed by something already on the host. Not installed.
    NOTE:     present on the host, does not stop the install, worth knowing.
  Conflicts: running elevated; another patch of the same minor version installed for this user (the installer
  upgrades it in place); the same minor version installed for all users; a python/python3/py on the machine PATH
  that a new session would start instead (the machine PATH comes before the user PATH); PYTHONHOME or PYTHONPATH
  set; a python3.exe in the target folder that is not python.exe; a uv.exe in %USERPROFILE%\.local\bin that is not
  the pinned uv (the install would replace it), in %USERPROFILE%\.cargo\bin (uv's folder before 0.5.0) or in
  another folder on the machine or user PATH (two uv on PATH: the first one runs).
  The pinned version already installed for this user: nothing is downloaded; only the python3.exe link is checked.
  The same for the pinned uv.

  Exit codes: 0 installed or already installed (or -CheckOnly with no conflict); 1 error (download, checksum,
  signature, installer); 3 conflicts found, nothing changed.

  The pin: $Pin below. It follows .python-version (the minor version). Moving it: take the version and the
  "sha256_sum" of the "Windows installer (64-bit)" and "(ARM64)" files from python.org's release API,
  https://www.python.org/api/v2/downloads/release_file/?release=<id> (ids: /api/v2/downloads/release/).
  The uv pin: $UvPin below. Moving it: the release's uv-x86_64-pc-windows-msvc.zip.sha256 and
  uv-aarch64-pc-windows-msvc.zip.sha256 assets (kb/public/python/uv-windows-install.md).
  Windows PowerShell 5.1 or PowerShell 7.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File _tools\install-python.ps1 -CheckOnly
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File _tools\install-python.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File _tools\install-python.ps1 -DownloadOnly
#>
[CmdletBinding()]
param(
  [ValidateSet('amd64', 'arm64')]
  [string]$Arch,
  [string]$OutDir = $env:TEMP,
  [switch]$CheckOnly,
  [switch]$DownloadOnly,
  [switch]$AcceptConflicts,
  [switch]$SkipPython3Alias,
  [switch]$SkipUv
)

$ErrorActionPreference = 'Stop'

# Pinned 2026-09-28 from https://www.python.org/api/v2/downloads/release_file/?release=1116 (Python 3.14.7).
$Pin = @{
  Version = '3.14.7'
  Sha256  = @{
    amd64 = '9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649'
    arm64 = '9a3fe120cc81bc2cb099550f794d8356811f96a86c7f438519243c3485db928d'
  }
  Signer  = 'Python Software Foundation'
}

# Pinned 2026-09-29 from the .sha256 assets of https://github.com/astral-sh/uv/releases/tag/0.12.19.
$UvPin = @{
  Version = '0.12.19'
  Sha256  = @{
    amd64 = '6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0'
    arm64 = '115b54cb823bc48260670f5782001add6067ac8d98d18c8263a833704e287de9'
  }
}

if (-not $Arch) {
  # PROCESSOR_ARCHITEW6432 is set in a 32-bit process on a 64-bit OS.
  $native = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
  switch ($native) {
    'AMD64' { $Arch = 'amd64' }
    'ARM64' { $Arch = 'arm64' }
    default { throw "Unsupported processor architecture '$native' (pinned: amd64, arm64)." }
  }
}

$version = $Pin.Version
$minorTag = (($version -split '\.')[0..1]) -join '.'          # 3.14
$minorDir = (($version -split '\.')[0..1]) -join ''           # 314
$file = "python-$version-$Arch.exe"
$url = "https://www.python.org/ftp/python/$version/$file"
$installer = Join-Path $OutDir $file
$targetDir = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$minorDir"
if ($Arch -eq 'arm64') { $targetDir += '-arm64' }
$python = Join-Path $targetDir 'python.exe'
$python3 = Join-Path $targetDir 'python3.exe'
$storeStubDir = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
$uvVersion = $UvPin.Version
$uvFile = 'uv-' + @{ amd64 = 'x86_64'; arm64 = 'aarch64' }[$Arch] + '-pc-windows-msvc.zip'
$uvUrl = "https://github.com/astral-sh/uv/releases/download/$uvVersion/$uvFile"
$uvZip = Join-Path $OutDir $uvFile
$uvDir = Join-Path $env:USERPROFILE '.local\bin'
$uv = Join-Path $uvDir 'uv.exe'
$uvInstalled = $false

$Findings = New-Object System.Collections.Generic.List[object]
function Add-Finding([string]$Level, [string]$Text) {
  $Findings.Add([pscustomobject]@{ Level = $Level; Text = $Text })
}

function Get-PathDirs([string]$Scope) {
  $raw = [Environment]::GetEnvironmentVariable('Path', $Scope)
  if (-not $raw) { return @() }
  $raw -split ';' | Where-Object { $_ } | ForEach-Object {
    [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\')
  }
}

function Test-SameDir([string]$A, [string]$B) {
  return ($A.TrimEnd('\')) -ieq ($B.TrimEnd('\'))
}

# Every python.exe / python3.exe / py.exe a new session would find, in PATH order (machine PATH, then user PATH),
# with the target folder prepended to the user PATH as the installer does.
function Get-Resolution([bool]$WithTarget) {
  $machine = @(Get-PathDirs 'Machine')
  $user = @(Get-PathDirs 'User')
  if ($WithTarget -and -not ($user | Where-Object { Test-SameDir $_ $targetDir })) { $user = @($targetDir) + $user }
  $result = @{}
  foreach ($name in 'python', 'python3', 'py') {
    $hits = New-Object System.Collections.Generic.List[object]
    foreach ($entry in @($machine | ForEach-Object { @{ Dir = $_; Scope = 'machine' } }) + @($user | ForEach-Object { @{ Dir = $_; Scope = 'user' } })) {
      $candidate = Join-Path $entry.Dir "$name.exe"
      $planned = ($WithTarget -and (Test-SameDir $entry.Dir $targetDir) -and $name -ne 'py')
      if ($planned -or (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        $hits.Add([pscustomobject]@{ Path = $candidate; Dir = $entry.Dir; Scope = $entry.Scope })
      }
    }
    $result[$name] = $hits
  }
  return $result
}

function Get-RegisteredPythons {
  $found = New-Object System.Collections.Generic.List[object]
  $hives = @(
    @{ Key = 'HKCU:\Software\Python'; Scope = 'user' },
    @{ Key = 'HKLM:\Software\Python'; Scope = 'all users' },
    @{ Key = 'HKLM:\Software\WOW6432Node\Python'; Scope = 'all users (32-bit)' }
  )
  foreach ($hive in $hives) {
    if (-not (Test-Path $hive.Key)) { continue }
    foreach ($company in Get-ChildItem $hive.Key -ErrorAction SilentlyContinue) {
      if ($company.PSChildName -eq 'PyLauncher') { continue }
      foreach ($tag in Get-ChildItem $company.PSPath -ErrorAction SilentlyContinue) {
        $props = Get-ItemProperty $tag.PSPath -ErrorAction SilentlyContinue
        $installPath = $null
        $ip = Join-Path $tag.PSPath 'InstallPath'
        if (Test-Path $ip) { $installPath = (Get-ItemProperty $ip -ErrorAction SilentlyContinue).'(default)' }
        $found.Add([pscustomobject]@{
          Scope = $hive.Scope; Company = $company.PSChildName; Tag = $tag.PSChildName
          Version = $props.Version; InstallPath = $installPath
        })
      }
    }
  }
  return $found
}

function Get-FileVersionOf([string]$Exe) {
  try { return (& $Exe -c "import sys; print(sys.version.split()[0])" 2>$null | Select-Object -First 1) } catch { return $null }
}

# ---- 1. Preflight -----------------------------------------------------------------------------------------------
$installedVersion = $null
if (Test-Path -LiteralPath $python) { $installedVersion = Get-FileVersionOf $python }
$alreadyInstalled = ($installedVersion -eq $version)

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  $me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $consoleUser = $null
  try { $consoleUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName } catch { }
  if ($consoleUser -and $consoleUser -ine $me) {
    Add-Finding 'CONFLICT' "Running elevated as $me, but $consoleUser is signed in at the console. The per-user install would go to ${me}'s profile, not ${consoleUser}'s. Run unelevated as the user who will use it."
  } else {
    Add-Finding 'NOTE' "Running elevated (as administrator) as $me. A per-user install needs no admin; it still goes to this user's profile."
  }
}

foreach ($reg in Get-RegisteredPythons) {
  $where = if ($reg.InstallPath) { $reg.InstallPath } else { '(no InstallPath)' }
  $desc = "$($reg.Company) $($reg.Tag) version $($reg.Version) for $($reg.Scope) at $where"
  $sameMinor = ($reg.Company -eq 'PythonCore' -and ($reg.Tag -eq $minorTag -or $reg.Tag -eq "$minorTag-arm64" -or $reg.Tag -eq "$minorTag-32"))
  if ($sameMinor -and $reg.Scope -eq 'user' -and $reg.Version -and $reg.Version -ne $version) {
    Add-Finding 'CONFLICT' "Registered: $desc. Installing $version for this user upgrades it in place (its site-packages stay, the interpreter changes)."
  } elseif ($sameMinor -and $reg.Scope -ne 'user') {
    Add-Finding 'CONFLICT' "Registered: $desc. A second $minorTag for this user sits beside it; which one 'python' and 'py -$minorTag' start depends on PATH and the launcher."
  } elseif ($sameMinor -and $reg.Version -eq $version) {
    Add-Finding 'NOTE' "Registered: $desc (the pinned version)."
  } else {
    Add-Finding 'NOTE' "Registered: $desc (side by side; not changed)."
  }
}
if ($installedVersion -and -not $alreadyInstalled) {
  if (-not ($Findings | Where-Object { $_.Text -like "*upgrades it in place*" })) {
    Add-Finding 'CONFLICT' "$python exists and runs Python $installedVersion. Installing $version would replace it."
  }
}

foreach ($var in 'PYTHONHOME', 'PYTHONPATH') {
  foreach ($scope in 'Process', 'User', 'Machine') {
    $value = [Environment]::GetEnvironmentVariable($var, $scope)
    if ($value) { Add-Finding 'CONFLICT' "$var is set ($scope): '$value'. It points every Python, the new one included, at other library folders. Unset it or confirm it is intended." }
  }
}
foreach ($var in 'PY_PYTHON', 'PY_PYTHON3') {
  $value = [Environment]::GetEnvironmentVariable($var)
  if ($value) { Add-Finding 'NOTE' "${var}=${value}: the py launcher's default version is overridden." }
}

if ((Test-Path -LiteralPath $python3) -and (Test-Path -LiteralPath $python)) {
  $h3 = (Get-FileHash -LiteralPath $python3 -Algorithm SHA256).Hash
  $h = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash
  if ($h3 -ne $h) { Add-Finding 'CONFLICT' "$python3 exists and is not a copy of python.exe. It is left as it is (not overwritten)." }
} elseif ((Test-Path -LiteralPath $python3) -and -not (Test-Path -LiteralPath $python)) {
  Add-Finding 'CONFLICT' "$python3 exists without python.exe beside it. It is left as it is (not overwritten)."
}

try {
  $appx = @(Get-AppxPackage -Name 'PythonSoftwareFoundation.*' -ErrorAction Stop)
  foreach ($pkg in $appx) {
    Add-Finding 'NOTE' "Microsoft Store package $($pkg.Name) $($pkg.Version) is installed. Its python/python3/py aliases live in $storeStubDir and come after the new install on the user PATH."
  }
} catch {
  Add-Finding 'NOTE' "Could not list Store packages (Get-AppxPackage: $($_.Exception.Message))."
}

$allUsersLauncher = Join-Path $env:SystemRoot 'py.exe'
if (Test-Path -LiteralPath $allUsersLauncher) {
  Add-Finding 'NOTE' "An all-users py launcher exists at $allUsersLauncher; the installer may keep it instead of adding a per-user one."
}

$resolution = Get-Resolution $true
foreach ($name in 'python', 'python3') {
  $hits = $resolution[$name]
  if ($hits.Count -eq 0) { continue }
  $winner = $hits[0]
  if (Test-SameDir $winner.Dir $targetDir) {
    foreach ($other in ($hits | Select-Object -Skip 1)) {
      if (-not (Test-SameDir $other.Dir $storeStubDir)) {
        Add-Finding 'NOTE' "Also on PATH, after the new install: $($other.Path)."
      }
    }
  } elseif (Test-SameDir $winner.Dir $storeStubDir) {
    Add-Finding 'NOTE' "'$name' in a new session would start the Store alias $($winner.Path). Turn it off: Settings > Apps > Advanced app settings > App execution aliases."
  } else {
    Add-Finding 'CONFLICT' "'$name' in a new session would start $($winner.Path) ($($winner.Scope) PATH), not the new install: the $($winner.Scope) PATH comes first. Remove it from PATH, or accept that it stays the default."
  }
}

if (-not $SkipUv) {
  if (Test-Path -LiteralPath $uv) {
    $uvSays = try { (& $uv --version 2>$null | Select-Object -First 1) } catch { '' }
    if ("$uvSays" -match "^uv $([regex]::Escape($uvVersion))( |$)") {
      $uvInstalled = $true
      Add-Finding 'NOTE' "uv $uvVersion (the pinned version) is already installed at $uv."
    } else {
      Add-Finding 'CONFLICT' "$uv exists and is not uv ${uvVersion} ('$uvSays'). Installing would replace it."
    }
  }
  $legacyUv = Join-Path $env:USERPROFILE '.cargo\bin\uv.exe'
  $uvElsewhere = @($legacyUv) + @(@(Get-PathDirs 'Machine') + @(Get-PathDirs 'User') | ForEach-Object { Join-Path $_ 'uv.exe' })
  foreach ($other in ($uvElsewhere | Select-Object -Unique)) {
    if ((Test-Path -LiteralPath $other -PathType Leaf) -and -not (Test-SameDir (Split-Path $other) $uvDir)) {
      Add-Finding 'CONFLICT' "Another uv is at $other. With two on PATH the first one runs, and 'uv self update' or pip may move it. Remove it, or accept that both stay."
    }
  }
}

Write-Host "Preflight for Python $version ($Arch), target $targetDir"
if (-not $SkipUv) { Write-Host "Preflight for uv $uvVersion, target $uvDir" }
$conflicts = @($Findings | Where-Object { $_.Level -eq 'CONFLICT' })
foreach ($f in $Findings) { Write-Host "$($f.Level): $($f.Text)" }
if ($Findings.Count -eq 0) { Write-Host 'Preflight: nothing on this host conflicts with the install.' }

if ($conflicts.Count -gt 0 -and -not $AcceptConflicts) {
  Write-Host ''
  Write-Host "STOPPED: $($conflicts.Count) conflict(s) with what is already on this host. Nothing was downloaded or installed."
  Write-Host 'Tell the user each CONFLICT line above and ask how to proceed. To install anyway, rerun with -AcceptConflicts.'
  exit 3
}
if ($CheckOnly) {
  if ($conflicts.Count -gt 0) { exit 3 }
  exit 0
}
if ($conflicts.Count -gt 0) {
  Write-Host "Proceeding despite $($conflicts.Count) conflict(s): -AcceptConflicts was given."
}

# ---- 2-4. Download and verify -------------------------------------------------------------------------------------
if ($alreadyInstalled -and -not $DownloadOnly) {
  Write-Host "Python $version is already installed at ${targetDir}: nothing downloaded or installed."
} else {
  # Windows PowerShell 5.1 may default to TLS 1.0; python.org needs 1.2+.
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

  Write-Host "Downloading $url"
  $oldProgress = $ProgressPreference
  $ProgressPreference = 'SilentlyContinue'  # the progress bar slows Invoke-WebRequest in 5.1 by an order of magnitude
  try {
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
  } finally {
    $ProgressPreference = $oldProgress
  }

  $expected = $Pin.Sha256[$Arch]
  $actual = (Get-FileHash -Path $installer -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    Remove-Item -Path $installer -Force
    Write-Error "SHA-256 mismatch for ${file}: expected $expected, got $actual. File deleted." -ErrorAction Continue
    exit 1
  }
  Write-Host "SHA-256 OK: $actual"

  $sig = Get-AuthenticodeSignature -FilePath $installer
  if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch [regex]::Escape($Pin.Signer)) {
    Remove-Item -Path $installer -Force
    Write-Error "Authenticode check failed for ${file}: status $($sig.Status), signer '$($sig.SignerCertificate.Subject)'. File deleted." -ErrorAction Continue
    exit 1
  }
  Write-Host "Signature OK: $($sig.SignerCertificate.Subject)"

  if ($DownloadOnly) {
    Write-Host "Verified installer: $installer"
  }
}
if (-not $alreadyInstalled -and -not $DownloadOnly) {
  # ---- 5. Install -------------------------------------------------------------------------------------------------
  # Per-user install, documented options: https://docs.python.org/3/using/windows.html#installing-without-ui
  $installArgs = @(
    '/quiet',
    'InstallAllUsers=0',
    'PrependPath=1',
    'Include_launcher=1',
    'InstallLauncherAllUsers=0',
    'Include_test=0',
    'Shortcuts=0'
  )
  Write-Host "Installing Python $version for $env:USERNAME"
  $proc = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
  if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    Write-Error "Installer exited with $($proc.ExitCode). Its logs: $env:TEMP\Python $version*.log" -ErrorAction Continue
    exit 1
  }
  Remove-Item -Path $installer -Force
  if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Installed, but $python is missing." -ErrorAction Continue
    exit 1
  }
}

# ---- 6. python3.exe ---------------------------------------------------------------------------------------------
if (-not $SkipPython3Alias -and -not $DownloadOnly) {
  if (-not (Test-Path -LiteralPath $python3)) {
    New-Item -ItemType HardLink -Path $python3 -Target $python | Out-Null
    Write-Host "Added $python3 (hard link to python.exe; the uninstaller leaves it, delete it by hand)"
  } elseif ((Get-FileHash -LiteralPath $python3 -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash) {
    Write-Host "WARNING: $python3 exists and is not python.exe; left unchanged. 'python3' may not start Python $version."
  }
}

# ---- 7. uv ------------------------------------------------------------------------------------------------------
if (-not $SkipUv) {
  if ($uvInstalled -and -not $DownloadOnly) {
    Write-Host "uv $uvVersion is already installed at ${uv}: nothing downloaded or installed."
  } else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host "Downloading $uvUrl"
    $oldProgress = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
      Invoke-WebRequest -Uri $uvUrl -OutFile $uvZip -UseBasicParsing
    } finally {
      $ProgressPreference = $oldProgress
    }
    $expected = $UvPin.Sha256[$Arch]
    $actual = (Get-FileHash -Path $uvZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
      Remove-Item -Path $uvZip -Force
      Write-Error "SHA-256 mismatch for ${uvFile}: expected $expected, got $actual. File deleted." -ErrorAction Continue
      exit 1
    }
    Write-Host "SHA-256 OK: $actual"
    if ($DownloadOnly) {
      Write-Host "Verified archive: $uvZip"
    } else {
      $unpacked = Join-Path $OutDir "uv-$uvVersion-unpacked"
      if (Test-Path -LiteralPath $unpacked) { Remove-Item -LiteralPath $unpacked -Recurse -Force }
      Expand-Archive -LiteralPath $uvZip -DestinationPath $unpacked
      New-Item -ItemType Directory -Force -Path $uvDir | Out-Null
      foreach ($exe in 'uv.exe', 'uvx.exe', 'uvw.exe') {
        Copy-Item -LiteralPath (Join-Path $unpacked $exe) -Destination (Join-Path $uvDir $exe) -Force
      }
      Remove-Item -LiteralPath $unpacked -Recurse -Force
      Remove-Item -Path $uvZip -Force
      $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
      if (-not (@(Get-PathDirs 'User') | Where-Object { Test-SameDir $_ $uvDir })) {
        [Environment]::SetEnvironmentVariable('Path', ((@($userPath -split ';' | Where-Object { $_ }) + $uvDir) -join ';'), 'User')
        Write-Host "Added $uvDir to the user PATH"
      }
      Write-Host "Installed uv $uvVersion in $uvDir"
    }
  }
}
if ($DownloadOnly) { exit 0 }

# ---- 8. What a new session starts -------------------------------------------------------------------------------
& $python --version
if (-not $SkipUv) { & $uv --version }
$after = Get-Resolution $false
foreach ($name in 'python', 'python3', 'py') {
  $hits = $after[$name]
  if ($hits.Count -eq 0) { Write-Host "New session: '$name' -> not found"; continue }
  $winner = $hits[0].Path
  Write-Host "New session: '$name' -> $winner"
  if ($name -ne 'py' -and -not (Test-SameDir $hits[0].Dir $targetDir)) {
    Write-Host "WARNING: '$name' in a new session does not start the new install. Tell the user."
  }
}
Write-Host "Done. Open a new terminal (and restart Claude Code) so the new PATH applies, then run /kb-setup."
exit 0
