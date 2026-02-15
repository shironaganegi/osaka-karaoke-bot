$ErrorActionPreference = "Stop"

try {
    # WinRT types are available in PowerShell 5.1 via type accelerator or assembly load
    # For Windows 10/11
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    
    $path = "$PSScriptRoot\test_ocr.png"
    $absPath = (Convert-Path $path)

    # Helper to await WinRT async
    # Simple approach: .GetAwaiter().GetResult() works if setup correctly, 
    # but sometimes needs task wrapper. Let's try direct.

    $fileTask = [Windows.Storage.StorageFile]::GetFileFromPathAsync($absPath)
    while (-not $fileTask.IAsyncInfo.Status -eq 'Completed') { Start-Sleep -Milliseconds 10 }
    $file = $fileTask.GetResults()

    $streamTask = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    while (-not $streamTask.IAsyncInfo.Status -eq 'Completed') { Start-Sleep -Milliseconds 10 }
    $stream = $streamTask.GetResults()

    $decoderTask = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    while (-not $decoderTask.IAsyncInfo.Status -eq 'Completed') { Start-Sleep -Milliseconds 10 }
    $decoder = $decoderTask.GetResults()

    $bitmapTask = $decoder.GetSoftwareBitmapAsync()
    while (-not $bitmapTask.IAsyncInfo.Status -eq 'Completed') { Start-Sleep -Milliseconds 10 }
    $bitmap = $bitmapTask.GetResults()

    # Try standard languages
    $lang = [Windows.Globalization.Language]::new("en-US")
    
    # Check if we have English
    if (-not ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang))) {
        # Fallback to Japanese if en-US not supported (unlikely but possible)
        $lang = [Windows.Globalization.Language]::new("ja-JP")
    }

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)

    if ($engine -eq $null) {
        Write-Output "Failed to create OCR engine."
        exit 1
    }

    $ocrTask = $engine.RecognizeAsync($bitmap)
    while (-not $ocrTask.IAsyncInfo.Status -eq 'Completed') { Start-Sleep -Milliseconds 10 }
    $result = $ocrTask.GetResults()

    Write-Output "--- OCR Result ---"
    $result.Lines | ForEach-Object { $_.Text }
    Write-Output "--- End ---"

} catch {
    Write-Error $_
}
