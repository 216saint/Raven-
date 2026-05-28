# raven.ps1 - Windows-native launcher for Raven.
# Removes the WSL2 + apt-install-tor dance. Idempotent: re-runs are safe.
#
# Usage:
#   .\raven.ps1                 # default: launches UI on http://localhost:8501
#   .\raven.ps1 -NoTorBundle    # skip Tor portable download (use system tor if running)
#   .\raven.ps1 -SkipInstall    # don't pip install (assume venv is ready)

[CmdletBinding()]
param(
    [switch]$NoTorBundle,
    [switch]$SkipInstall,
    [string]$Port = "8501"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# Tor Expert Bundle - pin a known-good version. Update both the URL and hash together.
# Bundle download page: https://www.torproject.org/download/tor/
$TorBundleUrl = "https://archive.torproject.org/tor-package-archive/torbrowser/13.5.6/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz"
$TorBundleSha256 = "PINNED_HASH_REPLACE_ME"   # see comment below
$ToolsDir = Join-Path $RepoRoot "tools"
$TorDir = Join-Path $ToolsDir "tor"
$TorExe = Join-Path $TorDir "tor\tor.exe"
$RavenStateDir = Join-Path $RepoRoot ".raven"
$TorPidFile = Join-Path $RavenStateDir "tor.pid"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "!! $msg" -ForegroundColor Yellow }
function Write-Err ($msg) { Write-Host "XX $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Step 1: Python 3.10+
# ---------------------------------------------------------------------------
Write-Step "Checking Python ..."
$pythonCmd = $null
foreach ($candidate in @("py -3.12", "py -3.11", "py -3.10", "python")) {
    try {
        $parts = $candidate.Split(" ")
        $exe = $parts[0]
        $args = $parts[1..($parts.Length - 1)] + @("--version")
        $ver = & $exe @args 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3\.(1[0-9]|[2-9][0-9])") {
            $pythonCmd = $candidate
            Write-Host "    found: $ver"
            break
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Warn "Python 3.10+ not found."
    $resp = Read-Host "Install Python 3.12 via winget now? [y/N]"
    if ($resp -match "^[yY]") {
        winget install --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
        $pythonCmd = "py -3.12"
    } else {
        Write-Err "Aborting. Install Python 3.10+ manually and re-run."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 2: venv
# ---------------------------------------------------------------------------
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating virtualenv .venv\ ..."
    Invoke-Expression "$pythonCmd -m venv `"$VenvDir`""
}

# ---------------------------------------------------------------------------
# Step 3: deps
# ---------------------------------------------------------------------------
if (-not $SkipInstall) {
    Write-Step "Installing Python dependencies ..."
    & $VenvPython -m pip install --upgrade pip --quiet
    & $VenvPython -m pip install -r requirements.txt --quiet
}

# ---------------------------------------------------------------------------
# Step 4: Tor portable (optional)
# ---------------------------------------------------------------------------
if (-not $NoTorBundle) {
    if (-not (Test-Path $TorExe)) {
        Write-Step "Downloading Tor Expert Bundle ..."
        New-Item -ItemType Directory -Force -Path $TorDir | Out-Null
        $tarball = Join-Path $TorDir "tor-expert-bundle.tar.gz"
        Invoke-WebRequest -Uri $TorBundleUrl -OutFile $tarball -UseBasicParsing

        if ($TorBundleSha256 -ne "PINNED_HASH_REPLACE_ME") {
            $actual = (Get-FileHash $tarball -Algorithm SHA256).Hash.ToLower()
            if ($actual -ne $TorBundleSha256.ToLower()) {
                Write-Err "Tor bundle SHA-256 mismatch. expected=$TorBundleSha256 actual=$actual"
                Remove-Item $tarball
                exit 1
            }
        } else {
            Write-Warn "Tor bundle SHA-256 not pinned in raven.ps1 - skipping integrity check."
            Write-Warn "Pin a hash from torproject.org and update `$TorBundleSha256."
        }

        # Extract via built-in tar (Windows 10+).
        & tar.exe -xzf $tarball -C $TorDir
        Remove-Item $tarball
    }
}

# ---------------------------------------------------------------------------
# Step 5: start Tor (if portable bundle present and no Tor on 9050 yet)
# ---------------------------------------------------------------------------
function Test-TorRunning {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 9050)
        $tcp.Close()
        return $true
    } catch { return $false }
}

New-Item -ItemType Directory -Force -Path $RavenStateDir | Out-Null

if (Test-TorRunning) {
    Write-Step "Tor already listening on 127.0.0.1:9050 - reusing it."
} elseif (Test-Path $TorExe) {
    Write-Step "Starting Tor ..."
    $torProc = Start-Process -FilePath $TorExe -PassThru -WindowStyle Hidden
    $torProc.Id | Out-File -Encoding ascii $TorPidFile
    # Best-effort wait for bootstrap (10s) - not strictly required, scrape will retry.
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-TorRunning) { break }
    }
    if (-not (Test-TorRunning)) {
        Write-Warn "Tor did not open 9050 within 10s - scrape may fail until it bootstraps."
    }
} else {
    Write-Warn "No system Tor and -NoTorBundle was set. Scraping .onion will fail."
}

# ---------------------------------------------------------------------------
# Step 6: Streamlit
# ---------------------------------------------------------------------------
Write-Step "Launching Raven on http://localhost:$Port ..."
try {
    & $VenvPython -m streamlit run ui.py --server.port $Port --server.headless true
} finally {
    # ---------------------------------------------------------------------------
    # Step 7: teardown
    # ---------------------------------------------------------------------------
    if (Test-Path $TorPidFile) {
        $torPid = Get-Content $TorPidFile -ErrorAction SilentlyContinue
        if ($torPid) {
            try { Stop-Process -Id $torPid -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item $TorPidFile -ErrorAction SilentlyContinue
    }
}
