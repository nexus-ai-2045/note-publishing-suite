[CmdletBinding()]
param(
    [string]$PackageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$WorkspaceRoot,
    [string]$DestinationRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Windows PowerShell 5.1 needs BOM for Japanese source and UTF-8 console output.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-NoReparsePointInPath([string]$Path) {
    $current = Get-FullPath $Path
    $root = [System.IO.Path]::GetPathRoot($current)
    while ($current -and $current -ne $root) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "path component must not be a symlink or junction: $current"
            }
        }
        $parent = [System.IO.Directory]::GetParent($current)
        $current = if ($parent) { $parent.FullName } else { $null }
    }
}

$PackageRoot = Get-FullPath $PackageRoot
Assert-NoReparsePointInPath $PackageRoot
if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot "SKILL.md") -PathType Leaf)) {
    throw "package root does not contain SKILL.md: $PackageRoot"
}

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    throw "one explicit external workspace directory is required"
}
$WorkspaceRoot = Get-FullPath $WorkspaceRoot
if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) {
    throw "workspace must be an existing directory"
}
Assert-NoReparsePointInPath $WorkspaceRoot
$packagePrefix = $PackageRoot.TrimEnd([char[]]"\/") + [System.IO.Path]::DirectorySeparatorChar
if ($WorkspaceRoot.TrimEnd([char[]]"\/").Equals($PackageRoot.TrimEnd([char[]]"\/"), [StringComparison]::OrdinalIgnoreCase) -or
    $WorkspaceRoot.StartsWith($packagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "workspace must be outside the package"
}

if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    $DestinationRoot = Join-Path $codexHome "skills"
}
$DestinationRoot = Get-FullPath $DestinationRoot
Assert-NoReparsePointInPath $DestinationRoot

$templateRoot = Join-Path $PackageRoot "adapters\claude-code"
Assert-NoReparsePointInPath $templateRoot
$templates = @(Get-ChildItem -LiteralPath $templateRoot -Directory | Sort-Object Name)
if ($templates.Count -eq 0) {
    throw "no pointer templates found: $templateRoot"
}

$generatedPointers = @()
foreach ($templateDirectory in $templates) {
    $templatePath = Join-Path $templateDirectory.FullName "SKILL.md"
    Assert-NoReparsePointInPath $templatePath
    if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
        throw "missing pointer template: $templatePath"
    }
    $content = [System.IO.File]::ReadAllText($templatePath)
    $content = $content.Replace("{{PACKAGE_ROOT}}", $PackageRoot)
    $content = $content.Replace("{{WORKSPACE_ROOT}}", $WorkspaceRoot)
    $content = $content.Replace("Claude Code Pointer", "Codex Pointer")
    $content = [regex]::Replace(
        $content,
        "(?ms)^## Codex[^\r\n]*読み替え\s*.*?(?=^## |\z)",
        ""
    )

    $expectedTarget = if ($templateDirectory.Name -eq "note-publishing-suite") {
        Join-Path $PackageRoot "SKILL.md"
    }
    else {
        Join-Path $PackageRoot ("skills\" + $templateDirectory.Name + "\SKILL.md")
    }
    if (-not (Test-Path -LiteralPath $expectedTarget -PathType Leaf)) {
        throw "missing package SSOT target: $expectedTarget"
    }
    $expectedPointerTarget = if ($templateDirectory.Name -eq "note-publishing-suite") {
        "$PackageRoot/SKILL.md"
    }
    else {
        "$PackageRoot/skills/$($templateDirectory.Name)/SKILL.md"
    }
    if ([regex]::Matches($content, [regex]::Escape($expectedPointerTarget)).Count -ne 1) {
        throw "generated pointer must contain exactly one expected SSOT target: $templatePath"
    }
    if ($content.Contains("{{PACKAGE_ROOT}}") -or $content.Contains("{{WORKSPACE_ROOT}}")) {
        throw "generated pointer contains an unresolved placeholder: $templatePath"
    }
    $generatedPointers += [pscustomobject]@{
        Name = $templateDirectory.Name
        Content = $content
    }
}

