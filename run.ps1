# Сборка ролика по монтажному листу.
#   .\run.ps1 "D:\Ролики\Проект — утро"
#   .\run.ps1 "D:\Ролики\Проект — утро" -DryRun

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Project,
    [switch]$DryRun,
    [string]$Output
)

$env:PYTHONIOENCODING = "utf-8"
$script = Join-Path $PSScriptRoot "assemble.py"

$argsList = @($script, $Project)
if ($DryRun) { $argsList += "--dry-run" }
if ($Output) { $argsList += @("-o", $Output) }

python @argsList
exit $LASTEXITCODE
