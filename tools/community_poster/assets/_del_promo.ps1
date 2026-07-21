$ErrorActionPreference = "Continue"
$paths = @(
    "C:\Users\hysoo\Desktop\PromoRoutine.lnk",
    "$env:USERPROFILE\Desktop\PromoRoutine.lnk",
    "$env:PUBLIC\Desktop\PromoRoutine.lnk"
)

Write-Host "Desktop folder:" ([Environment]::GetFolderPath("Desktop"))

foreach ($p in $paths) {
    Write-Host "Test-Path $p =>" (Test-Path -LiteralPath $p)
    if (Test-Path -LiteralPath $p) {
        Remove-Item -LiteralPath $p -Force
        Write-Host "Removed $p"
    }
}

# Shell namespace
$shell = New-Object -ComObject Shell.Application
$desk = $shell.NameSpace(0x00)
Write-Host "--- Shell desktop items ---"
foreach ($i in $desk.Items()) {
    $n = $i.Name
    if ($n -match "Promo|Reach|로드|홍보|커뮤니티|글쓰기") {
        Write-Host ("MATCH: " + $n + " PATH=" + $i.Path)
        try {
            if ($i.Path -and (Test-Path -LiteralPath $i.Path)) {
                Remove-Item -LiteralPath $i.Path -Force
                Write-Host "Removed shell item file"
            }
        } catch {
            Write-Host "Remove failed: $_"
        }
    }
}

Write-Host "--- All shell names ---"
foreach ($i in $desk.Items()) { Write-Host $i.Name }

# Final dir
Write-Host "--- dir Desktop ---"
Get-ChildItem -Force ([Environment]::GetFolderPath("Desktop")) | Select-Object Name, Length
