$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$diagramDir = $PSScriptRoot
$cacheDir = Join-Path $root ".npm-cache"

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

$env:npm_config_cache = $cacheDir
$env:PUPPETEER_SKIP_DOWNLOAD = "true"
$env:PUPPETEER_EXECUTABLE_PATH = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

$configPath = Join-Path $diagramDir "puppeteer-config.json"
$mmdFiles = Get-ChildItem -Path $diagramDir -Filter "*.mmd" | Sort-Object Name

foreach ($file in $mmdFiles) {
    $output = [System.IO.Path]::ChangeExtension($file.FullName, ".png")
    npx --yes -p @mermaid-js/mermaid-cli mmdc `
        -i $file.FullName `
        -o $output `
        -p $configPath `
        -b white `
        -s 2
}
