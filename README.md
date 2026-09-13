# BanScreenshot —— 玩游戏时不再误触截图 / 系统快捷键

音游里同时按一堆键，很容易误触系统快捷键，尤其是 **截图**（Windows 自己就有好几种触发方式）。
这个小工具在后台装一个**低层键盘钩子**（`WH_KEYBOARD_LL`），在按键送达系统和其它程序**之前**
先把命中的快捷键吞掉，于是截图之类的事情根本不会发生。

- 🎮 **只屏蔽组合快捷键**：`Ctrl+C/V/X/Z` 等基本编辑键照常可用，普通游戏按键完全不受影响
- 🖼️ **截图全灭**：`PrtScn`、`Alt+PrtScn`、`Win+Shift+S`、`Win+PrtScn`、`Win+Alt+PrtScn`、
  `Ctrl+Alt+A`(QQ)、`Alt+A`(微信)、`F12`(Steam) …
- ⚙️ **配置文件即改即用**：`ban_shortcut.ini` 改完保存，不用重新编译
- 🪶 **零依赖**：单文件 exe 或纯标准库 Python 脚本，关闭后**不修改注册表、不留任何系统改动**
- 🔍 **侦察模式**：`--observe` 只记录不屏蔽，先看清自己到底误触了哪些组合键

---

## 下载即用

不想折腾 Python？到 **[Releases](../../releases/latest)** 下载 `BanScreenshot.exe`：

1. 双击运行（会弹 UAC，点“是”）
2. 首次运行会在同目录生成 `ban_shortcut.ini`，想自定义就改它
3. 玩游戏时误触的快捷键会被吞掉；`Ctrl+Alt+F12` 暂停/恢复屏蔽，`Ctrl+Alt+Shift+F12` 退出

> 需要 64 位 Windows。程序不联网、不写注册表，源码全在上面，可自行审阅或打包。

---

## 快速开始

1. 运行 `BanScreenshot.exe`（从 Releases 下载，或本地 `build_exe.bat` 打包后取 `dist\BanScreenshot.exe`），
   或直接双击 `run_as_admin.bat` 用 Python 版（会弹 UAC，点“是”）
2. 正常玩游戏，控制台会实时打印 `[屏蔽] CTRL+SHIFT+S  (白名单模式：非基本组合)` 之类记录
3. 需要切出去看网页时：按 **`Ctrl+Alt+F12`** 暂停屏蔽，再 `Alt+Tab`；
   回来再按一次 `Ctrl+Alt+F12` 恢复
4. 退出：按 **`Ctrl+Alt+Shift+F12`**，或者直接在控制台按 `Ctrl+C` / 关掉窗口

首次运行会在 exe 同目录生成 `ban_shortcut.ini`，所有可调项都在里面。

> 应急出口：**`Ctrl+Alt+Del`** 是 Windows 的安全注意序列，任何程序都拦不住它，
> 所以哪怕程序出问题，你也可以随时用它切到任务管理器。

---

## 打包成 exe（部署给别的机器也一样简单）

```bat
:: 双击运行即可（会自动装 PyInstaller，然后打包）
build_exe.bat
```

产物是 **`dist\BanScreenshot.exe`**，单文件、无需 Python 环境：

- 复制到任意目录，**双击就启动**（程序会自己弹 UAC 请求管理员权限）
- 首次运行在 exe 同目录生成 `ban_shortcut.ini`
- **exe + ini 一起拷给别人 = 完整部署**，对方什么都不用装

> 想让某个游戏固定一套配置？把 exe 和对应 ini 一起放进那个游戏的文件夹，
> 双击 exe 时它会优先读自己旁边的 ini。

### 发布到 GitHub Releases（维护者用）

1. `build_exe.bat` 打包
2. 改 `ban_shortcut.py` 里的 `VERSION`（会显示在启动信息第一行）
3. 双击 `make_release.bat` 发布默认版本；换版本 / 清理旧资产：
   `make_release.bat -Tag v1.1 -CleanOld`
   删除某个旧 Release（只删 Release，git tag 保留）：
   `make_release.bat -DeleteRelease v1.0`

