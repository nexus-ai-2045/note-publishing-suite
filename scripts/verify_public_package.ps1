param(
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$scriptPath = $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptPath)
$skipStandaloneVerifierLane = $env:NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH -eq "1"
$errors = New-Object System.Collections.Generic.List[string]
$checked = New-Object System.Collections.Generic.List[string]

function Add-Error {
    param([string]$Message)
    [void]$errors.Add($Message)
}

function Add-Checked {
    param([string]$Message)
    [void]$checked.Add($Message)
}

function Read-Text {
    param([string]$RelativePath)
    return [System.IO.File]::ReadAllText((Join-Path $root $RelativePath), [System.Text.Encoding]::UTF8)
}

function Get-RepoRelativePath {
    param([string]$FullPath)
    $rootFull = [System.IO.Path]::GetFullPath($root).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $fileFull = [System.IO.Path]::GetFullPath($FullPath)
    if ($fileFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fileFull.Substring($rootFull.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar).Replace("\", "/")
    }
    return $fileFull.Replace("\", "/")
}

function Test-RequiredFile {
    param([string]$RelativePath)
    $path = Join-Path $root $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Error "missing file: $RelativePath"
        return
    }
    Add-Checked "file exists: $RelativePath"
}

function Test-RequiredDirectory {
    param([string]$RelativePath)
    $path = Join-Path $root $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        Add-Error "missing directory: $RelativePath"
        return
    }
    Add-Checked "directory exists: $RelativePath"
}

function Test-Contains {
    param(
        [string]$RelativePath,
        [string]$Needle
    )
    $text = Read-Text $RelativePath
    if ($text.IndexOf($Needle, [System.StringComparison]::Ordinal) -lt 0) {
        Add-Error "$RelativePath missing text: $Needle"
        return
    }
    Add-Checked "$RelativePath contains: $Needle"
}

function Invoke-Git {
    param(
        [string]$WorkingDirectory,
        [string[]]$Arguments
    )
    $output = & git -C $WorkingDirectory @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed: exit=$exitCode output=$($output -join ' ')"
    }
    return $output
}

function Copy-PublicPackageCloneFixture {
    param([string]$DestinationRoot)

    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $root -Force) {
        if ($item.Name -in @(".git", ".pytest_cache", "__pycache__")) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination $DestinationRoot -Recurse -Force
    }

    Get-ChildItem -LiteralPath $DestinationRoot -Recurse -Force -Directory |
        Where-Object { $_.Name -in @(".git", ".pytest_cache", "__pycache__") } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    foreach ($localOnly in @(
        "data/github_identity_guard_policy.local.json",
        "data/provenance_leak_policy.local.json"
    )) {
        Remove-Item -LiteralPath (Join-Path $DestinationRoot $localOnly) -Force -ErrorAction SilentlyContinue
    }
}

