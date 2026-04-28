param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

& codex @Args
exit $LASTEXITCODE
