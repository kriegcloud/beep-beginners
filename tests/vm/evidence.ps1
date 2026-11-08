# Milkman proof evidence, collected inside the VM's desktop session (so
# Credential Manager, 1Password and Windows Hello behave as they do for the
# user). Prints one JSON object. Records presence, counts and yes/no only:
# never emails, tokens, keys or item values.
$ErrorActionPreference = 'Continue'
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = "$machinePath;$userPath;$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin"

function Try-Json([scriptblock]$b) { try { & $b } catch { $null } }
$kit = Join-Path $env:USERPROFILE 'beep-beginners'
$state = Try-Json { Get-Content "$env:USERPROFILE\.beep-beginners\onboarding.json" -Raw | ConvertFrom-Json }
$ws = if ($state) { $state.answers.workspace } else { $null }

# Every tools.yaml verify, through the kit's own checker.
$verify = Try-Json { (& uv run --quiet --script "$kit\plugins\onboarding\scripts\tools.py" verify) -join "`n" | ConvertFrom-Json }

# Claude CLI and desktop: signed in, and to the same account (compared here, never printed).
$cli = Try-Json { (& claude auth status) -join "`n" | ConvertFrom-Json }
$cliAccount = Try-Json { (Get-Content "$env:USERPROFILE\.claude.json" -Raw | ConvertFrom-Json).oauthAccount.accountUuid }
$desk = Try-Json { Get-Content "$env:APPDATA\Claude\config.json" -Raw | ConvertFrom-Json }
$deskAccount = if ($desk) { $desk.lastKnownAccountUuid } else { $null }

# GitHub CLI.
$ghStatus = (& gh auth status 2>&1) -join "`n"
$ghScopes = if ($ghStatus -match "Token scopes: (.+)") { $Matches[1] -replace "'", '' } else { '' }

# Workspace repo backed up.
$wsPushed = $null
if ($ws -and (Test-Path $ws)) {
  & git -C $ws fetch --quiet origin 2>$null
  $wsPushed = ((& git -C $ws rev-parse HEAD) -eq (& git -C $ws rev-parse '@{u}' 2>$null))
}

# User settings: auto mode.
$userSettings = Try-Json { Get-Content "$env:USERPROFILE\.claude\settings.json" -Raw | ConvertFrom-Json }

# Help line.
$sshd = Get-Service sshd -ErrorAction SilentlyContinue
$rule = Get-NetFirewallRule -Name 'beep-beginners-ssh-tailscale' -ErrorAction SilentlyContinue
$ruleAddr = if ($rule) { ($rule | Get-NetFirewallAddressFilter).RemoteAddress } else { $null }
$defaultRule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
# The desktop session runs with a filtered token, so this file is unreadable
# here; run.sh adds the count from the harness SSH session instead.
$keyCount = try { @(Get-Content 'C:\ProgramData\ssh\administrators_authorized_keys' -ErrorAction Stop | Where-Object { $_ -match '^(ssh-|ecdsa-|sk-)' }).Count } catch { 'unreadable-here' }
$ts = Try-Json { (& "$env:ProgramFiles\Tailscale\tailscale.exe" status --json) -join "`n" | ConvertFrom-Json }

$plugins = (& claude plugin list 2>$null) -join "`n"

[ordered]@{
  tools_verify = $verify
  claude = [ordered]@{
    cli_logged_in = [bool]($cli -and $cli.loggedIn)
    desktop_signed_in = [bool]$deskAccount
    same_account = [bool]($cliAccount -and $deskAccount -and ($cliAccount -eq $deskAccount))
    plugins_installed = @('onboarding','guards','explore','unslop','helper','pokeseller','job-hunt','mattpocock-skills') | Where-Object { $plugins -match [regex]::Escape($_) }
    user_default_mode = if ($userSettings) { $userSettings.permissions.defaultMode } else { $null }
  }
  claude_in_chrome_extension = [bool](Get-ChildItem "$env:LOCALAPPDATA\Google\Chrome\User Data\*\Extensions\fcoeoabgfenejglbffodgkkbkcdhcgfn" -ErrorAction SilentlyContinue)
  github = [ordered]@{
    logged_in = [bool]($ghStatus -match 'Logged in to github.com')
    scopes = $ghScopes
    workspace_pushed = $wsPushed
  }
  onepassword = [ordered]@{
    cli_signed_in = [bool](& op vault list 2>$null)   # op whoami needs an explicit op signin first
    agents_vault_present = [bool]((& op vault list 2>$null) -match [regex]::Escape($(if ($env:BEEP_BEGINNERS_AGENTS_VAULT) { $env:BEEP_BEGINNERS_AGENTS_VAULT } else { 'beep-beginners-test' })))
  }
  help_line = [ordered]@{
    sshd = if ($sshd) { "$($sshd.Status)/$($sshd.StartType)" } else { 'missing' }
    tailscale_only_rule = [bool]$rule
    rule_remote_address = $ruleAddr
    default_port22_rule_enabled = [bool]($defaultRule -and "$($defaultRule.Enabled)" -eq 'True')
    helper_key_count = $keyCount
    tailscale_state = if ($ts) { $ts.BackendState } else { $null }
  }
  onboarding_steps = if ($state) { $state.steps } else { $null }
} | ConvertTo-Json -Depth 6
