@echo off
chcp 65001 >nul
setlocal
title BanScreenshot 启动器

rem ============================================================
rem  1) 权限检查：不是管理员就用 UAC 提权重新启动自己
rem     （用 fltmc 判断，比 net session 更可靠，家庭版也能用）
rem ============================================================
fltmc >nul 2>&1
if errorlevel 1 (
    echo 正在向 Windows 申请管理员权限，请在弹窗中点“是”……
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

rem ============================================================
rem  2) 查找 Python（优先 py 启动器，其次 PATH 里的 python）
rem ============================================================
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (where python >nul 2>&1 && set "PY=python")
if not defined PY (
    echo.
    echo [错误] 没有找到 Python。
    echo        请到 https://www.python.org/downloads/ 安装 Python 3.8+，
    echo        安装时记得勾选 “Add python.exe to PATH”。
    echo.
    pause
    exit /b 1
)

rem ============================================================
rem  3) 运行屏蔽程序
rem     常用参数（也可以手动在命令行里加）：
rem       --observe   只记录不屏蔽，用来找出自己误触了哪些组合键
rem       --mode blacklist   只屏蔽黑名单 + Win + PrintScreen
rem       --list      只打印当前配置
rem ============================================================
%PY% "%~dp0ban_shortcut.py" %*

echo.
echo 程序已退出，所有快捷键恢复正常。
pause
