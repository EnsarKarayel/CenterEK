@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0Collect-EndpointSessions.ps1" -AgentConfig "%~dp0agent.local.json" -Watch
pause
