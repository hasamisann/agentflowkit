param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$modelFile = Join-Path $projectRoot ".workflow\config\codex-model.txt"
$codexArgs = @()

if (Test-Path $modelFile) {
  $model = (Get-Content $modelFile -Raw).Trim()
  if ($model) {
    $codexArgs += @("-m", $model)
  }
}

$codexArgs += $Args

& codex @codexArgs
exit $LASTEXITCODE
