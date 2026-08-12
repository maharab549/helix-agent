$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $ScriptDir
}
python -m helix_agent @args
exit $LASTEXITCODE
