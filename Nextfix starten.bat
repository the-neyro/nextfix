@echo off
rem Nextfix per Doppelklick starten (Windows): Server starten, Browser oeffnen.
rem Fenster schliessen oder Strg+C beendet Nextfix. Erster Start richtet alles ein (scripts\install.ps1).
cd /d "%~dp0"
if "%NEXTFIX_PORT%"=="" set NEXTFIX_PORT=8000
set ADRESSE=http://localhost:%NEXTFIX_PORT%

rem Laeuft schon (zweiter Doppelklick)? Dann nur den Browser oeffnen.
curl.exe -s -o nul --max-time 1 %ADRESSE% && (
  echo Nextfix laeuft schon, oeffne %ADRESSE%
  start "" %ADRESSE%
  exit /b 0
)

rem Erster Start: Python-Umgebung einrichten (dauert ein paar Minuten, nur einmal)
if not exist ".venv\Scripts\uvicorn.exe" (
  echo Erster Start: richte Nextfix ein, einmalig, ein paar Minuten ...
  set NEXTFIX_START=nein
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
  if errorlevel 1 (
    echo Einrichtung fehlgeschlagen, siehe Meldungen oben.
    pause
    exit /b 1
  )
)

echo Starte Nextfix ... zum Beenden dieses Fenster schliessen oder Strg+C
rem Browser oeffnen, sobald der Server antwortet (laeuft im Hintergrund im selben Fenster)
start "" /b powershell -NoProfile -Command "for ($i = 0; $i -lt 30; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 '%ADRESSE%' | Out-Null; Start-Process '%ADRESSE%'; break } catch { Start-Sleep 1 } }"
".venv\Scripts\uvicorn.exe" app.web:app --port %NEXTFIX_PORT%
if errorlevel 1 (
  echo Nextfix liess sich nicht starten, siehe Meldungen oben.
  pause
)
