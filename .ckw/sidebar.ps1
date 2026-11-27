# sidebar.ps1 -Bin <cap-gpui.exe> -Tag <name> -Work <dir>: builder CK's Settings sidebar check on
# Windows (UI Automation, what Narrator uses). Settings open on General, signed out: which sidebar
# controls UIA reaches (name, control type, Invoke), then an Invoke on Sign In: the button turns into
# Cancel Sign In. Scratch profile, nothing ships.
param([string]$Bin, [string]$Tag, [string]$Work)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
$P = [System.Windows.Automation.PropertyCondition]
$D = Join-Path $Work $Tag
New-Item -ItemType Directory -Force "$D\data\meetings", "$D\logs" | Out-Null
'{"enabled": true, "setupCompleted": true}' | Set-Content -Encoding ascii "$D\data\meetings\settings.json"
'{"general_settings":{"hasCompletedOnboarding":true,"hasCompletedStartup":true,"enableNotifications":false,"enableTelemetry":false,"recordingCountdown":0,"serverUrl":"http://127.0.0.1:9"}}' | Set-Content -Encoding ascii "$D\data\store"
$env:CAP_GPUI_APP_DATA_DIR = "$D\data"; $env:CAP_GPUI_LOG_DIR = "$D\logs"; $env:CAP_GPUI_NO_TRAY = '1'
$env:CAP_GPUI_AUTO_SETTINGS = 'general'; $env:RUST_LOG = 'warn,cap_gpui=info'
# GPUI builds its accessibility tree while a screen reader runs, as Narrator users have it.
Start-Process "$env:WINDIR\System32\Narrator.exe"; Start-Sleep -Seconds 8
$p = Start-Process -PassThru -FilePath $Bin -RedirectStandardOutput "$D\app.out" -RedirectStandardError "$D\app.err"
Start-Sleep -Seconds 15
$out = New-Object System.Collections.Generic.List[string]
function Find($name) {
  $cond = New-Object System.Windows.Automation.AndCondition(
    (New-Object $P($A::ProcessIdProperty, $p.Id)), (New-Object $P($A::NameProperty, $name)))
  $A::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
}
function Describe($e) {
  if ($e -eq $null) { return "not reached" }
  $patterns = ($e.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName -replace 'PatternIdentifiers.Pattern', '' }) -join ','
  "type=$($e.Current.ControlType.ProgrammaticName -replace 'ControlType.', '') patterns=$patterns"
}
foreach ($name in 'General', 'Click to sign in', 'View previous versions', 'Check for updates', 'Sign In') {
  $out.Add("[$Tag] reaches '$name': $(Describe (Find $name))")
}
$sign = Find 'Sign In'
if ($sign -ne $null) {
  try {
    $sign.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    $out.Add("[$Tag] invoked Sign In")
  } catch { $out.Add("[$Tag] invoke failed: $_") }
  Start-Sleep -Seconds 3
  $out.Add("[$Tag] after invoke, 'Cancel Sign In': $(Describe (Find 'Cancel Sign In'))")
} else {
  $out.Add("[$Tag] no Sign In element to invoke")
}
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Name Narrator -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3
Get-Process | Where-Object { $_.ProcessName -match '^(msedge|chrome)$' } | Stop-Process -Force -ErrorAction SilentlyContinue
$panics = (Select-String -Path "$D\logs\*" -Pattern 'panicked' -ErrorAction SilentlyContinue | Measure-Object).Count
$out.Add("[$Tag] panics: $panics")
$out | Tee-Object -Append "$Work\summary.txt"
