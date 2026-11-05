@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0Send-DirectoryInventory.ps1" -AgentConfig "%~dp0agent.local.json" -Watch
pause
