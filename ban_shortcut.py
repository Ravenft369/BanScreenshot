#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BanScreenshot —— 玩游戏时屏蔽误触的截图 / 系统组合快捷键（Windows）
=====================================================================

原理
----
安装一个“低层键盘钩子”（WH_KEYBOARD_LL），按键在送达系统与其它程序之前先经过
本程序判断；命中屏蔽规则的按键会被直接吞掉（不再向下传递），因此截图、
Win 组合之类由系统/其它软件注册的快捷键根本不会被触发。

只用 Python 标准库（ctypes），不需要安装任何第三方包。

默认行为
--------
* 白名单模式：凡是含 Ctrl / Alt / Win 的组合键一律屏蔽，只放行 ALLOW_COMBOS
  中列出的“基本编辑快捷键”（Ctrl+C/V/X/Z 等）。
* 左/右 Win 键整键屏蔽，PrintScreen 整键屏蔽（于是 Win+PrtScn、
  Win+Shift+S、Alt+PrtScn 等截图组合全部失效）。
* 不含 Ctrl/Alt/Win 的普通按键（游戏按键、Shift+键等）全部正常。
* 黑名单里额外列出常见截图热键（QQ 的 Ctrl+Alt+A、微信的 Alt+A 等）。

热键
----
* Ctrl+Alt+F12        暂停 / 恢复屏蔽（暂停后 Alt+Tab 等立即恢复正常，方便切出去）
* Ctrl+Alt+Shift+F12  退出程序
* Ctrl+C              退出程序（控制台里按）
* Ctrl+Alt+Del        【保留】Windows 安全注意序列，任何程序都拦不住，可作应急出口

配置文件 / 命令行参数
---------------------
生效优先级：**命令行参数 > ban_shortcut.ini > 程序内置默认值**。

* `ban_shortcut.ini` —— 只要和本程序（或 BanScreenshot.exe）放在同一目录就会
  自动生效；首次运行会生成一份带中文注释的模板，用记事本改完保存即可。
  想放在别处就用 `--config 路径` 指定。
* 命令行参数可以临时覆盖，例如：
    --mode whitelist|blacklist   切换工作模式
    --allow "ctrl+w ctrl+t"      追加放行的组合键
    --block "ctrl+alt+p"         追加屏蔽的组合键
    --extra-keys "f12 f10"       追加整键屏蔽
    --no-win / --no-prtsc        不屏蔽 Win 键 / PrintScreen
    --observe                    只记录不屏蔽（侦察模式）
    --quiet                      不打印每次拦截记录
    --list                       打印当前生效的配置后退出
    --save-config [路径] [--force]   生成一份默认配置文件
    --config 路径                指定配置文件位置
    --no-elevate                 不自动请求管理员权限
    --self-test                  不装钩子，只自检判定逻辑（固定用内置默认值）

用法
----
    （推荐双击 exe，或双击 run_as_admin.bat）
    BanScreenshot.exe                        # 打包后：双击即用
    python ban_shortcut.py                   # 正常屏蔽
    python ban_shortcut.py --observe         # 只记录不屏蔽：先看看自己误触了哪些组合键
    python ban_shortcut.py --mode blacklist  # 只屏蔽黑名单 + Win + PrtScn

打包成 exe
----------
    双击 build_exe.bat，产物为 dist\\BanScreenshot.exe（单文件，可直接拷走）。
    启动时会自动请求管理员权限；首次运行会在 exe 同目录生成 ban_shortcut.ini。

注意
----
* 建议用管理员权限运行：当游戏本身以管理员身份运行时，非管理员进程的钩子
  看不到发给它的按键。程序默认会自动弹 UAC 提权（可用 --no-elevate 关掉）。
* 极少数带内核级反作弊的游戏会拦截键盘钩子；此时请用 README 里的“注册表方案”。
* 关闭本程序（或按热键退出）后一切恢复原样，不会留下任何系统改动。
"""

from __future__ import annotations

import argparse
import configparser
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
from ctypes import wintypes as wt

# ===========================================================================
#                    内置默认配置（可被 配置文件 / 命令行 覆盖）
# ---------------------------------------------------------------------------
#  这里只是“没有找到配置文件时”的默认值。
#  日常调整请改同目录下的 ban_shortcut.ini（首次运行自动生成），
#  或用命令行参数临时覆盖 —— 改那边不需要动这个源文件。
# ===========================================================================

# 工作模式：
#   "whitelist" —— 白名单：含 Ctrl / Alt / Win 的组合键一律屏蔽，
#                  只有 ALLOW_COMBOS 里列出的才放行。（推荐，按你的要求）
#   "blacklist" —— 黑名单：只屏蔽 BLOCK_COMBOS + 全部 Win 组合 + PrintScreen。
#                  想让游戏自己也能用 Ctrl/Alt 组合键时用这个。
MODE = "whitelist"

# 白名单：即使是组合键也放行的“基本编辑快捷键”（空格分隔，每行一个也行）
ALLOW_COMBOS = """
    ctrl+c          # 复制
    ctrl+v          # 粘贴
    ctrl+x          # 剪切
    ctrl+z          # 撤销
    ctrl+y          # 重做
    ctrl+a          # 全选
    ctrl+s          # 保存
    ctrl+f          # 查找
    ctrl+shift+z    # 重做（部分软件）
    ctrl+shift+c    # 终端 / 浏览器开发者工具里的复制
    ctrl+shift+v    # 终端 / 浏览器里的粘贴
    ctrl+shift+esc  # 任务管理器：留一个应急出口，不需要可以删掉
    alt+enter       # 游戏 / 播放器切换全屏；不想放行就删掉
