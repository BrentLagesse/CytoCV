$ErrorActionPreference = "Stop"

$diagramDir = $PSScriptRoot
$defaultCacheDir = Join-Path ([System.IO.Path]::GetTempPath()) "cytocv-diagram-npm-cache"
$cacheDir = if ($env:CYTOCV_DIAGRAM_NPM_CACHE) { $env:CYTOCV_DIAGRAM_NPM_CACHE } else { $defaultCacheDir }
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$scale = 4
$minimumWidth = 900
$minimumHeight = 200

if ($env:CYTOCV_DIAGRAM_SCALE) {
    $scale = [int]$env:CYTOCV_DIAGRAM_SCALE
}

if (-not (Test-Path -LiteralPath $edgePath)) {
    throw "Microsoft Edge executable was not found at $edgePath"
}

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

$env:npm_config_cache = $cacheDir
$env:PUPPETEER_SKIP_DOWNLOAD = "true"
$env:PUPPETEER_EXECUTABLE_PATH = $edgePath

$configPath = Join-Path $diagramDir "puppeteer-config.json"
$mmdFiles = Get-ChildItem -Path $diagramDir -Filter "*.mmd" | Sort-Object Name

Add-Type -AssemblyName System.Drawing

function Test-PngOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing rendered PNG: $Path"
    }

    $expected = [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
    $stream = [System.IO.File]::OpenRead($Path)

    try {
        $header = New-Object byte[] 8
        $read = $stream.Read($header, 0, 8)
        if ($read -ne 8) {
            throw "PNG header is truncated: $Path"
        }

        for ($i = 0; $i -lt $expected.Length; $i++) {
            if ($header[$i] -ne $expected[$i]) {
                throw "Invalid PNG signature: $Path"
            }
        }

        $stream.Position = 0
        $image = [System.Drawing.Image]::FromStream($stream, $false, $true)
        try {
            if ($image.Width -le 0 -or $image.Height -le 0) {
                throw "Rendered PNG has invalid dimensions: $Path"
            }

            if ($image.Width -lt $minimumWidth -or $image.Height -lt $minimumHeight) {
                throw "Rendered PNG is below publication size threshold: $Path ($($image.Width)x$($image.Height))"
            }

            Write-Host "Validated $([System.IO.Path]::GetFileName($Path)) ($($image.Width)x$($image.Height))"
        }
        finally {
            $image.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

foreach ($file in $mmdFiles) {
    $output = [System.IO.Path]::ChangeExtension($file.FullName, ".png")
    if (Test-Path -LiteralPath $output) {
        Remove-Item -LiteralPath $output -Force
    }

    Write-Host "Rendering $($file.Name)"
    & npx --yes -p @mermaid-js/mermaid-cli mmdc `
        -i $file.FullName `
        -o $output `
        -p $configPath `
        -b white `
        -s $scale

    if ($LASTEXITCODE -ne 0) {
        throw "Mermaid CLI failed while rendering $($file.Name)"
    }

    Test-PngOutput -Path $output
}
