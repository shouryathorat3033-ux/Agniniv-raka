$inventory = "dataset\processed\landcover\worldcover_inventory.txt"
$output = "dataset\raw\landcover\worldcover_2021"

New-Item -ItemType Directory -Force -Path $output | Out-Null

# The 64 India-intersecting tiles identified by the selector
$tiles = @(
"N06E072","N06E075","N06E078","N06E093",
"N09E072","N09E075","N09E078","N09E090","N09E093",
"N12E072","N12E075","N12E078","N12E090","N12E093",
"N15E072","N15E075","N15E078","N15E081",
"N18E069","N18E072","N18E075","N18E078","N18E081","N18E084","N18E087",
"N21E066","N21E069","N21E072","N21E075","N21E078","N21E081","N21E084","N21E087","N21E090","N21E093",
"N24E066","N24E069","N24E072","N24E075","N24E078","N24E081","N24E084","N24E087","N24E090","N24E093",
"N27E069","N27E072","N27E075","N27E078","N27E081","N27E084","N27E087","N27E090","N27E093","N27E096",
"N30E072","N30E075","N30E078","N30E081",
"N33E072","N33E075","N33E078",
"N36E072","N36E075"
)

Write-Host "==============================================="
Write-Host "HeatWatch - INDIA ONLY WorldCover Downloader"
Write-Host "==============================================="
Write-Host ""
Write-Host "Tiles to download: $($tiles.Count)"
Write-Host "Destination: $output"
Write-Host ""

foreach ($tile in $tiles) {

    $file = "ESA_WorldCover_10m_2021_v200_${tile}_Map.tif"
    $s3 = "s3://esa-worldcover/v200/2021/map/$file"
    $destination = Join-Path $output $file

    if (Test-Path $destination) {
        Write-Host "[SKIP] $file already exists"
        continue
    }

    Write-Host "[DOWNLOAD] $file"

    aws s3 cp $s3 $destination --no-sign-request

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] $file"
    }
    else {
        Write-Host "[FAILED] $file"
    }

    Write-Host ""
}

Write-Host "==============================================="
Write-Host "DOWNLOAD COMPLETE"
Write-Host "==============================================="