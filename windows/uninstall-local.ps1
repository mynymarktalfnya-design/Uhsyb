param([string]$TaskName = "MiniMarketAlFaniya")
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "تم إلغاء التشغيل التلقائي. لم يتم حذف بيانات النظام أو النسخ الاحتياطية."
