<#
  release.ps1 —— 把 dist\BanScreenshot.exe 发布到 GitHub Releases

  用法（在仓库根目录，或双击 make_release.bat）：
      powershell -ExecutionPolicy Bypass -File .\release.ps1
      powershell -ExecutionPolicy Bypass -File .\release.ps1 -Tag v1.1 -CleanOld

  凭据：自动从 Git 凭据管理器（就是你 git push 时缓存的那份）读取，
        只在内存中使用，不会打印、不会写入任何文件。

  参数：
      -Tag        发布的 tag（默认 v1.0.1；不存在时会在 main 上自动创建）
      -ExePath    要上传的 exe（默认 dist\BanScreenshot.exe）
      -Name       Release 标题（默认 "BanScreenshot <tag>"）
      -NotesFile  说明正文文件（UTF-8；不传则用内置的默认说明）
      -CleanOld   顺便清掉 v1.0 里旧的 zip 资产
      -DeleteRelease <tag>   只删除某个 Release（git tag 保留）后退出
      -DryRun     只做本地检查，不读凭据、不上传
#>
[CmdletBinding()]
param(
    [string]$Tag = "v1.0.1",
    [string]$ExePath,
    [string]$Name,
    [string]$NotesFile,
    [switch]$CleanOld,
    [string]$DeleteRelease,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-GitHubToken {
    # 让 git 自己去问凭据管理器要 github.com 的凭据
    # 注意：必须用 cmd 重定向喂 stdin；用 .NET 的管道写法 GCM 会回“missing protocol field”
    $tmp = [IO.Path]::GetTempFileName()
    try {
        # 请求里没有敏感信息，临时文件里也不会出现凭据
        [IO.File]::WriteAllText($tmp, "protocol=https`nhost=github.com`n`n")
        $out = cmd /c "git credential fill < `"$tmp`" 2>nul"
        foreach ($line in ($out -split "`r?`n")) {
            if ($line -like "password=*") {
                return $line.Substring(9).Trim()
            }
        }
        return ""
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
if (-not $ExePath) { $ExePath = Join-Path $root "dist\BanScreenshot.exe" }
if (-not $Name) { $Name = "BanScreenshot $Tag" }

Write-Host "== BanScreenshot 发布助手 ==" -ForegroundColor Cyan

# ---------- 1) 本地检查 ----------
if ($DeleteRelease) {
    Write-Host ("模式   : 只删除 Release {0}（git tag 保留）" -f $DeleteRelease)
}
if (-not $DeleteRelease) {
    if (-not (Test-Path -LiteralPath $ExePath)) {
        Write-Host "[错误] 找不到 $ExePath" -ForegroundColor Red
        Write-Host "       请先双击 build_exe.bat 打包。" -ForegroundColor Red
        exit 1
    }
    $exe = Get-Item -LiteralPath $ExePath
    $sha = (Get-FileHash -LiteralPath $exe.FullName -Algorithm SHA256).Hash
    Write-Host ("exe    : {0}" -f $exe.FullName)
    Write-Host ("大小   : {0} MB" -f [math]::Round($exe.Length / 1MB, 2))
    Write-Host ("SHA256 : {0}" -f $sha)
}

$remote = (git -C $root remote get-url origin).Trim()
if ($remote -notmatch 'github\.com[:/](?<owner>[^/]+)/(?<repo>[^/]+?)(\.git)?$') {
    Write-Host "[错误] 无法从 origin 解析 GitHub 仓库：$remote" -ForegroundColor Red
    exit 1
}
$owner = $Matches['owner']
$repo = $Matches['repo']
$api = "https://api.github.com/repos/$owner/$repo"
Write-Host ("仓库   : {0}/{1}" -f $owner, $repo)
Write-Host ("tag    : {0}" -f $Tag)

# ---------- 2) 说明正文 ----------
if (-not $DeleteRelease) {
    if ($NotesFile) {
        $notes = Get-Content -LiteralPath $NotesFile -Raw -Encoding UTF8
        Write-Host ("说明   : 来自 {0}" -f $NotesFile)
    } else {
    $notes = @"
## BanScreenshot $Tag

玩游戏（尤其是音游）时不再误触截图等系统快捷键。

### 使用
1. 下载 **BanScreenshot.exe（只需这一个文件）**，双击运行，UAC 弹窗点「是」
2. 首次运行会在 exe 同目录自动生成 `ban_shortcut.ini`，想自定义就改它
3. `Ctrl+Alt+F12` 暂停 / 恢复屏蔽，`Ctrl+Alt+Shift+F12` 退出

### 更新内容
- 修复：左右 Ctrl / Alt / Shift 会被当成 `CTRL+LCTRL` 这类假组合，导致白名单里的
  Ctrl+C/V/X/Z 实际失效、控制台被刷屏
- 现在所有修饰键统一归一（按哪一侧、按几个都等同于「按住 Ctrl」），
  单独的 Ctrl / Alt / Shift 按下永远放行
- 新增：启动信息显示版本号；ini 里写 `lctrl` / `rshift` 等也能识别

### 说明
- 需要 64 位 Windows；若 SmartScreen 提示「Windows 已保护你的电脑」，点「更多信息 → 仍要运行」
- 若游戏带内核级反作弊导致钩子无效，请参考 README 的注册表方案
- Ctrl+Alt+Del 无法被拦截（系统保留），可作应急出口
"@
        Write-Host "说明   : 使用内置默认文案"
    }
    $notes = $notes.TrimEnd() + "`n`nSHA256（BanScreenshot.exe）：$sha`n"
}

if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] 本地检查通过，未读取凭据、未上传。" -ForegroundColor Yellow
    exit 0
}