"""

# 黑名单：无论什么模式都一定屏蔽的组合键（不分左右；lwin/rwin 一律写 win）
BLOCK_COMBOS = """
    alt+tab         # 切换窗口（音游里非常容易误触）
    alt+shift+tab
    alt+esc         # 在窗口之间循环
    alt+space       # 窗口系统菜单
    alt+f4          # 关闭当前窗口 —— 误触直接把游戏关掉，所以默认屏蔽
    ctrl+esc        # 开始菜单
    ctrl+alt+a      # QQ 截图（默认热键）
    alt+a           # 微信截图（默认热键）
    ctrl+shift+a    # 钉钉 / 搜狗等输入法的截图热键
    ctrl+shift+s    # 浏览器“网页截图”类扩展
    ctrl+alt+s      # 部分截图 / 录屏工具
    ctrl+alt+q      # 部分录屏工具
    # 说明：Ctrl+Alt+Del 属于 Windows 安全注意序列，任何用户态程序都无法拦截，
    #       也不需要写在这里。
"""

# 切换 / 退出热键（这两个组合即使被上面屏蔽，也会被优先识别）
TOGGLE_COMBO = "ctrl+alt+f12"        # 暂停 / 恢复屏蔽
EXIT_COMBO = "ctrl+alt+shift+f12"    # 退出程序

BLOCK_WIN_KEY = True        # 完全屏蔽左/右 Win 键（所有 Win 组合随之失效）
BLOCK_PRTSCN = True         # 屏蔽 PrintScreen 整键（含 Alt+PrtScn、Ctrl+PrtScn）
EXTRA_BLOCKED_KEYS = "f12"  # 额外要整键屏蔽的键，空格分隔，如 "f12 f10"；留空 = 不屏蔽
#                            （F12 是 Steam 默认截图键，不需要就把这里改成 ""）
VERBOSE = True              # 每次拦截都在控制台打印一行记录
AUTO_ELEVATE = True         # 启动时若没有管理员权限，自动弹 UAC 重新启动自己
CONFIG_FILE_NAME = "ban_shortcut.ini"   # 配置文件名字（放在 exe/脚本同目录）
VERSION = "1.0.1"           # 版本号（发新版时记得改，会显示在启动信息里）

# 记下内置默认值，--self-test 用它们做确定性测试（不受用户配置影响）
_BUILTIN_DEFAULTS = {
    "MODE": MODE,
    "ALLOW_COMBOS": ALLOW_COMBOS,
    "BLOCK_COMBOS": BLOCK_COMBOS,
    "TOGGLE_COMBO": TOGGLE_COMBO,
    "EXIT_COMBO": EXIT_COMBO,
    "BLOCK_WIN_KEY": BLOCK_WIN_KEY,
    "BLOCK_PRTSCN": BLOCK_PRTSCN,
    "EXTRA_BLOCKED_KEYS": EXTRA_BLOCKED_KEYS,
}

# --save-config / 首次运行时生成的配置文件内容（注释是给用户看的）
DEFAULT_CONFIG_INI = """\
; ============================================================
;  BanScreenshot 配置文件
;  放在 BanScreenshot.exe（或 ban_shortcut.py）同一目录即生效
; ------------------------------------------------------------
;  · 用记事本改完保存即可
;  · # 或 ; 之后是注释；把某行删掉或前面加 # 就等于不启用该项
;  · 修饰键不分左右：lwin / rwin 一律写 win
;  · 名字有别名：printscreen、control、escape、del、pgup 都能认
;  · 组合键写法：ctrl+alt+f12 、win+shift+s 、alt+tab ……
;  · 本文件的值会被命令行参数覆盖（如 --mode / --allow / --block）
; ============================================================

[general]
; 工作模式：
;   whitelist = 白名单：含 Ctrl / Alt / Win 的组合键一律屏蔽，只放行 [allow] 里的
;   blacklist = 黑名单：只屏蔽 [block] 里的 + 所有 Win 组合 + PrintScreen
mode = whitelist

; 是否整键屏蔽左/右 Win 键（屏蔽后所有 Win+X 组合都失效，截图也在其中）
block_win_key = true

; 是否整键屏蔽 PrintScreen（含 Alt+PrtScn、Ctrl+PrtScn）
block_prtsc = true

; 额外要整键屏蔽的键，例如 Steam 的默认截图键 f12；留空 = 不屏蔽任何额外键
extra_blocked_keys = f12

; 是否在控制台打印每一次拦截记录
verbose = true

; 启动时若没有管理员权限，是否自动弹 UAC 重新启动（建议 true）
auto_elevate = true

[hotkeys]
; 暂停 / 恢复屏蔽（暂停后 Alt+Tab 等立刻恢复正常）
toggle = ctrl+alt+f12
; 退出程序
exit = ctrl+alt+shift+f12

[allow]
; 白名单：白名单模式下，这些组合键依然放行（每项一行）
;   · 想“一个都不放行”（连 Ctrl+C 也拦），保留 combos = 但把下面的项全删掉
;   · 想恢复程序内置的默认名单，把整个 [allow] 节删掉即可
combos =
    ctrl+c
    ctrl+v
    ctrl+x
    ctrl+z
    ctrl+y
    ctrl+a
    ctrl+s
    ctrl+f
    ctrl+shift+z
    ctrl+shift+c
    ctrl+shift+v
    ctrl+shift+esc
    alt+enter

