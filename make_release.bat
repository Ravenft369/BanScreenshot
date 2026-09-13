@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 发布到 GitHub Releases

rem 直接用 PowerShell 跑 release.ps1
rem   双击：发布默认版本（v1.0.1）
rem   想换版本或清理旧资产：在命令行里传参，例如
rem       make_release.bat -Tag v1.1 -CleanOld

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" %*
if errorlevel 1 (
    echo.
    echo [失败] 请看上面的红色提示。
)

echo.
pause
