@echo off
setlocal
title Deploy BanglaDoc Backend to Hugging Face Space

echo ==============================================================
echo  Deploy BanglaDoc Backend to Saddam-nib/bangladoc-api
echo ==============================================================
echo.
echo Create a WRITE token at: https://huggingface.co/settings/tokens
echo.
set /p HF_TOKEN="Paste your Hugging Face WRITE token (hf_...): "

if "%HF_TOKEN%"=="" (
    echo Error: Token cannot be empty.
    pause
    exit /b 1
)

set "STAGE_DIR=%TEMP%\bangladoc_hf_push_%RANDOM%"
mkdir "%STAGE_DIR%"

copy /Y "d:\Ebooks\backend\Dockerfile" "%STAGE_DIR%\" >nul
copy /Y "d:\Ebooks\backend\.dockerignore" "%STAGE_DIR%\" >nul
copy /Y "d:\Ebooks\backend\README.md" "%STAGE_DIR%\" >nul
copy /Y "d:\Ebooks\backend\requirements.txt" "%STAGE_DIR%\" >nul
xcopy /E /I /Y "d:\Ebooks\backend\app" "%STAGE_DIR%\app" >nul

cd /d "%STAGE_DIR%"
git init -b main
git config user.name "Saddam-nib"
git config user.email "saddam-nib@users.noreply.huggingface.co"
git add -A
git commit -m "Deploy BanglaDoc FastAPI Docker backend"

echo.
echo Pushing to https://huggingface.co/spaces/Saddam-nib/bangladoc-api ...
git push --force "https://Saddam-nib:%HF_TOKEN%@huggingface.co/spaces/Saddam-nib/bangladoc-api" main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================
    echo  SUCCESS! Hugging Face is now building your Docker container!
    echo  Watch build progress at:
    echo  https://huggingface.co/spaces/Saddam-nib/bangladoc-api
    echo ==============================================================
) else (
    echo.
    echo Push failed. Make sure your token has WRITE permission on Spaces.
)

cd /d d:\Ebooks
rmdir /S /Q "%STAGE_DIR%"
pause