$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("note-publishing-suite-stage-" + [Guid]::NewGuid().ToString("N"))
try {
    [System.IO.Directory]::CreateDirectory($stageRoot) | Out-Null
    foreach ($generated in $generatedPointers) {
        $stageDirectory = Join-Path $stageRoot $generated.Name
        [System.IO.Directory]::CreateDirectory($stageDirectory) | Out-Null
        [System.IO.File]::WriteAllText(
            (Join-Path $stageDirectory "SKILL.md"),
            $generated.Content,
            [System.Text.UTF8Encoding]::new($false)
        )
    }

    $python = Get-Command python -ErrorAction Stop
    & $python.Source -X utf8 (Join-Path $PackageRoot "scripts\skill_pointer_check.py") `
        --installed-root $stageRoot `
        --json
    if ($LASTEXITCODE -ne 0) {
        throw "skill pointer validation failed with exit code $LASTEXITCODE"
    }

    $committed = @()
    $createdDirectories = @()
    try {
        [System.IO.Directory]::CreateDirectory($DestinationRoot) | Out-Null
        foreach ($generated in $generatedPointers) {
            $destinationDirectory = Join-Path $DestinationRoot $generated.Name
            Assert-NoReparsePointInPath $destinationDirectory
            if (-not (Test-Path -LiteralPath $destinationDirectory)) {
                [System.IO.Directory]::CreateDirectory($destinationDirectory) | Out-Null
                $createdDirectories += $destinationDirectory
            }

            $pointerPath = Join-Path $destinationDirectory "SKILL.md"
            Assert-NoReparsePointInPath $pointerPath
            $temporaryPath = Join-Path $destinationDirectory (".SKILL.md." + [Guid]::NewGuid().ToString("N") + ".tmp")
            $backupPath = Join-Path $destinationDirectory (".SKILL.md." + [Guid]::NewGuid().ToString("N") + ".bak")
            try {
                [System.IO.File]::WriteAllText(
                    $temporaryPath,
                    $generated.Content,
                    [System.Text.UTF8Encoding]::new($false)
                )
                if (Test-Path -LiteralPath $pointerPath -PathType Leaf) {
                    [System.IO.File]::Replace($temporaryPath, $pointerPath, $backupPath)
                    $committed += [pscustomobject]@{ Pointer = $pointerPath; Backup = $backupPath; IsNew = $false }
                }
                else {
                    [System.IO.File]::Move($temporaryPath, $pointerPath)
                    $committed += [pscustomobject]@{ Pointer = $pointerPath; Backup = $null; IsNew = $true }
                }
            }
            finally {
                if (Test-Path -LiteralPath $temporaryPath) {
                    Remove-Item -LiteralPath $temporaryPath -Force
                }
            }
            Write-Output "installed: $pointerPath"
        }
    }
    catch {
        if ($committed.Count -gt 0) {
            for ($index = $committed.Count - 1; $index -ge 0; $index--) {
                $entry = $committed[$index]
                if (Test-Path -LiteralPath $entry.Pointer) {
                    Remove-Item -LiteralPath $entry.Pointer -Force
                }
                if (-not $entry.IsNew -and (Test-Path -LiteralPath $entry.Backup)) {
                    [System.IO.File]::Move($entry.Backup, $entry.Pointer)
                }
            }
        }
        if ($createdDirectories.Count -gt 0) {
            for ($index = $createdDirectories.Count - 1; $index -ge 0; $index--) {
                $directory = $createdDirectories[$index]
                if ((Test-Path -LiteralPath $directory) -and -not (Get-ChildItem -LiteralPath $directory -Force)) {
                    Remove-Item -LiteralPath $directory -Force
                }
            }
        }
        throw
    }

    foreach ($entry in $committed) {
        if ($entry.Backup -and (Test-Path -LiteralPath $entry.Backup)) {
            Remove-Item -LiteralPath $entry.Backup -Force
        }
    }
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}

Write-Output "OK: note skills are available to the next Codex session"
Write-Output "初回設定は別途確認します。保存先・読んでよい素材・本人の文体参照について、次のセッションで「NPSの初回設定から案内して」と依頼してください。既存settingsは再初期化しません。手順: references/note-workflow-review-contract.md の初回設定の案内。"