[block]
; 黑名单：任何模式下都屏蔽（包括纯 Shift 组合）
;   · 这里清空 = 只保留 Win 组合 + PrintScreen 这两个整键规则
;   · 想恢复内置默认名单，把整个 [block] 节删掉即可
combos =
    alt+tab
    alt+shift+tab
    alt+esc
    alt+space
    alt+f4
    ctrl+esc
    ctrl+alt+a
    alt+a
    ctrl+shift+a
    ctrl+shift+s
    ctrl+alt+s
    ctrl+alt+q
"""

# ===========================================================================
#                        Win32 常量 / 结构体 / API 声明
# ===========================================================================

WH_KEYBOARD_LL = 13
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

LLKHF_INJECTED = 0x10       # 事件由 SendInput 等程序注入（本程序不处理，直接放行）

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6

VK_SNAPSHOT = 0x2C          # PrintScreen
WIN_VKS = frozenset({0x5B, 0x5C})   # 左 Win / 右 Win

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """低层键盘钩子回调收到的按键信息结构体。"""

    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t
)
PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wt.BOOL, wt.DWORD)

user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, ctypes.c_void_p, wt.DWORD)
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = (
    ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t,
)
user32.UnhookWindowsHookEx.restype = wt.BOOL
user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), ctypes.c_void_p, wt.UINT, wt.UINT)
user32.PeekMessageW.argtypes = (
    ctypes.POINTER(wt.MSG), ctypes.c_void_p, wt.UINT, wt.UINT, wt.UINT,
)
user32.TranslateMessage.argtypes = (ctypes.POINTER(wt.MSG),)
user32.DispatchMessageW.argtypes = (ctypes.POINTER(wt.MSG),)
user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, ctypes.c_size_t, ctypes.c_ssize_t)

kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.SetConsoleCtrlHandler.argtypes = (PHANDLER_ROUTINE, wt.BOOL)
kernel32.SetConsoleTitleW.argtypes = (wt.LPCWSTR,)
kernel32.GetConsoleProcessList.argtypes = (ctypes.POINTER(wt.DWORD), wt.DWORD)
kernel32.GetConsoleProcessList.restype = wt.DWORD

shell32.IsUserAnAdmin.restype = wt.BOOL
shell32.ShellExecuteW.restype = ctypes.c_void_p
shell32.ShellExecuteW.argtypes = (
    ctypes.c_void_p, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_int,
)

# ===========================================================================
#                          虚拟键码表 / 组合键解析
# ===========================================================================

VK_NAMES: dict[int, str] = {
    0x08: "backspace",
    0x09: "tab",
    0x0D: "enter",
    0x1B: "esc",
    0x20: "space",
    0x21: "pageup",
    0x22: "pagedown",
    0x23: "end",
    0x24: "home",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x2C: "prtsc",
    0x2D: "insert",
    0x2E: "delete",
    0x5B: "win",
    0x5C: "win",
    0x5D: "apps",           # 菜单键
    0x6A: "num*",
    0x6B: "num+",
    0x6D: "num-",
    0x6E: "num.",
    0x6F: "num/",
    0x90: "numlock",
    0x91: "scrolllock",
    0xA0: "lshift",
    0xA1: "rshift",
    0xA2: "lctrl",
    0xA3: "rctrl",
    0xA4: "lalt",
    0xA5: "ralt",
    0xBA: ";",
    0xBB: "=",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDC: "\\",
    0xDD: "]",
    0xDE: "'",
}
for _i in range(10):
    VK_NAMES[0x30 + _i] = chr(0x30 + _i)          # 0-9
for _i in range(26):
    VK_NAMES[0x41 + _i] = chr(ord("a") + _i)      # a-z
for _i in range(24):
    VK_NAMES[0x70 + _i] = f"f{_i + 1}"            # f1-f24
for _i in range(10):
    VK_NAMES[0x60 + _i] = f"num{_i}"              # 小键盘数字

_MOD_VKS = {
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "win", 0x5C: "win",
}

# 修饰键左右两半的虚拟键码（左右只影响物理位置，判定时一律当作同一个键）
_MOD_KEY_VK = {
    "ctrl": 0xA2, "lctrl": 0xA2, "rctrl": 0xA3,
    "shift": 0xA0, "lshift": 0xA0, "rshift": 0xA1,
    "alt": 0xA4, "lalt": 0xA4, "ralt": 0xA5,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
}

# 名字别名：用户写 printscreen / lwin / control 之类也能认
ALIASES = {
    "control": "ctrl", "ctl": "ctrl",
    "escape": "esc",
    "printscreen": "prtsc", "prtscr": "prtsc", "print": "prtsc",
    "lwin": "win", "rwin": "win", "windows": "win", "super": "win", "meta": "win",
    # 左右修饰键统一到一个名字，写 lctrl / rshift 也能认
    "lctrl": "ctrl", "rctrl": "ctrl", "lcontrol": "ctrl", "rcontrol": "ctrl",
    "lshift": "shift", "rshift": "shift",
    "lalt": "alt", "ralt": "alt", "altgr": "alt",
    "del": "delete", "back": "backspace", "return": "enter",
    "pgup": "pageup", "pgdn": "pagedown", "ins": "insert",
    "uparrow": "up", "downarrow": "down", "leftarrow": "left", "rightarrow": "right",
}

MOD_ORDER = ("ctrl", "alt", "shift", "win")


def _parse_combo(token: str) -> frozenset[str]:
    """把 "Ctrl+Shift+Z" 解析成 frozenset({"ctrl", "shift", "z"})。"""
    parts = set()
    for piece in token.lower().split("+"):
        piece = piece.strip()
        if piece:
            parts.add(ALIASES.get(piece, piece))
    return frozenset(parts)


def _split_items(text: str) -> list[str]:
    """把 "ctrl+c, ctrl+v  alt+tab" 拆成 ["ctrl+c", "ctrl+v", "alt+tab"]。"""
    if not text:
        return []
    for sep in (",", "，", ";", "；", "、", "|"):
        text = text.replace(sep, " ")
    return text.split()


def _parse_combo_list(text: str) -> list[frozenset[str]]:
    """把配置区 / 配置文件里的多行文本解析成组合键列表（# ; 之后是注释）。"""
    result = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].split(";", 1)[0]
        for token in _split_items(line):
            result.append(_parse_combo(token))
    return result


