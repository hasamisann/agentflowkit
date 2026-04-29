param (
  [Parameter(Mandatory = $false)]
  [string]$TargetDir = ".",

  [switch]$InitGit,

  [string]$GitHubRepo
)

$TemplateRoot = $PSScriptRoot
$ErrorsFound = @()
$WarningsFound = @()

function Add-WarningMessage {
  param([string]$Message)
  $script:WarningsFound += $Message
  Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Add-ErrorMessage {
  param([string]$Message)
  $script:ErrorsFound += $Message
  Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Backup-PathIfExists {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path
  )

  if (-not (Test-Path $Path)) {
    return
  }

  $backupPath = "$Path.backup"
  if (Test-Path $backupPath) {
    Remove-Item -Path $backupPath -Recurse -Force
  }

  Copy-Item -Path $Path -Destination $backupPath -Recurse -Force
  Write-Host "  Backup created: $backupPath"
}

function Copy-TopLevelItem {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RelativePath,

    [Parameter(Mandatory = $true)]
    [string]$TargetRoot
  )

  $sourcePath = Join-Path $TemplateRoot $RelativePath
  $destinationPath = Join-Path $TargetRoot $RelativePath
  $destinationParent = Split-Path -Parent $destinationPath

  if (-not (Test-Path $sourcePath)) {
    Add-WarningMessage "Skipping missing template path: $RelativePath"
    return
  }

  if ($destinationParent -and -not (Test-Path $destinationParent)) {
    New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
  }

  Backup-PathIfExists -Path $destinationPath
  Copy-Item -Path $sourcePath -Destination $destinationPath -Recurse -Force
  Write-Host "  Copied $RelativePath"
}

function Ensure-ClaudeSkillsSymlink {
  param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot
  )

  $claudeDir = Join-Path $TargetRoot ".claude"
  $skillsPath = Join-Path $claudeDir "skills"

  if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
  }

  Backup-PathIfExists -Path $skillsPath

  try {
    New-Item -ItemType SymbolicLink -Path $skillsPath -Target "..\.agents\skills" -Force | Out-Null
    Write-Host "  Linked .claude\skills -> ..\.agents\skills"
  }
  catch {
    Add-ErrorMessage "Failed to create .claude\skills symlink. On Windows, enable Developer Mode or run PowerShell as administrator. Details: $($_.Exception.Message)"
  }
}

function Get-TemplateEntries {
  param(
    [Parameter(Mandatory = $true)]
    [string]$TemplatePath
  )

  return Get-Content $TemplatePath |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }
}

function Ensure-LineEntries {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [Parameter(Mandatory = $true)]
    [string[]]$Entries,

    [Parameter(Mandatory = $true)]
    [string]$Header
  )

  $parent = Split-Path -Parent $FilePath
  if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }

  if (-not (Test-Path $FilePath)) {
    New-Item -ItemType File -Path $FilePath -Force | Out-Null
  }

  $raw = Get-Content $FilePath -Raw
  if ($null -eq $raw) {
    $raw = ""
  }
  $normalized = $raw -replace "`r`n", "`n"
  $missing = @()

  foreach ($entry in $Entries) {
    $escaped = [regex]::Escape($entry)
    if ($normalized -notmatch "(?m)^$escaped$") {
      $missing += $entry
    }
  }

  if ($missing.Count -eq 0) {
    return $false
  }

  $section = ""
  if ($normalized -and -not $normalized.EndsWith("`n")) {
    $section += "`r`n"
  }
  if ($normalized -and $normalized.Trim()) {
    $section += "`r`n"
  }
  if ($normalized -notmatch "(?m)^$([regex]::Escape($Header))$") {
    $section += "$Header`r`n"
  }
  $section += ($missing -join "`r`n") + "`r`n"

  Add-Content -Path $FilePath -Value $section
  return $true
}

function Ensure-GitIgnoreEntries {
  param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot
  )

  $templatePath = Join-Path $TemplateRoot ".gitignore-template"
  $gitignorePath = Join-Path $TargetRoot ".gitignore"
  $entries = Get-TemplateEntries -TemplatePath $templatePath
  $changed = Ensure-LineEntries -FilePath $gitignorePath -Entries $entries -Header "# Workflow template entries"
  if ($changed) {
    Write-Host "  Merged workflow entries into .gitignore"
  }
  else {
    Write-Host "  .gitignore already contains workflow entries"
  }
}

function Ensure-GitExcludeEntries {
  param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot
  )

  $templatePath = Join-Path $TemplateRoot "exclude_template"
  $excludePath = Join-Path $TargetRoot ".git\info\exclude"
  $entries = Get-TemplateEntries -TemplatePath $templatePath
  $changed = Ensure-LineEntries -FilePath $excludePath -Entries $entries -Header "# Workflow local-only files"
  if ($changed) {
    Write-Host "  Updated .git/info/exclude"
  }
  else {
    Write-Host "  .git/info/exclude already contains workflow entries"
  }
}

function Get-GitHubSshUrl {
  param([string]$HttpsUrl)
  if ($HttpsUrl -match '^https://github.com/(.+?)(?:\.git)?/?$') {
    return "git@github.com:$($Matches[1]).git"
  }
  return $null
}

