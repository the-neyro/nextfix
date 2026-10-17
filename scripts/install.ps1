# Nextfix installieren (Windows, PowerShell), in einer Zeile:
#   irm https://raw.githubusercontent.com/the-neyro/nextfix/main/scripts/install.ps1 | iex
#
# Prüft Python 3.12+, holt das neueste Release nach %USERPROFILE%\nextfix (oder nutzt den Ordner, aus dem das
# Skript läuft), richtet .venv mit allen Paketen und Chromium ein, zeigt den Befehl für Claude Code und startet auf
# Wunsch Nextfix mit der Demo-Website.
# Einstellbar: NEXTFIX_DIR, NEXTFIX_REPO, NEXTFIX_BRANCH (z. B. main statt neuestem Release),
# NEXTFIX_START=ja|nein (ohne Rückfrage).
$ErrorActionPreference = 'Continue'   # Fehler prüfen wir selbst über $LASTEXITCODE

function Wert($name, $standard) { $w = [Environment]::GetEnvironmentVariable($name); if ($w) { $w } else { $standard } }
$Repo = Wert 'NEXTFIX_REPO' 'https://github.com/the-neyro/nextfix.git'
$Branch = Wert 'NEXTFIX_BRANCH' ''
$Ziel = Wert 'NEXTFIX_DIR' (Join-Path $HOME 'nextfix')
$Port = 8000
$DemoPort = 8798

function Schritt($text) { Write-Host "`n$text" -ForegroundColor Cyan }
function Abbruch($text) { Write-Host "`nFehler: $text" -ForegroundColor Red; exit 1 }
function Pruefe($was) { if ($LASTEXITCODE -ne 0) { Abbruch $was } }

# 1. Python 3.12 oder neuer finden (Python-Launcher „py“ zuerst, dann „python“)
Schritt '1/4 Python prüfen'
$PyBefehl = $null
$PyArgs = @()
foreach ($kandidat in @(@{ Befehl = 'py'; Args = @('-3') }, @{ Befehl = 'python'; Args = @() })) {
    if (-not (Get-Command $kandidat.Befehl -ErrorAction SilentlyContinue)) { continue }
    $argumente = $kandidat.Args
    & $kandidat.Befehl @argumente -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>$null
    if ($LASTEXITCODE -eq 0) { $PyBefehl = $kandidat.Befehl; $PyArgs = $argumente; break }
}
if (-not $PyBefehl) { Abbruch 'Nextfix braucht Python 3.12 oder neuer: https://www.python.org/downloads/ (beim Installieren „Add python.exe to PATH“ anhaken)' }
& $PyBefehl @PyArgs --version

# 2. Ordner: läuft das Skript aus einem Nextfix-Ordner, wird der genutzt, sonst klonen bzw. aktualisieren
Schritt '2/4 Nextfix holen'
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot '..\app\web'))) {
    $Ziel = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    Write-Host "Nutze vorhandenen Ordner: $Ziel"
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Abbruch 'git fehlt: https://git-scm.com/download/win' }
    # Standard: neuestes Release (höchstes Tag v…); ohne Release oder mit NEXTFIX_BRANCH: dieser Branch
    if (-not $Branch) {
        $tag = git ls-remote --tags --refs --sort=-v:refname $Repo 'v*' 2>$null | Select-Object -First 1
        $Branch = if ($tag) { ($tag -split 'refs/tags/')[-1] } else { 'main' }
    }
    if (Test-Path (Join-Path $Ziel '.git')) {
        Write-Host "Aktualisiere $Ziel auf $Branch"
        # Tag oder Branch gezielt holen: der flache Klon kennt sonst nur den Stand, mit dem er angelegt wurde
        git -C $Ziel fetch --quiet --depth 1 origin $Branch; Pruefe 'git fetch fehlgeschlagen'
        git -C $Ziel -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD; Pruefe 'git checkout fehlgeschlagen'
    } elseif (Test-Path $Ziel) {
        Abbruch "$Ziel gibt es schon, ist aber kein Nextfix-Ordner. Anderen Ordner wählen: `$env:NEXTFIX_DIR = 'C:\anderer-ordner'"
    } else {
        Write-Host "Hole Nextfix $Branch nach $Ziel"
        git -c advice.detachedHead=false clone --quiet --depth 1 --branch $Branch $Repo $Ziel; Pruefe 'git clone fehlgeschlagen'
    }
}
Set-Location $Ziel

# 3. Python-Umgebung mit allen Paketen und Chromium (für Ladezeit, PDF und JavaScript-Seiten)
Schritt '3/4 Pakete einrichten (beim ersten Mal ein paar Minuten)'
$VenvPy = Join-Path $Ziel '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPy)) {
    & $PyBefehl @PyArgs -m venv .venv; Pruefe 'Python-Umgebung ließ sich nicht anlegen'
}
& $VenvPy -m pip install -q --disable-pip-version-check -r requirements.txt; Pruefe 'Pakete ließen sich nicht installieren'
& $VenvPy -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Hinweis: Chromium fehlt. Website-Check läuft trotzdem, nur Ladezeit, PDF und JavaScript-Seiten nicht.'
}

# 4. Wie starten, und auf Wunsch gleich starten
Schritt '4/4 Fertig'
if (Test-Path (Join-Path $Ziel 'Nextfix starten.bat')) {
    Write-Host "Künftig starten: Doppelklick auf „Nextfix starten.bat“ in $Ziel"
} else {
    Write-Host "Künftig starten: cd `"$Ziel`"; .venv\Scripts\uvicorn app.web:app   -> http://localhost:$Port"
}
Write-Host "`nMit Claude Code verbinden (einmal, dann kennt Claude die Nextfix-Werkzeuge in jedem Ordner):"
Write-Host "  claude mcp add --scope user seo-tool -e PYTHONPATH=`"$Ziel`" -- `"$Ziel\.venv\Scripts\python.exe`" -m app.mcp_server"

$Start = Wert 'NEXTFIX_START' ''
if (-not $Start) {
    if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
        $antwort = Read-Host "`nJetzt starten, mit Demo-Website zum Ausprobieren? [J/n]"
        $Start = if ($antwort -match '^[nN]') { 'nein' } else { 'ja' }
    } else { $Start = 'nein' }
}
if ($Start -ne 'ja') { exit 0 }

$Demo = Start-Process -FilePath $VenvPy -ArgumentList '-m', 'scripts.demo_website', $DemoPort -PassThru -WindowStyle Hidden
try {
    Start-Job -ScriptBlock { param($p) Start-Sleep 3; Start-Process "http://localhost:$p" } -ArgumentList $Port | Out-Null
    Write-Host "`nNextfix läuft auf http://localhost:$Port"
    Write-Host "Demo-Website zum Ausprobieren: Projekt anlegen mit der Start-URL http://127.0.0.1:$DemoPort/"
    Write-Host 'Beenden: Ctrl+C'
    & (Join-Path $Ziel '.venv\Scripts\uvicorn.exe') app.web:app --port $Port
} finally {
    Stop-Process -Id $Demo.Id -ErrorAction SilentlyContinue
}
