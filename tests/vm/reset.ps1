# Reset what a Milkman test run created outside the VM, so the next run starts
# clean: the test workspace repos on GitHub, the test SSH key on GitHub, and the
# VM's Tailscale login. Reverting the VM snapshot handles everything inside it.
# Needs the test account's gh sign-in with delete_repo (onboarding adds it when
# BEEP_BEGINNERS_GH_EXTRA_SCOPES=delete_repo).
$ErrorActionPreference = 'Continue'
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = "$machinePath;$userPath;$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:USERPROFILE\.local\bin"

$login = (& gh api user --jq .login 2>$null)
if (-not $login) { 'gh is not signed in; nothing removed on GitHub'; exit 1 }
foreach ($repo in @('workspace', 'PokeLedger')) {
  & gh repo view "$login/$repo" *> $null
  if ($LASTEXITCODE -eq 0) {
    & gh repo delete "$login/$repo" --yes
    "deleted repo $login/$repo (exit $LASTEXITCODE)"
  }
}
# `gh ssh-key list` has no stable id column; ask the API for the ids.
$ids = & gh api user/keys --jq '.[] | select(.title | startswith("GitHub ")) | .id' 2>$null
foreach ($id in $ids) {
  if ($id) { & gh ssh-key delete $id --yes; "deleted SSH key $id (exit $LASTEXITCODE)" }
}
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (Test-Path $ts) { & $ts logout; 'logged out of Tailscale (remove the device from the test tailnet admin page)' }