_NAME_TO_VK: dict[str, int] = {}
for _vk, _name in sorted(VK_NAMES.items()):
    _NAME_TO_VK.setdefault(_name, _vk)

_unknown_keys: list[str] = []       # 配置里写了但不认识的键名，启动时提示用户


def _build_rules() -> None:
    """根据当前配置（MODE / ALLOW_COMBOS / ... ）重新计算判定用的各个集合。"""
    global ALLOW_SET, BLOCK_SET, TOGGLE_SET, EXIT_SET, EXTRA_BLOCKED_VKS, _unknown_keys
    ALLOW_SET = frozenset(_parse_combo_list(ALLOW_COMBOS))
    BLOCK_SET = frozenset(_parse_combo_list(BLOCK_COMBOS))
    TOGGLE_SET = _parse_combo(TOGGLE_COMBO)
    EXIT_SET = _parse_combo(EXIT_COMBO)
    names = [n.lower() for n in _split_items(EXTRA_BLOCKED_KEYS)]
    EXTRA_BLOCKED_VKS = {_NAME_TO_VK[n] for n in names if n in _NAME_TO_VK}
    _unknown_keys = [n for n in names if n not in _NAME_TO_VK]


ALLOW_SET: frozenset[frozenset[str]] = frozenset()
BLOCK_SET: frozenset[frozenset[str]] = frozenset()
TOGGLE_SET: frozenset[str] = frozenset()
EXIT_SET: frozenset[str] = frozenset()
EXTRA_BLOCKED_VKS: set[int] = set()

_build_rules()      # 先用内置默认值初始化，之后 main() 里会按配置文件重算


def _combo_str(parts: frozenset[str]) -> str:
    """frozenset({"ctrl","alt","a"}) -> "CTRL+ALT+A"（便于阅读/打印）。"""
    mods = [m for m in MOD_ORDER if m in parts]
    keys = sorted(p for p in parts if p not in MOD_ORDER)
    return "+".join(mods + keys).upper()


# ===========================================================================
#                          运行状态 / 日志
# ===========================================================================


class _State:
    def __init__(self) -> None:
        self.held: set[int] = set()          # 当前按住的虚拟键
        self.blocked_down: set[int] = set()  # 已被吞掉“按下”的键（其抬起也要吞）
        self.suspended = False               # 是否已临时暂停屏蔽
        self.blocked_total = 0               # 累计拦截次数


_state = _State()
_thread_id: int | None = None                # 主线程 ID（用于投递退出消息）
_log_queue: queue.SimpleQueue | None = None  # 钩子内不做 I/O，日志丢队列里由别的线程打印
_use_queue = False
_observer = False
_verbose = VERBOSE


def _log(text: str, always: bool = False) -> None:
    if not always and not _verbose:
        return
    if _use_queue and _log_queue is not None:
        _log_queue.put(text)
    else:
        try:
            print(text, flush=True)
        except Exception:
            pass


_last_log_at: dict[str, float] = {}


def _log_throttled(combo: frozenset[str], text: str, interval: float = 0.4) -> None:
    """同一个组合键短时间内的重复记录（按住不放产生的自动重复）只打印一次。"""
    name = _combo_str(combo)
    now = time.monotonic()
    if now - _last_log_at.get(name, 0.0) < interval:
        return
    _last_log_at[name] = now
    _log(text)


def _printer_loop(q: queue.SimpleQueue) -> None:
    while True:
        item = q.get()
        if item is None:
            return
        try:
            print(item, flush=True)
        except Exception:
            pass


def _set_title(text: str) -> None:
    try:
        kernel32.SetConsoleTitleW(text)
    except Exception:
        pass


def _post_quit() -> None:
    """让主线程的 GetMessage 循环退出（只能在消息队列已建立后调用）。"""
    if _thread_id:
        user32.PostThreadMessageW(_thread_id, WM_QUIT, 0, 0)


# ===========================================================================
#                            判定逻辑
# ===========================================================================


