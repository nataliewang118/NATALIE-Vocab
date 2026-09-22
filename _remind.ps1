param([switch]$Setup)

# NATALIE的词汇库 —— 到点弹个框提醒背单词，点「是」直接打开。
#   · 计划任务「NATALIE背单词」在工作日 10:30 和 17:00 各调用一次这个脚本（不带参数）
#   · 想重建任务（换时间、换电脑）： powershell -ExecutionPolicy Bypass -File _remind.ps1 -Setup
#   · 不要这个提醒了： Unregister-ScheduledTask -TaskName 'NATALIE背单词' -Confirm:$false
# 注意：这个文件必须存成 **UTF-8 带 BOM**，不然 PowerShell 5.1 按 GBK 读，中文会变乱码。

$URL = 'https://nataliewang118.github.io/NATALIE-Vocab/'

if ($Setup) {
  $me   = $PSCommandPath
  $exe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
  $act  = New-ScheduledTaskAction -Execute $exe `
            -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $me + '"')
  $days = 'Monday','Tuesday','Wednesday','Thursday','Friday'
  $trg  = @('10:30','17:00') | ForEach-Object {
            New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $_
          }
  # StartWhenAvailable：关机/睡眠错过的，开机后补一次（笔记本上这条最要紧）
  $set  = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
  $prin = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
  Register-ScheduledTask -TaskName 'NATALIE背单词' -Action $act -Trigger $trg `
    -Settings $set -Principal $prin -Force | Out-Null
  $t = Get-ScheduledTask -TaskName 'NATALIE背单词'
  Write-Host ('已建好计划任务「' + $t.TaskName + '」，状态 ' + $t.State)
  $t.Triggers | ForEach-Object { Write-Host ('  触发时间 ' + $_.StartBoundary) }
  Write-Host ('  到点执行 ' + $t.Actions[0].Execute)
  Write-Host ('  参数     ' + $t.Actions[0].Arguments)
  exit
}

Add-Type -AssemblyName System.Windows.Forms
$r = [System.Windows.Forms.MessageBox]::Show(
  "该背单词了！`n`n今天这一轮现在就开始？", 'NATALIE的词汇库',
  [System.Windows.Forms.MessageBoxButtons]::YesNo,
  [System.Windows.Forms.MessageBoxIcon]::Information)
if ($r -eq [System.Windows.Forms.DialogResult]::Yes) { Start-Process $URL }
