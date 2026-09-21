@echo off
:: Double-click launcher for Windows.
:: Requires uv + dependencies installed: run "uv sync" once in the project folder
cd /d "%~dp0"
uv run --project .. spotify_ad_mute_windows.py
pause
