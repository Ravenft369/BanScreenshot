@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 打包 BanScreenshot.exe

rem ============================================================
rem  1) 选一个 Python：优先用本目录的 .venv，其次 py 启动器 / PATH
rem ============================================================
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (where py >nul 2>&1 && set "PY=py -3")
if not defined PY (where python >nul 2>&1 && set "PY=python")
if not defined PY (
    echo [错误] 没有找到 Python，请先安装 Python 3.8 或更高版本。
    pause
    exit /b 1
)
echo 使用 Python：%PY%
%PY% -c "import sys; print('版本:', sys.version)"

rem ============================================================
rem  2) 安装 / 更新 PyInstaller
rem ============================================================
echo.
echo [1/3] 检查 PyInstaller ……
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [错误] 安装 PyInstaller 失败，请检查网络后重试。
    pause
    exit /b 1
)

rem ============================================================
rem  3) 打包（单文件、控制台程序）
rem     说明：不加 --uac-admin 清单，改由程序启动时自己请求提权，
rem           这样 --self-test / --list / --save-config 依然可以不提权运行。
rem ============================================================
echo.
echo [2/3] 清理旧产物 ……
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/3] 开始打包 ……
%PY% -m PyInstaller --noconfirm --clean --onefile --console --name BanScreenshot ^
    --exclude-module tkinter --exclude-module pydoc --exclude-module unittest ^
    --exclude-module doctest --exclude-module test ^
    ban_shortcut.py
if errorlevel 1 (
    echo [错误] 打包失败，请看上面的报错信息。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  打包完成： dist\BanScreenshot.exe
echo.
echo   · 一个 exe 就是全部，复制到任意位置双击即可使用
echo   · 启动时会自动请求管理员权限（UAC 点“是”）
echo   · 首次运行会在同目录生成 ban_shortcut.ini，改它即可自定义
echo   · 把 exe 和 ini 一起拷给别人 = 完整部署
echo ============================================================
pause