`release.ps1` 会自动：从 Git 凭据管理器读取已缓存的 GitHub 凭据（**只在内存里用，
不打印、不写文件**）→ 建 Release（tag 指向 main）→ 上传 `dist\BanScreenshot.exe`
→ 写入说明并附上 SHA256。同名资产会先删后传，所以脚本可以重复运行。

---

## 配置文件 `ban_shortcut.ini`

程序（或 exe）同目录下的 `ban_shortcut.ini` 会自动生效，用记事本改完保存即可。
首次运行自动生成一份带中文注释的模板，`--save-config [路径]` 可以随时再生成。

> **它只读一份 ini，顺序是：① exe / 脚本同目录 → ② 当前工作目录**，取第一个找到的。
> 所以「改了配置却不生效」几乎都是改错了文件：exe 放哪儿就读哪儿旁边那份。
> 程序启动时会打印实际使用的路径；如果另一处也存在 ini，会额外提示
> `！存在但未使用的 ini: …`，照着提示改对的那份即可。
> 另外这个文件是**运行时自动生成的**，不纳入版本管理，删掉也会自己再长出来。

| 节 | 项 | 说明 |
| --- | --- | --- |
| `[general]` | `mode` | `whitelist`（默认，除白名单外所有 Ctrl/Alt/Win 组合全屏蔽）或 `blacklist` |
| | `block_win_key` | 是否整键屏蔽左右 Win 键（`true` / `false`） |
| | `block_prtsc` | 是否整键屏蔽 PrintScreen |
| | `extra_blocked_keys` | 额外整键屏蔽的键，如 `f12 f10`；留空 = 不屏蔽 |
| | `verbose` | 是否在控制台打印每一次拦截 |
| | `auto_elevate` | 启动时是否自动弹 UAC 提权 |
| `[hotkeys]` | `toggle` / `exit` | 暂停恢复热键 / 退出热键（如 `ctrl+alt+f12`） |
| `[allow]` | `combos` | 白名单组合（每项一行，缩进写） |
| `[block]` | `combos` | 黑名单组合（任何模式下都屏蔽） |

写法很自由：大小写随意，`printscreen`、`lwin`、`control`、`escape`、`del`、`pgup`
之类别名都能认；`#` `;` 之后是注释；也可以在一行里用逗号分隔：`combos = ctrl+c, ctrl+v`。

**左右修饰键一律等价**：`lctrl` / `rctrl` → `ctrl`，`lshift` / `rshift` → `shift`，
`lalt` / `ralt` → `alt`，`lwin` / `rwin` → `win`。所以写哪个都行，判定结果完全一样。

> ⚠️ `combos =` 下面的每一行**都要缩进**（有个空格就行），否则会报解析错误。

名单语义小抄：

- `combos =` 后面**留空** = 明确表示「一个都不放行」/「不额外屏蔽」
  （`[allow]` 留空 → 连 `Ctrl+C` 也拦；`[block]` 留空 → 只剩 Win 组合和 PrintScreen 两条整键规则）
- 把整个 `[allow]` / `[block]` **节删掉** = 沿用程序内置的默认名单
- `[allow]` 只在 `mode = whitelist` 下参与判定；`blacklist` 模式下它不起作用

写错项名也不会崩：不认识的键名会在启动时提示「不认识的键名」。

## 命令行参数

参数优先级 **高于** 配置文件，适合做不同游戏的启动快捷方式：

| 参数 | 作用 |
| --- | --- |
| `--mode whitelist\|blacklist` | 切换工作模式 |
| `--allow "ctrl+w ctrl+t"` | 追加放行的组合键 |
| `--block "ctrl+alt+p"` | 追加屏蔽的组合键 |
| `--extra-keys "f12 f10"` | 追加整键屏蔽 |
| `--no-win` / `--no-prtsc` | 不屏蔽 Win 键 / PrintScreen |
| `--config 路径` | 指定配置文件 |
| `--save-config [路径] [--force]` | 生成默认配置文件 |
| `--no-elevate` | 不自动请求管理员权限 |
| `--observe` | 只记录不屏蔽（侦察模式） |
| `--quiet` | 不打印每次拦截记录 |
| `--list` | 打印当前生效配置后退出 |
| `--self-test` | 不装钩子，自检判定逻辑（固定用内置默认值） |

例：给音游做两个快捷方式，一个严格一个宽松：

