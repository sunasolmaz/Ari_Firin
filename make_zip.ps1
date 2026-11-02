Add-Type -Assembly 'System.IO.Compression.FileSystem'
$src = 'D:\Desktop\Arı_Fırın\dist\AriFirin_Musteri_Dagitim_Paketi_v1.0.0'
$dst = 'D:\Desktop\Arı_Fırın\dist\AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip'

if (Test-Path $dst) { Remove-Item $dst -Force }

$zip = [System.IO.Compression.ZipFile]::Open($dst, 'Create')
$files = Get-ChildItem -Path $src -Recurse -File
foreach ($file in $files) {
    $rel = $file.FullName.Substring($src.Length + 1)
    try {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $rel, 'Optimal') | Out-Null
        Write-Host "Added: $rel"
    } catch {
        Write-Host "Skipped (locked): $rel"
    }
}
$zip.Dispose()
Write-Host "`nZIP olusturuldu: $dst"