function Test-StandaloneCloneIdentityLane {
    $fixtureRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("note-publishing-suite-standalone-" + [System.Guid]::NewGuid().ToString("N"))
    try {
        Copy-PublicPackageCloneFixture $fixtureRoot
        Invoke-Git $fixtureRoot @("init") | Out-Null
        Invoke-Git $fixtureRoot @("checkout", "-B", "main") | Out-Null
        Invoke-Git $fixtureRoot @("config", "--local", "user.name", "nexus_ai") | Out-Null
        Invoke-Git $fixtureRoot @("config", "--local", "user.email", "nexus.ai.2045@gmail.com") | Out-Null
        Invoke-Git $fixtureRoot @("remote", "add", "origin", "https://github.com/nexus-ai-2045/note-publishing-suite.git") | Out-Null
        Invoke-Git $fixtureRoot @("add", "-A") | Out-Null
        Invoke-Git $fixtureRoot @("commit", "-m", "standalone clone verification fixture") | Out-Null

        Push-Location $fixtureRoot
        $previousRepositoryEnv = $env:GITHUB_REPOSITORY
        try {
            $env:GITHUB_REPOSITORY = "nexus-ai-2045/note-publishing-suite"
            $identityOutput = & python "scripts/github_identity_guard.py" "--json" 2>&1
        } finally {
            if ($null -eq $previousRepositoryEnv) {
                Remove-Item Env:\GITHUB_REPOSITORY -ErrorAction SilentlyContinue
            } else {
                $env:GITHUB_REPOSITORY = $previousRepositoryEnv
            }
            Pop-Location
        }

        $identityExitCode = $LASTEXITCODE
        if ($identityExitCode -ne 0) {
            Add-Error "standalone clone GitHub identity guard failed: exit=$identityExitCode output=$($identityOutput -join ' ')"
            return
        }

        try {
            $identityResult = ($identityOutput -join "`n") | ConvertFrom-Json
        } catch {
            Add-Error "failed to parse standalone clone GitHub identity guard output: $($_.Exception.Message)"
            return
        }

        if ($identityResult.ok -ne $true) {
            Add-Error "standalone clone GitHub identity guard did not return ok=true"
        } elseif ($identityResult.mode -ne "standalone_repository") {
            Add-Error "standalone clone GitHub identity guard mode must be standalone_repository, got $($identityResult.mode)"
        } elseif ($identityResult.external_actions_performed.Count -ne 0 -or $identityResult.publication_actions_performed.Count -ne 0) {
            Add-Error "standalone clone GitHub identity guard must not perform external or publication actions"
        } else {
            Add-Checked "standalone clone GitHub identity guard passed"
        }
    } catch {
        Add-Error "standalone clone verification lane failed: $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-StandaloneCloneVerifierLane {
    $fixtureRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("note-publishing-suite-verifier-" + [System.Guid]::NewGuid().ToString("N"))
    try {
        Copy-PublicPackageCloneFixture $fixtureRoot
        Invoke-Git $fixtureRoot @("init") | Out-Null
        Invoke-Git $fixtureRoot @("checkout", "-B", "main") | Out-Null
        Invoke-Git $fixtureRoot @("config", "--local", "user.name", "nexus_ai") | Out-Null
        Invoke-Git $fixtureRoot @("config", "--local", "user.email", "nexus.ai.2045@gmail.com") | Out-Null
        Invoke-Git $fixtureRoot @("remote", "add", "origin", "https://github.com/nexus-ai-2045/note-publishing-suite.git") | Out-Null
        Invoke-Git $fixtureRoot @("add", "-A") | Out-Null
        Invoke-Git $fixtureRoot @("commit", "-m", "standalone verifier fixture") | Out-Null

        Push-Location $fixtureRoot
        $previousDepth = $env:NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH
        try {
            $env:NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH = "1"
            $verifierOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File "scripts/verify_public_package.ps1" "-Json" 2>&1
        } finally {
            if ($null -eq $previousDepth) {
                Remove-Item Env:\NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH -ErrorAction SilentlyContinue
            } else {
                $env:NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH = $previousDepth
            }
            Pop-Location
        }

        $verifierExitCode = $LASTEXITCODE
        if ($verifierExitCode -ne 0) {
            Add-Error "standalone clone public package verifier failed: exit=$verifierExitCode output=$($verifierOutput -join ' ')"
            return
        }

        try {
            $verifierResult = ($verifierOutput -join "`n") | ConvertFrom-Json
        } catch {
            Add-Error "failed to parse standalone clone public package verifier output: $($_.Exception.Message)"
            return
        }

        if ($verifierResult.ok -ne $true) {
            Add-Error "standalone clone public package verifier did not return ok=true"
        } elseif ($verifierResult.verification_lanes -notcontains "standalone_clone" -or $verifierResult.verification_lanes -notcontains "embedded_copy") {
            Add-Error "standalone clone public package verifier did not report both verification lanes"
        } elseif ($verifierResult.external_actions_performed.Count -ne 0 -or $verifierResult.publication_actions_performed.Count -ne 0) {
            Add-Error "standalone clone public package verifier must not perform external or publication actions"
        } else {
            Add-Checked "standalone clone public package verifier passed"
        }
    } catch {
        Add-Error "standalone clone public package verifier lane failed: $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-EmbeddedCopyIdentityLane {
    $fixtureParent = Join-Path ([System.IO.Path]::GetTempPath()) ("nexus-ai-embedded-fixture-" + [System.Guid]::NewGuid().ToString("N"))
    $fixtureRoot = Join-Path $fixtureParent "public/note-publishing-suite"
    try {
        Copy-PublicPackageCloneFixture $fixtureRoot
        Invoke-Git $fixtureParent @("init") | Out-Null

        Push-Location $fixtureRoot
        try {
            $identityOutput = & python "scripts/github_identity_guard.py" "--json" 2>&1
        } finally {
            Pop-Location
        }

        $identityExitCode = $LASTEXITCODE
        if ($identityExitCode -ne 0) {
            Add-Error "embedded copy GitHub identity guard failed: exit=$identityExitCode output=$($identityOutput -join ' ')"
            return
        }

        try {
            $identityResult = ($identityOutput -join "`n") | ConvertFrom-Json
        } catch {
            Add-Error "failed to parse embedded copy GitHub identity guard output: $($_.Exception.Message)"
            return
        }

        if ($identityResult.ok -ne $true) {
            Add-Error "embedded copy GitHub identity guard did not return ok=true"
        } elseif ($identityResult.mode -ne "embedded_copy_text_scan_only") {
            Add-Error "embedded copy GitHub identity guard mode must be embedded_copy_text_scan_only, got $($identityResult.mode)"
        } elseif ($identityResult.external_actions_performed.Count -ne 0 -or $identityResult.publication_actions_performed.Count -ne 0) {
            Add-Error "embedded copy GitHub identity guard must not perform external or publication actions"
        } else {
            Add-Checked "embedded copy GitHub identity guard fixture passed"
        }
    } catch {
        Add-Error "embedded copy verification lane failed: $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $fixtureParent -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-LocalOnlyPolicyBoundary {
    foreach ($localOnly in @(
        "data/github_identity_guard_policy.local.json",
        "data/provenance_leak_policy.local.json"
    )) {
        $ignored = & git -C $root check-ignore $localOnly 2>&1
        if ($LASTEXITCODE -ne 0) {
            Add-Error "local-only policy is not ignored by git: $localOnly output=$($ignored -join ' ')"
        } else {
            Add-Checked "local-only policy is gitignored: $localOnly"
        }

        $tracked = & git -C $root ls-files --error-unmatch $localOnly 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Error "local-only policy must not be tracked by git: $localOnly"
        } else {
            Add-Checked "local-only policy is not tracked: $localOnly"
        }
    }
}

function Test-RequiredFilesTracked {
    foreach ($required in $requiredFiles) {
        $tracked = & git -C $root ls-files --error-unmatch $required 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Checked "required public file is tracked: $required"
        } else {
            Add-Error "required public file is not tracked by git: $required"
        }
    }
}

$requiredFiles = @(
    "SKILL.md",
    "package.yaml",
    "README.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "README.rendered.html",
    "PUBLIC_READY.md",
    "PUBLIC_RELEASE_CHECKLIST.md",
    "SECURITY.md",
    "LICENSE",
    "issue-drafts.md",
    "issue-packet.json",
    "references/note-editor-capability-inventory.md",
    "references/note-editor-pdca-orchestration.md",
    "references/note-image-upload-automation-boundary.md",
    "references/note-editor-live-constraint-boundaries.md",
    "references/note-article-provenance-design.md",
    "skills/note-idea-intake/SKILL.md",
    "skills/note-draft-production/SKILL.md",
    "skills/note-prepublish-qa/SKILL.md",
    "skills/note-editor-prepublish/SKILL.md",
    "skills/note-editor-ops/SKILL.md",
    "skills/note-official-guidance-intake/SKILL.md",
    "skills/note-editor-constraint-debug/SKILL.md",
    "skills/note-publication-gate/SKILL.md",
    "skills/note-postpublish-ledger/SKILL.md",
    "scripts/note_preview.py",
    "scripts/pre_publish_check.py",
    "scripts/note_fact_check.py",
    "scripts/note_diff_check.py",
    "scripts/post_publish.py",
    "scripts/engagement_tracker.py",
    "scripts/render_readme.py",
    "scripts/provenance_leak_check.py",
    "scripts/provenance_label_check.py",
    "scripts/github_identity_guard.py",
    "scripts/japanese_closeout_language_check.py",
    "scripts/note_image_upload_boundary_check.py",
    "scripts/note_editor_prepublish_verify.py",
    "scripts/run_local_draft_qa_proof.py",
    "scripts/verify_public_package.ps1",
    "tests/test_content_pdca_check.py",
    "tests/test_note_image_upload_boundary.py",
    "tests/test_note_editor_prepublish_verify.py",
    "content/drafts/caramel-provenance-label-fixture.md",
    "data/github_identity_guard_policy.example.json",
    "data/note_drafts.json",
    "data/published_notes.json",
    "data/note_image_upload_automation_policy.json"
)

$requiredDirectories = @(
    "content",
    "content/drafts",
    "data",
    "published",
    "references",
    "scripts",
    "skills",
    "tests"
)

foreach ($item in $requiredFiles) {
    Test-RequiredFile $item
}

Test-RequiredFilesTracked

foreach ($item in $requiredDirectories) {
    Test-RequiredDirectory $item
}

$package = Read-Text "package.yaml"
$packageVersion = $null
if ($package -match "(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$") {
    $packageVersion = $Matches[1]
} else {
    Add-Error "package.yaml missing semantic version"
}
foreach ($item in $requiredFiles) {
    if ($item -like "README.rendered.html" -or $item -like "PUBLIC_READY.md" -or $item -like "SECURITY.md" -or $item -like "LICENSE" -or $item -like "tests/*") {
        continue
    }
    if ($package.IndexOf($item, [System.StringComparison]::Ordinal) -ge 0) {
        Add-Checked "package.yaml references: $item"
    }
}

Test-Contains "package.yaml" "human_review_required: true"
Test-Contains "package.yaml" "explicit_current_conversation_approval_required: true"
Test-Contains "package.yaml" "repository_visibility_change"
Test-Contains "package.yaml" "roadmap: ROADMAP.md"
Test-Contains "package.yaml" "changelog: CHANGELOG.md"
Test-Contains "package.yaml" "version:"
Test-Contains "package.yaml" "output_language_gate:"
Test-Contains "package.yaml" "user_visible_language: japanese"
Test-Contains "package.yaml" "cli_status_translation_required: true"
Test-Contains "package.yaml" "roadmap_contract:"
Test-Contains "package.yaml" "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1"
Test-Contains "package.yaml" "standalone_clone:"
Test-Contains "package.yaml" "embedded_copy:"
Test-Contains "package.yaml" "requires:"
Test-Contains "package.yaml" "PowerShell"
Test-Contains "package.yaml" "Python"
Test-Contains "package.yaml" "git"
Test-Contains "README.md" "PowerShell、Python、git"
Test-Contains "README.md" "この verifier は Python と git も使って各 checker を実行する"

$forbiddenRuntimeClaims = @(
    "Python が無い",
    "Python を前提にせず",
    "Python を必須にせず"
)
foreach ($doc in @("README.md", "README.rendered.html", "PUBLIC_READY.md")) {
    $docText = Read-Text $doc
    foreach ($claim in $forbiddenRuntimeClaims) {
        if ($docText.IndexOf($claim, [System.StringComparison]::Ordinal) -ge 0) {
            Add-Error "$doc contains misleading verifier runtime claim: $claim"
        } else {
            Add-Checked "$doc does not contain misleading verifier runtime claim: $claim"
        }
    }
}

Test-Contains "SKILL.md" "publication_gate: human_review_required"
Test-Contains "SKILL.md" "external_action: none"
Test-Contains "SKILL.md" "日本語完了報告ゲート"
Test-Contains "SKILL.md" "下書き解除済み"
Test-Contains "SKILL.md" "未マージPR"
Test-Contains "SKILL.md" "マージ済み"
Test-Contains "SKILL.md" "マージ可能"
Test-Contains "skills/note-publication-gate/SKILL.md" "public action"
Test-Contains "skills/note-publication-gate/SKILL.md" "Unknown"
Test-Contains "README.md" "publication_gate: human_review_required"
Test-Contains "README.md" "構造バグ"
Test-Contains "README.md" "出力ゲート"
if ($packageVersion) {
    Test-Contains "README.md" "パッケージ版: ``$packageVersion``"
    Test-Contains "CHANGELOG.md" "## $packageVersion"
}
Test-Contains "CHANGELOG.md" "python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py"
Test-Contains "README.md" "ROADMAP.md"
Test-Contains "README.md" "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1"
Test-Contains "README.md" "standalone clone"
Test-Contains "README.md" "embedded copy"
Test-Contains "PUBLIC_READY.md" "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1"
Test-Contains "PUBLIC_READY.md" "ROADMAP 確認済み: はい"
Test-Contains "ROADMAP.md" "publication_gate: human_review_required"
Test-Contains "ROADMAP.md" "external_action: none"
Test-Contains "ROADMAP.md" "## オーケストレーション地図"
Test-Contains "ROADMAP.md" "## 判断ルール"
Test-Contains "PUBLIC_RELEASE_CHECKLIST.md" "tests/test_note_image_upload_boundary.py"
Test-Contains "PUBLIC_RELEASE_CHECKLIST.md" "python scripts/note_image_upload_boundary_check.py --json"
Test-Contains "README.md" "scripts/note_editor_prepublish_verify.py <observation.json> --json"
Test-Contains "package.yaml" "scripts/note_editor_prepublish_verify.py"
Test-Contains "README.md" "scripts/run_local_draft_qa_proof.py --json"
Test-Contains "package.yaml" "scripts/run_local_draft_qa_proof.py"
Test-Contains "ROADMAP.md" "local_draft_qa_stop_before_publish_evidence.json"
Test-Contains "PUBLIC_RELEASE_CHECKLIST.md" "リポジトリ公開範囲"
Test-Contains "PUBLIC_RELEASE_CHECKLIST.md" "## プッシュ前の人間判断"
Test-Contains "README.md" "scripts/provenance_leak_check.py --scope changed"
Test-Contains "README.md" "scripts/provenance_label_check.py <draft.md> --json"
Test-Contains "references/note-article-provenance-design.md" "source_pack_locked_with_user_speech_priority"
Test-Contains "content/drafts/caramel-provenance-label-fixture.md" "provenance-label: user-said"
Test-Contains "content/drafts/caramel-provenance-label-fixture.md" "provenance-label: external-fact"
Test-Contains "content/drafts/caramel-provenance-label-fixture.md" "provenance-label: assistant-organized"
Test-Contains "content/drafts/caramel-provenance-label-fixture.md" "provenance-label: hold"
Test-Contains "package.yaml" "scripts/github_identity_guard.py"
Test-Contains "package.yaml" "data/github_identity_guard_policy.example.json"
Test-Contains ".gitignore" "data/github_identity_guard_policy.local.json"
Test-Contains "README.md" "scripts/japanese_closeout_language_check.py --json"
Test-Contains ".gitignore" "data/provenance_leak_policy.local.json"

Test-LocalOnlyPolicyBoundary

$policyPath = Join-Path $root "data/note_image_upload_automation_policy.json"
try {
    $policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($policy.public_action_allowed -ne $false) {
        Add-Error "policy public_action_allowed must be false"
    } else {
        Add-Checked "policy public_action_allowed=false"
    }
    if ($policy.internal_browser_image_upload_fully_automated -ne $false) {
        Add-Error "policy internal_browser_image_upload_fully_automated must be false"
    } else {
        Add-Checked "policy internal_browser_image_upload_fully_automated=false"
    }
    foreach ($action in @("cookie_read", "session_read", "publish", "schedule_publish", "external_share")) {
        if ($policy.prohibited_actions -notcontains $action) {
            Add-Error "policy prohibited_actions missing: $action"
        } else {
            Add-Checked "policy prohibits: $action"
        }
    }
} catch {
    Add-Error "failed to parse data/note_image_upload_automation_policy.json: $($_.Exception.Message)"
}

Push-Location $root
try {
    $provenanceOutput = & python "scripts/provenance_leak_check.py" "--scope" "all" "--json" 2>&1
} finally {
    Pop-Location
}
$provenanceExitCode = $LASTEXITCODE
if ($provenanceExitCode -ne 0) {
    Add-Error "provenance leak check failed: exit=$provenanceExitCode output=$($provenanceOutput -join ' ')"
} else {
    try {
        $provenanceResult = ($provenanceOutput -join "`n") | ConvertFrom-Json
        if ($provenanceResult.ok -ne $true) {
            Add-Error "provenance leak check did not return ok=true"
        } else {
            Add-Checked "provenance leak check passed"
        }
    } catch {
        Add-Error "failed to parse provenance leak check output: $($_.Exception.Message)"
    }
}

Push-Location $root
try {
    $labelOutput = & python "scripts/provenance_label_check.py" "content/drafts/caramel-provenance-label-fixture.md" "--json" 2>&1
} finally {
    Pop-Location
}
$labelExitCode = $LASTEXITCODE
if ($labelExitCode -ne 0) {
    Add-Error "provenance label check failed: exit=$labelExitCode output=$($labelOutput -join ' ')"
} else {
    try {
        $labelResult = ($labelOutput -join "`n") | ConvertFrom-Json
        if ($labelResult.ok -ne $true) {
            Add-Error "provenance label check did not return ok=true"
        } else {
            Add-Checked "provenance label check passed"
        }
    } catch {
        Add-Error "failed to parse provenance label check output: $($_.Exception.Message)"
    }
}

Push-Location $root
try {
    $identityOutput = & python "scripts/github_identity_guard.py" "--json" 2>&1
} finally {
    Pop-Location
}
$identityExitCode = $LASTEXITCODE
if ($identityExitCode -ne 0) {
    Add-Error "GitHub identity guard failed: exit=$identityExitCode output=$($identityOutput -join ' ')"
} else {
    try {
        $identityResult = ($identityOutput -join "`n") | ConvertFrom-Json
        if ($identityResult.ok -ne $true) {
            Add-Error "GitHub identity guard did not return ok=true"
        } else {
            Add-Checked "GitHub identity guard passed"
        }
        if ($identityResult.mode -eq "embedded_copy_text_scan_only") {
            Add-Checked "embedded copy GitHub identity guard lane passed"
        }
    } catch {
        Add-Error "failed to parse GitHub identity guard output: $($_.Exception.Message)"
    }
}

Test-StandaloneCloneIdentityLane
Test-EmbeddedCopyIdentityLane
if (-not $skipStandaloneVerifierLane) {
    Test-StandaloneCloneVerifierLane
} else {
    Add-Checked "standalone clone public package verifier lane skipped at nested depth"
}

Push-Location $root
try {
    $languageOutput = & python "scripts/japanese_closeout_language_check.py" "--json" 2>&1
} finally {
    Pop-Location
}
$languageExitCode = $LASTEXITCODE
if ($languageExitCode -ne 0) {
    Add-Error "日本語完了報告ゲート検証に失敗: exit=$languageExitCode output=$($languageOutput -join ' ')"
} else {
    try {
        $languageResult = ($languageOutput -join "`n") | ConvertFrom-Json
        if ($languageResult.ok -ne $true) {
            Add-Error "日本語完了報告ゲート検証が ok=true を返していない"
        } else {
            Add-Checked "日本語完了報告ゲート検証に成功"
        }
    } catch {
        Add-Error "日本語完了報告ゲート検証の出力を解析できない: $($_.Exception.Message)"
    }
}

$editorObservation = @{
    title = "Public package fixture"
    top_image = @{ present = $true }
    toc_count = 1
    footer = @{
        required_urls = @("https://example.com/archive")
        figures = @("https://example.com/archive")
        raw_counts = @{
            "https://example.com/archive" = 0
        }
    }
    magazine = @{
        target = "Example"
        added = $true
    }
    tags = @("note", "公開前QA")
    article_type = "無料"
    final_buttons = @(
        @{
            label = "投稿する"
            clicked = $false
        }
    )
}
$editorObservationPath = Join-Path ([System.IO.Path]::GetTempPath()) ("note-editor-prepublish-observation-" + [System.Guid]::NewGuid().ToString("N") + ".json")
$editorObservation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $editorObservationPath -Encoding UTF8
Push-Location $root
try {
    $editorOutput = & python "scripts/note_editor_prepublish_verify.py" $editorObservationPath "--json" 2>&1
} finally {
    Pop-Location
    Remove-Item -LiteralPath $editorObservationPath -ErrorAction SilentlyContinue
}
$editorExitCode = $LASTEXITCODE
if ($editorExitCode -ne 0) {
    Add-Error "Note editor prepublish observation checker failed: exit=$editorExitCode output=$($editorOutput -join ' ')"
} else {
    try {
        $editorResult = ($editorOutput -join "`n") | ConvertFrom-Json
        if ($editorResult.ok -ne $true -or $editorResult.ready_for_publish -ne $true) {
            Add-Error "Note editor prepublish observation checker did not return ok=true and ready_for_publish=true"
        } else {
            Add-Checked "Note editor prepublish observation checker passed"
        }
    } catch {
        Add-Error "failed to parse Note editor prepublish observation checker output: $($_.Exception.Message)"
    }
}

try {
    $issuePacket = Get-Content -LiteralPath (Join-Path $root "issue-packet.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $issuePacket) {
        Add-Error "issue-packet.json parsed as null"
    } else {
        Add-Checked "issue-packet.json parses"
    }
} catch {
    Add-Error "failed to parse issue-packet.json: $($_.Exception.Message)"
}

$readme = Read-Text "README.md"
$rendered = Read-Text "README.rendered.html"
foreach ($needle in @("Note Publishing Suite", "verify_public_package.ps1", "note-image-upload-automation-boundary")) {
    if ($rendered.IndexOf($needle, [System.StringComparison]::Ordinal) -lt 0) {
        Add-Error "README.rendered.html missing rendered README text: $needle"
    } else {
        Add-Checked "README.rendered.html contains: $needle"
    }
}
if ($readme.IndexOf("verify:local", [System.StringComparison]::Ordinal) -lt 0) {
    Add-Error "README.md missing verification section"
} else {
    Add-Checked "README.md has verification section"
}

$textFiles = Get-ChildItem -LiteralPath $root -Recurse -File |
    Where-Object { $_.Extension -in @(".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".html", ".txt") }

$secretPatterns = @(
    "sk-[A-Za-z0-9_-]{20,}",
    "ghp_[A-Za-z0-9_]{20,}",
    "github_pat_[A-Za-z0-9_]{20,}",
    "AKIA[0-9A-Z]{16}",
    "xox[baprs]-[A-Za-z0-9-]{10,}"
)

foreach ($file in $textFiles) {
    $relative = Get-RepoRelativePath $file.FullName
    if (
        $relative -eq "scripts/verify_public_package.ps1" -or
        $relative -eq "data/provenance_leak_policy.local.json" -or
        $relative -eq "data/github_identity_guard_policy.local.json"
    ) {
        continue
    }
    $text = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    $localUserSegment = "y" + "as"
    $windowsUserPathPattern = "C:\\Users\\" + $localUserSegment
    $posixUserPathPattern = "/Users/" + $localUserSegment
    if ($text -match [regex]::Escape($windowsUserPathPattern) -or $text -match [regex]::Escape($posixUserPathPattern)) {
        Add-Error "personal local path found: $relative"
    }
    foreach ($pattern in $secretPatterns) {
        if ($text -match $pattern) {
            Add-Error "secret-like token found: $relative"
            break
        }
    }
}
Add-Checked "scanned text files for user-specific local paths and secret-like tokens"

$qaDraft = "content/drafts/sample-note-prepublish-fixture.md"
$qaDraftPath = Join-Path $root $qaDraft
$qaPreview = "content/drafts/sample-note-prepublish-fixture.preview.html"
$qaPreviewPath = Join-Path $root $qaPreview

if (-not (Test-Path -LiteralPath $qaDraftPath -PathType Leaf)) {
    Add-Error "missing local QA draft: $qaDraft"
} else {
    Add-Checked "local QA draft exists: $qaDraft"

    $qaCommands = @(
        @{
            label = "note_preview"
            args = @("scripts/note_preview.py", $qaDraft, "-o", $qaPreview)
        },
        @{
            label = "pre_publish_check"
            args = @("scripts/pre_publish_check.py", $qaDraft, "--json")
        },
        @{
            label = "note_fact_check"
            args = @("scripts/note_fact_check.py", "local", $qaDraft, "--json")
        },
        @{
            label = "note_diff_check_unknown_url"
            args = @("scripts/note_diff_check.py", "Unknown", $qaDraft, "--json")
        }
    )

    foreach ($commandSpec in $qaCommands) {
        $commandArgs = $commandSpec.args
        Push-Location $root
        try {
            $output = & python @commandArgs 2>&1
        } finally {
            Pop-Location
        }
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Add-Error "local QA command failed ($($commandSpec.label)): exit=$exitCode output=$($output -join ' ')"
        } else {
            Add-Checked "local QA command passed: $($commandSpec.label)"
        }

        if ($commandSpec.label -eq "note_diff_check_unknown_url" -and (($output -join "`n").IndexOf('"overall": "skipped"', [System.StringComparison]::Ordinal) -lt 0)) {
            Add-Error "local QA diff check did not report skipped for Unknown URL"
        }
    }

    if (-not (Test-Path -LiteralPath $qaPreviewPath -PathType Leaf)) {
        Add-Error "local QA preview was not generated: $qaPreview"
    } else {
        Add-Checked "local QA preview generated: $qaPreview"
    }
}

$qaProofPath = Join-Path ([System.IO.Path]::GetTempPath()) ("note-publishing-suite-qa-proof-" + [System.Guid]::NewGuid().ToString("N") + ".json")
$qaProofPreviewPath = Join-Path ([System.IO.Path]::GetTempPath()) ("note-publishing-suite-qa-proof-" + [System.Guid]::NewGuid().ToString("N") + ".preview.html")
Push-Location $root
try {
    $qaProofOutput = & python "scripts/run_local_draft_qa_proof.py" "--preview" $qaProofPreviewPath "--output" $qaProofPath "--json" 2>&1
} finally {
    Pop-Location
}
$qaProofExitCode = $LASTEXITCODE
if ($qaProofExitCode -ne 0) {
    Add-Error "local draft QA proof failed: exit=$qaProofExitCode output=$($qaProofOutput -join ' ')"
} elseif (-not (Test-Path -LiteralPath $qaProofPath -PathType Leaf)) {
    Add-Error "local draft QA proof did not write evidence: $qaProofPath"
} else {
    try {
        $qaProofResult = ($qaProofOutput -join "`n") | ConvertFrom-Json
        if ($qaProofResult.overall -ne "stopped_before_publish") {
            Add-Error "local draft QA proof did not stop before publish: overall=$($qaProofResult.overall)"
        } elseif ($qaProofResult.diff_check.overall -ne "skipped") {
            Add-Error "local draft QA proof did not record skipped diff for Unknown URL"
        } elseif ($qaProofResult.external_actions_performed.Count -ne 0 -or $qaProofResult.publication_actions_performed.Count -ne 0) {
            Add-Error "local draft QA proof must not perform external or publication actions"
        } else {
            Add-Checked "local draft QA proof stopped before publish with temp evidence"
        }
    } catch {
        Add-Error "failed to parse local draft QA proof output: $($_.Exception.Message)"
    }
}
Remove-Item -LiteralPath $qaProofPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $qaProofPreviewPath -Force -ErrorAction SilentlyContinue

$result = [ordered]@{
    ok = ($errors.Count -eq 0)
    command = "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1"
    root = $root
    checked_count = $checked.Count
    verification_lanes = @(
        "embedded_copy",
        "standalone_clone"
    )
    errors = @($errors)
    external_actions_performed = @()
    publication_actions_performed = @()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 5
} elseif ($errors.Count -eq 0) {
    Write-Output "OK public package verification passed"
    Write-Output "checked_count=$($checked.Count)"
    Write-Output "external_actions_performed=0"
    Write-Output "publication_actions_performed=0"
} else {
    Write-Output "NG public package verification failed"
    foreach ($err in $errors) {
        Write-Output "- $err"
    }
}

if ($errors.Count -eq 0) {
    exit 0
}
exit 1