if (-not (Test-Path $TargetDir)) {
  New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

$TargetRoot = (Resolve-Path $TargetDir).Path

Write-Host "Copying workflow files to $TargetRoot..." -ForegroundColor Cyan
Copy-TopLevelItem -RelativePath ".workflow" -TargetRoot $TargetRoot
Copy-TopLevelItem -RelativePath ".opencode\commands" -TargetRoot $TargetRoot
Copy-TopLevelItem -RelativePath ".agents" -TargetRoot $TargetRoot
Ensure-ClaudeSkillsSymlink -TargetRoot $TargetRoot
Copy-TopLevelItem -RelativePath ".spec" -TargetRoot $TargetRoot
Copy-TopLevelItem -RelativePath "AGENTS.md" -TargetRoot $TargetRoot
Copy-TopLevelItem -RelativePath "CLAUDE.md" -TargetRoot $TargetRoot

Ensure-GitIgnoreEntries -TargetRoot $TargetRoot

if ($GitHubRepo) {
  $InitGit = $true
}

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
$createdGitRepo = $false

if ($InitGit -or (Test-Path (Join-Path $TargetRoot ".git"))) {
  if (-not $gitCmd) {
    Add-ErrorMessage "git is not installed or not in PATH. Install with: winget install Git.Git"
  }
  else {
    Write-Host ""
    Write-Host "=== Git Setup ===" -ForegroundColor Cyan
    Push-Location $TargetRoot
    try {
      if (-not (Test-Path (Join-Path $TargetRoot ".git"))) {
        if ($InitGit) {
          git init | Out-Null
          if ($LASTEXITCODE -eq 0) {
            $createdGitRepo = $true
            Write-Host "  Initialized git repository"
          }
          else {
            Add-ErrorMessage "Failed to initialize git repository."
          }
        }
      }
      else {
        Write-Host "  Git repository already exists"
      }

      if (Test-Path (Join-Path $TargetRoot ".git")) {
        Ensure-GitExcludeEntries -TargetRoot $TargetRoot
      }

      if ($createdGitRepo) {
        $gitignoreStatus = git status --porcelain -- ".gitignore" 2>&1
        if ($LASTEXITCODE -eq 0 -and $gitignoreStatus) {
          git add -- ".gitignore" | Out-Null
          git commit -m "chore: initialize git repository" | Out-Null
          if ($LASTEXITCODE -eq 0) {
            Write-Host "  Created initial commit for .gitignore"
          }
          else {
            Add-WarningMessage "Failed to create initial commit. Configure git user.name and user.email if needed."
          }
        }
        else {
          Write-Host "  No tracked initialization changes to commit"
        }
      }

      if ($GitHubRepo) {
        Write-Host ""
        Write-Host "=== GitHub Repository Setup ===" -ForegroundColor Cyan

        $ghCmd = Get-Command gh -ErrorAction SilentlyContinue
        if (-not $ghCmd) {
          Add-ErrorMessage "GitHub CLI (gh) is not installed or not in PATH. Install with: winget install GitHub.cli"
        }
        else {
          gh auth status | Out-Null
          if ($LASTEXITCODE -ne 0) {
            Add-ErrorMessage "GitHub CLI is not authenticated. Run: gh auth login"
          }
          else {
            $repoUrl = gh repo view $GitHubRepo --json url -q .url 2>&1
            if ($LASTEXITCODE -ne 0) {
              Write-Host "  Creating GitHub repository: $GitHubRepo (private)..."
              gh repo create $GitHubRepo --private | Out-Null
              if ($LASTEXITCODE -eq 0) {
                $repoUrl = gh repo view $GitHubRepo --json url -q .url 2>&1
                Write-Host "  Repository created: $repoUrl"
              }
              else {
                Add-ErrorMessage "Failed to create GitHub repository."
                $repoUrl = $null
              }
            }
            else {
              Write-Host "  Repository already exists: $repoUrl"
            }

            if ($repoUrl) {
              $sshUrl = Get-GitHubSshUrl -HttpsUrl $repoUrl
              $existingRemote = git remote get-url origin 2>$null
              if ($LASTEXITCODE -ne 0) {
                git remote add origin $repoUrl | Out-Null
                if ($LASTEXITCODE -eq 0) {
                  Write-Host "  Added remote 'origin': $repoUrl"
                }
                else {
                  Add-ErrorMessage "Failed to add remote 'origin'."
                }
              }
              elseif ($existingRemote -eq $repoUrl -or ($sshUrl -and $existingRemote -eq $sshUrl)) {
                Write-Host "  Remote 'origin' already set: $existingRemote"
              }
              else {
                Add-WarningMessage "Existing remote 'origin' differs from requested repository. Leaving it unchanged: $existingRemote"
              }
            }
          }
        }
      }
    }
    finally {
      Pop-Location
    }
  }
}

Write-Host ""
if ($ErrorsFound.Count -gt 0) {
  Write-Host "Initialization completed with errors." -ForegroundColor Red
}
elseif ($WarningsFound.Count -gt 0) {
  Write-Host "Initialization completed with warnings." -ForegroundColor Yellow
}
else {
  Write-Host "Initialization complete. Project at '$TargetRoot' is ready." -ForegroundColor Green
}

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open the project in your editor"
Write-Host "  2. Start OpenCode and run /specify-design"
Write-Host "  3. Start Claude Code and run /specify-design"
Write-Host '  4. For Codex, start codex in the project and invoke repo skills with $specify-design'
if (-not $InitGit) {
  Write-Host "  5. Re-run with -InitGit if you want this script to initialize git"
}

if ($ErrorsFound.Count -gt 0) {
  exit 1
}