def _on_key_down(vk: int) -> bool:
    """返回 True 表示吞掉这个按键（向上不传递）。"""
    mods = {_MOD_VKS[v] for v in _state.held if v in _MOD_VKS}
    is_modifier = vk in _MOD_VKS
    if is_modifier:
        mods.add(_MOD_VKS[vk])
    # 修饰键统一归一成 ctrl / shift / alt / win：左右 Ctrl、左右 Alt 都按同一个键算，
    # 否则“按住左 Ctrl 再按右 Ctrl”会被当成 CTRL+LCTRL 这种根本不存在的组合。
    key = _MOD_VKS.get(vk) or VK_NAMES.get(vk)
    combo = frozenset(mods | {key}) if key else frozenset(mods)
    has_real_key = (not is_modifier) and key is not None

    # 1) 应急热键优先，不受任何模式影响
    if combo == EXIT_SET:
        _log(f"[热键] 收到 {_combo_str(combo)}，退出程序。", always=True)
        _post_quit()
        return True
    if combo == TOGGLE_SET:
        _state.suspended = not _state.suspended
        if _state.suspended:
            _log("[热键] 屏蔽已【暂停】，现在所有快捷键都恢复正常。", always=True)
            _set_title("BanScreenshot - 已暂停")
        else:
            _log("[热键] 屏蔽已【恢复】。", always=True)
            _set_title("BanScreenshot - 屏蔽中")
        return True

    # 2) 观测模式：只记录不拦截
    if _observer:
        if has_real_key or vk in WIN_VKS or vk == VK_SNAPSHOT:
            _log(f"[观测] {_combo_str(combo)}")
        return False

    if _state.suspended:
        return False

    # 3) 整键屏蔽
    block = False
    why = ""
    if BLOCK_WIN_KEY and vk in WIN_VKS:
        block, why = True, "Win 键"
    elif BLOCK_PRTSCN and vk == VK_SNAPSHOT:
        block, why = True, "PrintScreen"
    elif vk in EXTRA_BLOCKED_VKS:
        block, why = True, "指定屏蔽键"

    # 4) 修饰键本身永远放行：
    #    · 游戏常把 Ctrl / Shift / Alt 当键位，按住不放也必须传得进去
    #    · 一旦吞掉 Ctrl 的“按下”，别的程序就收不到 Ctrl，白名单里的 Ctrl+C 也就形同失效
    #    （Win 键若被上面判定为整键屏蔽，block 已是 True，不受这条影响）
    if is_modifier and not block:
        return False

    # 5) 组合键判定
    if not block:
        if combo in ALLOW_SET:
            pass                                   # 白名单放行
        elif combo in BLOCK_SET:
            block, why = True, "黑名单"
        elif MODE == "whitelist" and (mods & {"ctrl", "alt", "win"}):
            block, why = True, "白名单模式：非基本组合"
        elif has_real_key and not mods:
            pass                                   # 光按游戏按键，放行

    if block:
        _state.blocked_down.add(vk)
        _state.blocked_total += 1
        if has_real_key or vk in WIN_VKS or vk == VK_SNAPSHOT:
            _log_throttled(combo, f"[屏蔽] {_combo_str(combo)}    ({why})")
    return block


def _on_key_up(vk: int) -> bool:
    if vk in _state.blocked_down:
        _state.blocked_down.discard(vk)
        return True
    return False


# —— 钩子回调：必须极快，且绝不能抛异常 ——
@HOOKPROC
def _hook_proc(nCode, wParam, lParam):  # noqa: N803 (Win32 命名风格)
    if nCode == HC_ACTION:
        try:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if not (kb.flags & LLKHF_INJECTED):       # 忽略程序注入的按键
                vk = int(kb.vkCode)
                if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                    blocked = _on_key_down(vk)
                    _state.held.add(vk)
                    if blocked:
                        return 1
                elif wParam == WM_KEYUP or wParam == WM_SYSKEYUP:
                    blocked = _on_key_up(vk)
                    _state.held.discard(vk)
                    if blocked:
                        return 1
        except Exception:
            pass
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# ===========================================================================
#                          配置打印 / 自检测试
# ===========================================================================


def _config_text() -> str:
    mode_note = ("（含 Ctrl/Alt/Win 的组合一律屏蔽，除非在白名单里）" if MODE == "whitelist"
                 else "（只屏蔽黑名单 + Win 组合 + PrintScreen）")
    lines = [
        f"版本          : {VERSION}",
        f"配置文件      : {_config_path or '（未找到，使用程序内置默认值）'}",
        f"模式          : {MODE} {mode_note}",
        f"放行白名单    : {', '.join(sorted((_combo_str(c) for c in ALLOW_SET))) or '（空）'}",
        f"强制黑名单    : {', '.join(sorted((_combo_str(c) for c in BLOCK_SET))) or '（无）'}",
        f"Win 键        : {'整键屏蔽' if BLOCK_WIN_KEY else '不屏蔽'}",
        f"PrintScreen   : {'整键屏蔽' if BLOCK_PRTSCN else '不屏蔽'}",
        f"额外屏蔽键    : {', '.join(sorted(set(_split_items(EXTRA_BLOCKED_KEYS)))) or '（无）'}",
        f"暂停/恢复热键 : {_combo_str(TOGGLE_SET)}",
        f"退出热键      : {_combo_str(EXIT_SET)}",
        f"自动提权      : {'是' if AUTO_ELEVATE else '否'}",
    ]
    if _unknown_keys:
        lines.append(f"！不认识的键名: {', '.join(_unknown_keys)}（已忽略，请检查拼写）")
    if _ignored_configs:
        lines.append(f"！存在但未使用的 ini: {', '.join(_ignored_configs)}")
        lines.append("  → 程序只读「自己旁边」那份 ini；改的是另一个是不会生效的")
    return "\n".join(lines)