```bat
BanScreenshot.exe --mode whitelist --extra-keys "f12 f10"
BanScreenshot.exe --mode blacklist --no-win
```

**推荐第一次这样用**：`BanScreenshot.exe --observe` 玩一两首曲子，
看看自己到底按出了哪些组合键，再按需调整 ini 里的名单。

---

## 默认屏蔽了什么

判定规则只有三条，非常好记：

1. **左/右 Win 键整键屏蔽** → 所有 `Win+X` 组合自然全部失效（截图那几种就在里面）
2. **PrintScreen 整键屏蔽** → `PrtScn`、`Alt+PrtScn`、`Ctrl+PrtScn` 一起失效
3. **白名单模式**：凡是带 `Ctrl` / `Alt` / `Win` 的组合一律屏蔽，
   只有下表中“放行”的那些除外；不含这些修饰键的按键**全部正常**

| 快捷键 | 作用 | 本程序默认处理 |
| --- | --- | --- |
| `Win`（左/右，单独按） | 打开开始菜单 | 🚫 屏蔽 |
| `Win+Shift+S` | 截图工具：区域截图 | 🚫 屏蔽（Win 规则） |
| `Win+PrtScn` | 全屏截图并保存到 `图片\屏幕截图` | 🚫 屏蔽 |
| `Win+Alt+PrtScn` | Xbox Game Bar 截图 | 🚫 屏蔽 |
| `Win+G` | 打开 Game Bar（内含录制/截图） | 🚫 屏蔽 |
| `Win+Alt+R` / `Win+Alt+G` | Game Bar 录屏 / 录制最近 30 秒 | 🚫 屏蔽 |
| `PrtScn` | 全屏截图到剪贴板（Win11 可设为打开截图工具） | 🚫 屏蔽 |
| `Alt+PrtScn` | 当前窗口截图到剪贴板 | 🚫 屏蔽 |
| `Alt+Tab` / `Alt+Shift+Tab` | 切换窗口 | 🚫 屏蔽 |
| `Alt+Esc` | 在窗口间循环 | 🚫 屏蔽 |
| `Alt+Space` | 窗口系统菜单 | 🚫 屏蔽 |
| `Alt+F4` | 关闭当前窗口（误触直接关游戏） | 🚫 屏蔽 |
| `Ctrl+Esc` | 开始菜单 | 🚫 屏蔽 |
| `Ctrl+Alt+A` | QQ 截图（默认热键） | 🚫 屏蔽 |
| `Alt+A` | 微信截图（默认热键） | 🚫 屏蔽 |
| `Ctrl+Shift+A` | 钉钉 / 搜狗输入法等截图热键 | 🚫 屏蔽 |
| `Ctrl+Shift+S`、`Ctrl+Alt+S` | 浏览器网页截图插件等 | 🚫 屏蔽 |
| `F12` | Steam 默认截图键 | 🚫 屏蔽（`EXTRA_BLOCKED_KEYS`） |
| `Win+D` / `Win+M` / `Win+Home` | 显示桌面 / 最小化所有窗口 | 🚫 屏蔽 |
| `Win+E` `Win+R` `Win+I` `Win+S` `Win+A` `Win+N` `Win+V` `Win+X` `Win+K` `Win+P` `Win+U` `Win+Z` `Win+.` | 资源管理器 / 运行 / 设置 / 搜索 / 快捷设置 / 通知 / 剪贴板历史 / 快速链接 / 投影 / 表情面板…… | 🚫 屏蔽 |
| `Win+Tab`、`Win+Ctrl+D`、`Win+Ctrl+←→` | 任务视图 / 虚拟桌面 | 🚫 屏蔽 |
| `Win+←` `Win+→` `Win+↑` `Win+↓`、`Win+Shift+←→` | 窗口贴靠 / 移到其它显示器 | 🚫 屏蔽 |
| `Win+数字`、`Win+T` | 打开 / 切换任务栏上的第 N 个程序 | 🚫 屏蔽 |
| `Win+L` | 锁定电脑 | 🚫 屏蔽 |
| `Win+空格` | 切换输入法 | 🚫 屏蔽 |
| `Ctrl+Space`、`Ctrl+Shift` | 输入法中英文 / 输入法切换 | 🚫 屏蔽（白名单模式） |
| `Ctrl+Alt+←→` | 屏幕旋转（部分显卡驱动） | 🚫 屏蔽（白名单模式） |
| `Ctrl+Alt+Del` | Windows 安全界面 | ⛔ **无法拦截**（系统保留），留着当应急出口 |

