@echo off
title BanglaDoc Converter Launcher
echo Starting BanglaDoc Converter Backend (FastAPI on port 8000)...
start "BanglaDoc Backend" cmd /k "cd /d d:\Ebooks\backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting BanglaDoc Converter Frontend (Next.js on port 3000)...
start "BanglaDoc Frontend" cmd /k "cd /d d:\Ebooks\frontend && npm.cmd run dev"

echo.
echo BanglaDoc Converter is launching!
echo Web UI:  http://localhost:3000
echo API Docs: http://127.0.0.1:8000/docs
