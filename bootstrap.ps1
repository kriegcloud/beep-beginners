# beep-beginners bootstrap for Windows. The one script that isn't Python,
# because Python (through uv) is one of the things it installs (decision D35).
#
# Run by the agent from the pasted setup sentence:
#   irm https://raw.githubusercontent.com/kriegcloud/beep-beginners/main/bootstrap.ps1 | iex
#
# Installs, all for the current user only, with no admin prompt:
#   Claude Code (official installer), uv (official installer),
#   Git for Windows (the portable build; the regular installer always asks
#   for admin), then adds the beep-beginners marketplace and installs the
#   onboarding plugin. Safe to run again: it skips what's already there.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$result = [ordered]@{}

function Add-UserPath([string]$dir) {
  $current = [Environment]::GetEnvironmentVariable('Path', 'User')
  $parts = @($current -split ';' | Where-Object { $_ })
  if ($parts -notcontains $dir) {
    [Environment]::SetEnvironmentVariable('Path', (@($dir) + $parts) -join ';', 'User')
  }
  if (($env:Path -split ';') -notcontains $dir) { $env:Path = "$dir;$env:Path" }
}

$localBin = Join-Path $env:USERPROFILE '.local\bin'
Add-UserPath $localBin

# Claude Code
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
}
$result.claude = (& claude --version) -join ' '

# uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  $env:UV_NO_MODIFY_PATH = '1'
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
}
$result.uv = (& uv --version) -join ' '

# Git for Windows, portable build, under %LOCALAPPDATA%\Programs\Git
$gitRoot = Join-Path $env:LOCALAPPDATA 'Programs\Git'
if (-not (Get-Command git -ErrorAction SilentlyContinue) -and -not (Test-Path "$gitRoot\cmd\git.exe")) {
  $release = Invoke-RestMethod https://api.github.com/repos/git-for-windows/git/releases/latest -Headers @{ 'User-Agent' = 'beep-beginners-bootstrap' }
  $asset = $release.assets | Where-Object { $_.name -match '^PortableGit-.*-64-bit\.7z\.exe$' } | Select-Object -First 1
  if (-not $asset) { throw 'Could not find the portable Git download.' }
  $exe = Join-Path $env:TEMP $asset.name
  Invoke-WebRequest $asset.browser_download_url -OutFile $exe
  New-Item -ItemType Directory -Force $gitRoot | Out-Null
  $p = Start-Process -FilePath $exe -ArgumentList '-y', "-o`"$gitRoot`"" -Wait -PassThru -WindowStyle Hidden
  if ($p.ExitCode -ne 0) { throw "Portable Git unpack failed with exit code $($p.ExitCode)" }
  Remove-Item $exe -ErrorAction SilentlyContinue
}
if (Test-Path "$gitRoot\cmd\git.exe") {
  Add-UserPath "$gitRoot\cmd"
  [Environment]::SetEnvironmentVariable('CLAUDE_CODE_GIT_BASH_PATH', "$gitRoot\bin\bash.exe", 'User')
}
$result.git = (& git --version) -join ' '

# Default model for every session: Opus 5.5 at medium effort (operator ruling
# 2026-11-07). Written before the first session so onboarding itself uses it.
$settingsPath = Join-Path $env:USERPROFILE '.claude\settings.json'
New-Item -ItemType Directory -Force (Split-Path $settingsPath) | Out-Null
$settings = if (Test-Path $settingsPath) { Get-Content $settingsPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not ($settings.PSObject.Properties.Name -contains 'model')) { $settings | Add-Member -NotePropertyName model -NotePropertyValue 'claude-opus-5-5' }
if (-not ($settings.PSObject.Properties.Name -contains 'modelSettings')) { $settings | Add-Member -NotePropertyName modelSettings -NotePropertyValue ([pscustomobject]@{ 'claude-opus-5-5' = [pscustomobject]@{ effortLevel = 'medium' } }) }
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

# The kit. Test runs point BEEP_BEGINNERS_MARKETPLACE_SOURCE at a local copy.
$source = if ($env:BEEP_BEGINNERS_MARKETPLACE_SOURCE) { $env:BEEP_BEGINNERS_MARKETPLACE_SOURCE } else { 'kriegcloud/beep-beginners' }
& claude plugin marketplace add $source 2>&1 | Out-Null
& claude plugin install kit@beep-beginners --scope user 2>&1 | Out-Null
$result.kit_plugin = [bool]((& claude plugin list 2>$null) -match 'kit@beep-beginners')

$result | ConvertTo-Json