## 默认放行了什么（基本编辑快捷键）

| 快捷键 | 作用 | 处理 |
| --- | --- | --- |
| `Ctrl+C` / `Ctrl+V` / `Ctrl+X` | 复制 / 粘贴 / 剪切 | ✅ 放行 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做 | ✅ 放行 |
| `Ctrl+A` / `Ctrl+S` / `Ctrl+F` | 全选 / 保存 / 查找 | ✅ 放行 |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` / `Ctrl+Shift+Z` | 终端复制粘贴 / 重做 | ✅ 放行 |
| `Ctrl+Shift+Esc` | 任务管理器（应急出口） | ✅ 放行 |
| `Alt+Enter` | 游戏 / 播放器切换全屏 | ✅ 放行 |
| 所有不含 `Ctrl`/`Alt`/`Win` 的按键（字母、数字、方向键、`Shift+键`、`Space`、`Tab`、`F1–F11`……） | 游戏按键 | ✅ 放行 |
| 单独按一下 `Shift` / `Ctrl` / `Alt`（不带其它键） | 游戏里当按键用 | ✅ 放行 |

---

## 自定义

**首选：改 `ban_shortcut.ini`**（和 exe 放一起，记事本即可）。只改想要的两三行就行：

```ini
[allow]
combos =
    ctrl+c
    ctrl+v
    ctrl+w          ; ← 想额外放行什么，就在这里加一行

[block]
combos =
    alt+tab
    ctrl+alt+p      ; ← 想额外屏蔽什么，就在这里加一行
```

临时试一下不想改文件？用命令行参数：`BanScreenshot.exe --allow "ctrl+w" --block "ctrl+alt+p"`。

**备选：直接改 `ban_shortcut.py` 顶部**的内置默认值（没有 ini 文件时就用它；
`--self-test` 也固定用这套默认值做测试）：

```python
MODE = "whitelist"           # 或 "blacklist"

ALLOW_COMBOS = """
    ctrl+c
    ctrl+v
"""

BLOCK_COMBOS = """
    alt+tab
    ctrl+alt+p
"""

BLOCK_WIN_KEY = True         # 是否整键屏蔽左右 Win
BLOCK_PRTSCN  = True         # 是否整键屏蔽 PrintScreen
EXTRA_BLOCKED_KEYS = "f12"   # 额外整键屏蔽的键，例如 "f12 f10"；填 "" 表示不屏蔽
```

写法很自由：大小写随便，`printscreen`、`lwin`、`control`、`escape`、`del`、`pgup` 之类别名都能认；
`#` 后面是注释；左右键不用区分（`lwin`/`rwin` 统一写 `win`）。

**两种模式怎么选：**

- `whitelist`（默认）—— 按你的要求：除白名单外，所有 `Ctrl/Alt/Win` 组合全灭，最省心。
- `blacklist` —— 只灭黑名单。**如果游戏自己用 `Ctrl+某键` 作为键位**（比如某些铺面把 `Ctrl`、`Alt` 当轨道），
  就切到这个模式，否则那个轨道键会因为“Ctrl+键”被吞掉而失效。

---

## 常见问题

**Q：为什么建议用管理员权限运行？**
钩子只能在“同一权限级别”内看到按键。如果游戏是管理员身份启动的（很多游戏加上反作弊
驱动后就是），非管理员的钩子看不到发给它的按键，屏蔽就会失效。
本程序默认会自动弹 UAC 提权（想关掉就用 `--no-elevate` 或把 ini 里 `auto_elevate` 改成 `false`）。

**Q：我的键盘区分左右 Ctrl / Alt / Shift（日志里像 `CTRL+LCTRL`），会影响判定吗？**
不会（v1.0.1 起）。程序把修饰键统一归一成 `ctrl` / `shift` / `alt` / `win`：
按住左 Ctrl 再按右 Ctrl、或者两只手各按一个 Ctrl，都只会被理解为「按住 Ctrl」，
不会冒出 `CTRL+LCTRL` 这种假组合；而且**单独的 Ctrl / Alt / Shift 按下永远放行**
（游戏要把它们当键位用，Ctrl 的按下如果被吞掉，`Ctrl+C` 在别的程序里也会失效）。
日志只会在真的命中屏蔽规则时打印，并且按住的自动重复不会刷屏。

