@echo off
echo ORCA OS View - Starting...
call conda activate camel-ai
cd /d "%~dp0"
start http://127.0.0.1:5001
python server.py
