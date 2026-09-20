Add-Type -AssemblyName System.Device
$GeoWatcher = New-Object System.Device.Location.GeoCoordinateWatcher
$GeoWatcher.Start()
$i = 0
$loc = $GeoWatcher.Position.Location
while (([Double]::IsNaN($loc.Latitude) -or $loc.Latitude -eq 0) -and ($GeoWatcher.Permission -ne 2) -and ($i -lt 100)) {
    Start-Sleep -Milliseconds 100
    $loc = $GeoWatcher.Position.Location
    $i++
}
if ($GeoWatcher.Permission -ne 2 -and -not [Double]::IsNaN($loc.Latitude) -and $loc.Latitude -ne 0) {
    Write-Output "$($loc.Latitude),$($loc.Longitude)"
}