def _self_test() -> int:
    """不安装钩子，只验证判定逻辑是否符合预期（固定使用内置默认配置）。"""
    global _observer, _verbose

    globals().update(_BUILTIN_DEFAULTS)   # 让自检结果不受用户配置文件影响
    _build_rules()
    _observer = False
    _verbose = True

    cases: list[tuple[str, int, tuple[str, ...], bool]] = [
        ("Ctrl+C 复制要放行", 0x43, ("ctrl",), False),
        ("Ctrl+V 粘贴要放行", 0x56, ("ctrl",), False),
        ("Ctrl+X 剪切要放行", 0x58, ("ctrl",), False),
        ("Ctrl+Z 撤销要放行", 0x5A, ("ctrl",), False),
        ("Ctrl+A 全选要放行", 0x41, ("ctrl",), False),
        ("Ctrl+Shift+Esc 应急出口放行", 0x1B, ("ctrl", "shift"), False),
        ("Ctrl+Shift+S 截图组合要屏蔽", 0x53, ("ctrl", "shift"), True),
        ("Ctrl+Alt+A QQ截图要屏蔽", 0x41, ("ctrl", "alt"), True),
        ("Alt+A 微信截图要屏蔽", 0x41, ("alt",), True),
        ("Alt+Tab 要屏蔽", 0x09, ("alt",), True),
        ("Alt+F4 要屏蔽", 0x73, ("alt",), True),
        ("Alt+Enter 全屏放行", 0x0D, ("alt",), False),
        ("Win 键要屏蔽", 0x5B, (), True),
        ("Win+S 要屏蔽", 0x53, ("win",), True),
        ("Win+Shift+S 要屏蔽", 0x53, ("win", "shift"), True),
        ("PrintScreen 要屏蔽", 0x2C, (), True),
        ("Alt+PrtScn 要屏蔽", 0x2C, ("alt",), True),
        ("F12 (Steam截图) 要屏蔽", 0x7B, (), True),
        ("普通字母键 z 要放行", 0x5A, (), False),
        ("Shift+字母键 要放行", 0x5A, ("shift",), False),
        ("方向键 要放行", 0x26, (), False),
        ("Ctrl+W 默认屏蔽（可加到白名单）", 0x57, ("ctrl",), True),
        # —— 左右修饰键 / 单独按修饰键：以前会被误吞，见 v1.0 修正 ——
        ("单独按左 Ctrl 要放行", 0xA2, (), False),
        ("单独按右 Ctrl 要放行", 0xA3, (), False),
        ("按住左 Ctrl 再按右 Ctrl 要放行", 0xA3, ("lctrl",), False),
        ("按住右 Ctrl 再按左 Ctrl 要放行", 0xA2, ("rctrl",), False),
        ("左右 Ctrl 都按住后按 C 要放行", 0x43, ("lctrl", "rctrl"), False),
        ("按住右 Ctrl 按 C 要放行", 0x43, ("rctrl",), False),
        ("按住右 Ctrl 按 V 要放行", 0x56, ("rctrl",), False),
        ("单独按左 Alt 要放行", 0xA4, (), False),
        ("按住左 Alt 再按右 Alt 要放行", 0xA5, ("lalt",), False),
        ("单独按左 Shift 要放行", 0xA0, (), False),
        ("按住左 Shift 再按右 Shift 要放行", 0xA1, ("lshift",), False),
        ("左右 Ctrl 按住时按 W 仍要屏蔽", 0x57, ("lctrl", "rctrl"), True),
        ("单独按左 Win 仍要屏蔽", 0x5B, (), True),
        ("左 Win + Shift + S 仍要屏蔽", 0x53, ("lwin", "lshift"), True),
    ]

    passed = failed = 0
    print("=== 自检：判定逻辑 ===")
    for desc, vk, mods, expect_block in cases:
        _state.held = {_MOD_KEY_VK[name] for name in mods if name in _MOD_KEY_VK}
        _state.blocked_down.clear()
        got = _on_key_down(vk)
        ok = got == expect_block
        passed += ok
        failed += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}："
              f"期望{'屏蔽' if expect_block else '放行'}，"
              f"实际{'屏蔽' if got else '放行'}")
    _state.held.clear()
    print(f"=== 自检结束：{passed} 通过，{failed} 失败 ===")
    return 0 if failed == 0 else 1


# ===========================================================================
#                    配置文件 / 命令行参数 / 自动提权
# ===========================================================================

_config_path: str | None = None      # 实际生效的配置文件；None = 使用内置默认值
_ignored_configs: list[str] = []     # 同样存在、但按优先级没被使用的其它 ini（用于提示）