**Q：我改了 `ban_shortcut.ini` 却没生效？**
先看控制台第一行打印的 `配置文件 : …` 路径 —— 程序**只读那一个**。
最常见的情况是：exe 在 `dist\` 里，而你改的是别处（比如项目根目录）那份 ini。
两处都有时启动会提示 `！存在但未使用的 ini: …`，把多余的删掉，或改提示里被使用的那份。
（另外注意：`[allow]` 白名单只在 `mode = whitelist` 下起作用。）

**Q：exe 和 ini 的关系？换台电脑怎么带？**
exe 自带默认配置，**单独一个 exe 就能用**；`ban_shortcut.ini` 只在你想要自定义时才需要。
拷给别人时把 exe + ini 一起复制过去即可，对方无需安装 Python。

**Q：`--save-config` 生成的 ini 在哪儿？**
默认在 exe（或 `ban_shortcut.py`）同目录；也可以 `--save-config "D:\我的配置\游戏A.ini"`
指定位置，再用 `--config` 指向它。

**Q：为什么 `Fn+PrtScn`、键盘上的“一键截图”键拦不住？**
`Fn` 组合通常是键盘固件层面处理的，根本不产生 Windows 按键事件，软件层面无法拦截。
请在 BIOS / 键盘驱动软件里关掉它。

**Q：某个带内核级反作弊的游戏，钩子好像不生效？**
少数反作弊会阻止用户态钩子。这时请用下面的“注册表方案”（改完重启生效，属于系统级设置，
不需要常驻程序）。

**Q：会不会影响游戏手感 / 增加输入延迟？**
不会。钩子回调只是几次集合查表，且**不在回调里做任何磁盘或控制台 I/O**（日志走独立线程打印）。

**Q：程序崩了/被杀了怎么办？**
钩子随进程消失，快捷键立即恢复正常；任何时候 `Ctrl+Alt+Del` 都能用。

---

## 注册表方案（Plan B，不常驻程序）

如果不想用钩子，也可以用系统自带的设置达到类似效果（改完需重启或重启资源管理器）：

```bat
:: 1) 屏蔽大部分 Win+键 系统快捷键（用户级，立即生效前需重登一次）
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" /v NoWinKeys /t REG_DWORD /d 1 /f

:: 2) 关闭 Xbox Game Bar（Win+G / Win+Alt+PrtScn 录屏截图）
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR" /v AppCaptureEnabled /t REG_DWORD /d 0 /f
reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f

:: 3) 关掉“按 PrtScn 打开截图工具”（Win11）
reg add "HKCU\Control Panel\Keyboard" /v PrintScreenKeyForSnippingEnabled /t REG_DWORD /d 0 /f
```

恢复：把上面每条的值改成 `0` / `1` 的相反值，或删除对应键值。
**注意：注册表方案对 `Ctrl+Shift+A`、`Alt+A` 这类第三方软件热键无效**，那些还是得靠本程序
或去对应软件里改热键。

---

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `dist\BanScreenshot.exe` | **打包好的成品**（单文件，双击即用，自动提权） |
| `build_exe.bat` | 打包脚本：一键生成上面的 exe（需要 Python + 联网装 PyInstaller） |
| `release.ps1` / `make_release.bat` | 维护者工具：把 exe 发布到 GitHub Releases（自动读取已缓存的凭据） |
| `ban_shortcut.py` | 主程序源码：低层键盘钩子 + 屏蔽规则 + 配置文件/参数处理 |
| `ban_shortcut.ini` | 配置文件（首次运行自动生成，**不纳入版本管理**；exe 只读它旁边那份） |
| `BanScreenshot.spec` | PyInstaller 打包配置（自动生成，一般不用管） |
| `run_as_admin.bat` | 用 Python 直接跑时的启动器（自动请求管理员权限） |
| `README.md` | 本说明 |
| `LICENSE` | MIT 开源许可证 |

---

## 许可证

[MIT](LICENSE) © 2026 Ravenft369

工具本身只用 Windows 公开 API，不联网、不收集任何数据。