function Invoke-GitHub {
    param([string]$Uri, [string]$Method = "Get", $Body, [string]$ContentType)
    $req = @{ Uri = $Uri; Method = $Method; Headers = $script:headers }
    if ($Body) { $req.Body = $Body; $req.ContentType = $ContentType }
    Invoke-RestMethod @req
}

# ---------- 3) 取凭据 ----------
$token = Get-GitHubToken
if (-not $token) {
    Write-Host "[错误] 没能从 Git 凭据管理器取到 GitHub 凭据。" -ForegroundColor Red
    Write-Host "       先随便 git push 一次（会弹浏览器登录），再跑本脚本。" -ForegroundColor Red
    Write-Host "       或改用网页上传：仓库页 → Releases → Create a new release" -ForegroundColor Red
    exit 1
}
Write-Host ("凭据   : 已读取（长度 {0}，仅内存使用）" -f $token.Length)
$script:headers = @{
    Authorization          = "Bearer $token"
    Accept                 = "application/vnd.github+json"
    "User-Agent"           = "BanScreenshot-release-script"
    "X-GitHub-Api-Version" = "2022-11-28"
}

try {
    $me = Invoke-GitHub -Uri "https://api.github.com/user"
    Write-Host ("账号   : {0}" -f $me.login)

    # ---------- 3.5) 只删除某个 Release（git tag 保留）----------
    if ($DeleteRelease) {
        Write-Host ("删除 Release {0} …" -f $DeleteRelease)
        $victim = Invoke-GitHub -Uri "$api/releases/tags/$DeleteRelease"
        Invoke-GitHub -Uri "$api/releases/$($victim.id)" -Method Delete
        Write-Host ("已删除 Release {0}（git tag 仍保留，需要的话手动删 tag 即可）。" -f $DeleteRelease) -ForegroundColor Green
        exit 0
    }

    # ---------- 4) 找 Release，没有就建 ----------
    $rel = $null
    try { $rel = Invoke-GitHub -Uri "$api/releases/tags/$Tag" } catch { $rel = $null }

    $payload = @{ name = $Name; body = $notes } | ConvertTo-Json -Depth 4
    if (-not $rel) {
        Write-Host ("创建 Release {0}（tag 指向 main）…" -f $Tag)
        $payload = @{
            tag_name         = $Tag
            name             = $Name
            body             = $notes
            draft            = $false
            prerelease       = $false
            target_commitish = "main"
        } | ConvertTo-Json -Depth 4
        $rel = Invoke-GitHub -Uri "$api/releases" -Method Post `
                             -Body ([Text.Encoding]::UTF8.GetBytes($payload)) `
                             -ContentType "application/json; charset=utf-8"
    } else {
        Write-Host "已存在同名 Release，更新标题与说明 …"
        $rel = Invoke-GitHub -Uri "$api/releases/$($rel.id)" -Method Patch `
                             -Body ([Text.Encoding]::UTF8.GetBytes($payload)) `
                             -ContentType "application/json; charset=utf-8"
    }

    # ---------- 5) 传资产（同名先删，保证可重复运行）----------
    $assetName = "BanScreenshot.exe"
    foreach ($a in @($rel.assets)) {
        if ($a.name -eq $assetName) {
            Write-Host ("删除旧资产 {0} …" -f $a.name)
            Invoke-GitHub -Uri "$api/releases/assets/$($a.id)" -Method Delete
        }
    }
    Write-Host ("上传 {0} …" -f $assetName)
    $upload = "https://uploads.github.com/repos/$owner/$repo/releases/$($rel.id)/assets?name=$assetName"
    # 上传要带文件体，这里直接用 Invoke-RestMethod + -InFile
    $asset = Invoke-RestMethod -Uri $upload -Method Post -Headers $script:headers `
                               -ContentType "application/octet-stream" -InFile $exe.FullName
    Write-Host ("上传完成：{0}" -f $asset.browser_download_url) -ForegroundColor Green

    # ---------- 6) 顺手清理旧 Release 的 zip ----------
    if ($CleanOld) {
        try {
            $old = Invoke-GitHub -Uri "$api/releases/tags/v1.0"
            foreach ($a in @($old.assets)) {
                Write-Host ("清理旧资产 {0}（{1}）…" -f $a.name, $old.tag_name)
                Invoke-GitHub -Uri "$api/releases/assets/$($a.id)" -Method Delete
            }
        } catch {
            Write-Host ("跳过旧 Release 清理：{0}" -f $_.Exception.Message) -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host ("完成：{0}" -f $rel.html_url) -ForegroundColor Green
    Write-Host ("下载页：https://github.com/{0}/{1}/releases/latest" -f $owner, $repo) -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "[错误] 调用 GitHub API 失败：" -ForegroundColor Red
    Write-Host ("       {0}" -f $_.Exception.Message) -ForegroundColor Red
    $resp = $_.Exception.Response
    if ($resp) {
        Write-Host ("       HTTP {0}" -f [int]$resp.StatusCode) -ForegroundColor Red
        if ([int]$resp.StatusCode -eq 404 -or [int]$resp.StatusCode -eq 403) {
            Write-Host "       凭据可能缺少 repo 权限（或不是该仓库的协作者）。" -ForegroundColor Yellow
            Write-Host "       改用网页上传：仓库页 → Releases → Create a new release" -ForegroundColor Yellow
        }
    }
    exit 1
}