def _app_dir() -> str:
    """exe（已打包）或脚本所在目录 —— 配置文件默认就找这里。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _default_config_path() -> str:
    return os.path.join(_app_dir(), CONFIG_FILE_NAME)


def _config_candidates() -> list[str]:
    """按优先级列出所有可能的位置：① 程序/exe 同目录 ② 当前工作目录。"""
    candidates: list[str] = []
    for folder in (_app_dir(), os.getcwd()):
        path = os.path.join(folder, CONFIG_FILE_NAME)
        if path not in candidates:
            candidates.append(path)
    return candidates


def _find_config_file() -> str | None:
    """exe 永远优先读自己旁边的那份 ini。"""
    for path in _config_candidates():
        if os.path.isfile(path):
            return path
    return None


def _as_bool(text: str | None, default: bool) -> bool:
    value = (text or "").strip().lower()
    if value in ("1", "true", "yes", "on", "是", "开"):
        return True
    if value in ("0", "false", "no", "off", "否", "关"):
        return False
    return default


def _load_config_file(path: str) -> None:
    """读取 ini，覆盖内置默认值（只覆盖文件里确实写了的项）。"""
    global MODE, ALLOW_COMBOS, BLOCK_COMBOS, TOGGLE_COMBO, EXIT_COMBO
    global BLOCK_WIN_KEY, BLOCK_PRTSCN, EXTRA_BLOCKED_KEYS, VERBOSE, AUTO_ELEVATE
    global _config_path

    parser = configparser.ConfigParser(
        interpolation=None, inline_comment_prefixes=("#", ";"),
    )
    parser.read(path, encoding="utf-8-sig")
    _config_path = path

    if parser.has_section("general"):
        g = parser["general"]
        mode = (g.get("mode") or "").strip().lower()
        if mode in ("whitelist", "blacklist"):
            MODE = mode
        BLOCK_WIN_KEY = _as_bool(g.get("block_win_key"), BLOCK_WIN_KEY)
        BLOCK_PRTSCN = _as_bool(g.get("block_prtsc"), BLOCK_PRTSCN)
        if g.get("extra_blocked_keys") is not None:
            EXTRA_BLOCKED_KEYS = g.get("extra_blocked_keys") or ""
        VERBOSE = _as_bool(g.get("verbose"), VERBOSE)
        AUTO_ELEVATE = _as_bool(g.get("auto_elevate"), AUTO_ELEVATE)

    if parser.has_section("hotkeys"):
        h = parser["hotkeys"]
        if (h.get("toggle") or "").strip():
            TOGGLE_COMBO = h.get("toggle").strip()
        if (h.get("exit") or "").strip():
            EXIT_COMBO = h.get("exit").strip()

    # 注意语义差别：
    #   `combos =` 存在但列表为空 —— 明确表示“一个都不放行 / 一个都不额外屏蔽”
    #   整节删掉（或没有该项）   —— 沿用程序内置默认名单
    if parser.has_option("allow", "combos"):
        ALLOW_COMBOS = parser["allow"].get("combos") or ""
    if parser.has_option("block", "combos"):
        BLOCK_COMBOS = parser["block"].get("combos") or ""


def _write_config_file(path: str, overwrite: bool = False) -> bool:
    """写出一份带注释的默认配置文件。已存在且不允许覆盖时返回 False。"""
    try:
        if os.path.exists(path) and not overwrite:
            return False
        folder = os.path.dirname(os.path.abspath(path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write(DEFAULT_CONFIG_INI)
        return True
    except OSError as exc:
        print(f"[警告] 写入配置文件失败：{path}（{exc}）")
        return False


def _is_admin() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate_self(argv: list[str]) -> bool:
    """用 UAC 以管理员身份重新启动自己；成功发起返回 True。"""
    try:
        if getattr(sys, "frozen", False):        # 已打包成 exe
            exe, params = sys.executable, subprocess.list2cmdline(argv)
        else:                                     # 直接跑 .py
            exe = sys.executable
            params = subprocess.list2cmdline([os.path.abspath(sys.argv[0]), *argv])
        result = shell32.ShellExecuteW(None, "runas", exe, params, _app_dir(), 1)
        return bool(result) and int(result) > 32
    except Exception:
        return False


def _console_will_close() -> bool:
    """控制台里只有本进程时，退出后窗口会立刻消失（典型情况：双击 exe）。"""
    try:
        pids = (wt.DWORD * 8)()
        return kernel32.GetConsoleProcessList(pids, 8) <= 1
    except Exception:
        return False


def _pause_before_exit() -> None:
    """双击运行时留个“按回车退出”，否则出错信息会一闪而过看不见。"""
    if not _console_will_close():
        return
    try:
        input("\n按回车键退出……")
    except Exception:
        pass


# ===========================================================================
#                                主程序
# ===========================================================================


def _install_console_handler() -> None:
    @PHANDLER_ROUTINE
    def handler(event):  # noqa: ANN001
        if event in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT,
                     CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            _log("[退出] 收到控制台关闭/中断信号，正在卸载键盘钩子……", always=True)
            _post_quit()
            return True
        return False

    kernel32.SetConsoleCtrlHandler(handler, True)
    globals()["_console_handler_ref"] = handler   # 防止被 GC


def main(argv: list[str] | None = None) -> int:
    global MODE, ALLOW_COMBOS, BLOCK_COMBOS, EXTRA_BLOCKED_KEYS
    global BLOCK_WIN_KEY, BLOCK_PRTSCN, AUTO_ELEVATE
    global _observer, _verbose, _use_queue, _log_queue, _thread_id, _config_path
    global _ignored_configs

    parser = argparse.ArgumentParser(
        description="玩游戏时屏蔽误触的截图 / 系统组合快捷键（Windows 键盘钩子）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="配置文件：程序目录下的 %s（首次运行自动生成，命令行参数优先级更高）"
               % CONFIG_FILE_NAME,
    )
    parser.add_argument("--mode", choices=["whitelist", "blacklist"],
                        help="工作模式：白名单（默认）/ 黑名单")
    parser.add_argument("--allow", metavar="组合键", default="",
                        help='追加放行的组合键，如 --allow "ctrl+w ctrl+t"')
    parser.add_argument("--block", metavar="组合键", default="",
                        help='追加屏蔽的组合键，如 --block "ctrl+alt+p"')
    parser.add_argument("--extra-keys", metavar="键名", default="",
                        help='追加整键屏蔽，如 --extra-keys "f12 f10"')
    parser.add_argument("--no-win", action="store_true", help="不屏蔽 Win 键")
    parser.add_argument("--no-prtsc", action="store_true", help="不屏蔽 PrintScreen")
    parser.add_argument("--config", metavar="路径", help="指定配置文件位置")
    parser.add_argument("--save-config", nargs="?", const="", default=None,
                        metavar="路径", help="生成一份默认配置文件后退出")
    parser.add_argument("--force", action="store_true", help="配合 --save-config 覆盖已有文件")
    parser.add_argument("--no-elevate", action="store_true", help="不自动请求管理员权限")
    parser.add_argument("--observe", action="store_true",
                        help="只记录不屏蔽，用来找出自己误触了哪些组合键")
    parser.add_argument("--quiet", action="store_true", help="不打印每次拦截记录")
    parser.add_argument("--duration", type=float, default=0,
                        help="运行 N 秒后自动退出（自测用）")
    parser.add_argument("--list", action="store_true", help="只打印当前生效配置后退出")
    parser.add_argument("--self-test", action="store_true",
                        help="不安装钩子，只测试判定逻辑（固定用内置默认值）")
    args = parser.parse_args(argv)

    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    # ---- 1) 读配置文件（命令行的 --config 优先）----
    if args.config:
        config_path: str | None = os.path.abspath(args.config)
        if not os.path.isfile(config_path):
            print(f"[错误] 找不到配置文件：{config_path}")
            _pause_before_exit()
            return 2
    else:
        config_path = _find_config_file()
    if config_path:
        try:
            _load_config_file(config_path)
        except (configparser.Error, OSError, UnicodeDecodeError) as exc:
            print(f"[错误] 读取配置文件失败：{config_path}")
            print(f"       {exc}")
            print("       提示：多行列表（combos = 下面那些行）每一项都要缩进；")
            print("             也可以用记事本“另存为”UTF-8 编码再试。")
            _pause_before_exit()
            return 2

    # 另一个位置也存在 ini 却没被读取 —— 这正是“改了配置却不生效”的常见原因
    _ignored_configs = [
        path for path in _config_candidates()
        if path != _config_path and os.path.isfile(path)
    ]

    # ---- 2) 命令行参数覆盖 ----
    if args.mode:
        MODE = args.mode
    if args.allow:
        ALLOW_COMBOS = f"{ALLOW_COMBOS}\n{args.allow}\n"
    if args.block:
        BLOCK_COMBOS = f"{BLOCK_COMBOS}\n{args.block}\n"
    if args.extra_keys:
        EXTRA_BLOCKED_KEYS = f"{EXTRA_BLOCKED_KEYS} {args.extra_keys}"
    if args.no_win:
        BLOCK_WIN_KEY = False
    if args.no_prtsc:
        BLOCK_PRTSCN = False
    _observer = args.observe
    _verbose = VERBOSE
    if args.quiet:
        _verbose = False
    _build_rules()

    # ---- 3) 只做一件事就退出的开关 ----
    if args.self_test:
        return _self_test()
    if args.save_config is not None:
        target = os.path.abspath(args.save_config) if args.save_config else _default_config_path()
        if _write_config_file(target, overwrite=args.force):
            print(f"已生成配置文件：{target}")
            print("用记事本打开它，就能自定义要屏蔽 / 放行哪些快捷键。")
            return 0
        print(f"[错误] 文件已存在：{target}（要覆盖请加 --force）")
        _pause_before_exit()
        return 2
    if args.list:
        print(_config_text())
        return 0

    # ---- 4) 没有配置文件就自动生成一份，方便用户改 ----
    if config_path is None:
        target = _default_config_path()
        if _write_config_file(target, overwrite=False):
            _config_path = target
            print(f"[提示] 已生成配置文件：{target}")
            print("       想自定义屏蔽 / 放行哪些快捷键，用记事本改它就行。")
        else:
            print("[提示] 未能生成配置文件（目录不可写？），本次使用内置默认值；")
            print("       可以加 --save-config 指定别的位置。")

    # ---- 5) 需要管理员权限时自动提权 ----
    if AUTO_ELEVATE and not args.no_elevate and not _is_admin():
        print("[提示] 正在请求管理员权限（UAC 弹窗请点“是”）……")
        if _elevate_self(raw_argv):
            return 0
        print("[警告] 提权被取消或失败，将以普通权限继续；")
        print("       若游戏是管理员身份运行的，可能拦不到发给它的按键。")

    # —— 启动日志线程（钩子里不做 I/O，避免拖慢游戏输入）——
    _log_queue = queue.SimpleQueue()
    _use_queue = True
    printer = threading.Thread(target=_printer_loop, args=(_log_queue,), daemon=True)
    printer.start()

    print("=" * 68)
    print(" BanScreenshot —— 游戏快捷键屏蔽器")
    print("=" * 68)
    print(_config_text())
    print("-" * 68)
    if _observer:
        print(" ★ 观测模式：只记录、不屏蔽。玩一会儿，看下面打印了哪些组合键，")
        print("   再把它们加进 BLOCK_COMBOS（或选择白名单模式）即可。")
    else:
        print(" 屏蔽已开启。误触的组合键会被吞掉，控制台会打印 [屏蔽] 记录。")
    print(f" 暂停/恢复：{_combo_str(TOGGLE_SET)}    退出：{_combo_str(EXIT_SET)} / Ctrl+C")
    print(" 应急：Ctrl+Alt+Del 永远有效（系统保留，任何程序都拦不住）。")
    print("=" * 68)

    if not _observer:
        _set_title("BanScreenshot - 屏蔽中")
    else:
        _set_title("BanScreenshot - 观测中")

    # —— 强制创建消息队列，然后安装钩子 ——
    msg = wt.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
    _thread_id = int(kernel32.GetCurrentThreadId())
    _install_console_handler()

    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_proc, None, 0)
    if not hook:
        err = ctypes.get_last_error()
        print(f"[错误] 安装键盘钩子失败（Win32 错误码 {err}）。")
        print("       请确认已用管理员权限运行；若游戏带有内核级反作弊，请改用 README 的注册表方案。")
        _log_queue.put(None)
        _pause_before_exit()
        return 1

    if args.duration > 0:
        threading.Timer(args.duration, _post_quit).start()

    try:
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnhookWindowsHookEx(hook)
        print("-" * 68)
        if _observer:
            print(" 观测结束（未屏蔽任何按键）。")
        else:
            print(f" 键盘钩子已卸载，累计拦截 {_state.blocked_total} 次，快捷键已全部恢复。")
        print("=" * 68)
        _log_queue.put(None)
        _pause_before_exit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
