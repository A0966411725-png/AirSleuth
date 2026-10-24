# 註冊 Windows 工作排程：每小時執行一次 scripts/collect_scheduled.py（氣象署 API 只給最新一筆，所以要每小時）
# 用法（在專案根目錄的 PowerShell 執行）：
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# 移除排程：
#   Unregister-ScheduledTask -TaskName "AirSleuth-colife-collect" -Confirm:$false

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\pythonw.exe"   # pythonw：不跳出命令列視窗
if (-not (Test-Path $python)) { throw "找不到 $python，請先建立虛擬環境" }

$action = New-ScheduledTaskAction -Execute $python -Argument "-m scripts.collect_scheduled" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "AirSleuth-colife-collect" -Action $action -Trigger $trigger -Settings $settings `
    -Description "AirSleuth 專題：每小時收集微型感測器、國家測站、氣象站資料（臺中市、高雄市）" -Force | Out-Null

Get-ScheduledTask -TaskName "AirSleuth-colife-collect" | Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime | Format-List
