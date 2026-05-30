Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"

function Get-WorkspaceRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

function Start-PowerShellScript {
    param(
        [string]$ScriptPath,
        [string]$WorkingDirectory
    )

    if (-not (Test-Path $ScriptPath)) {
        [System.Windows.Forms.MessageBox]::Show("Script not found:`n$ScriptPath", "ComfyUI Environments") | Out-Null
        return
    }

    Start-Process powershell.exe -WorkingDirectory $WorkingDirectory -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ScriptPath
    ) | Out-Null
}

function Open-Url {
    param([string]$Url)

    Start-Sleep -Milliseconds 800
    Start-Process $Url | Out-Null
}

function Add-Button {
    param(
        [System.Windows.Forms.Form]$Form,
        [string]$Text,
        [int]$Top,
        [scriptblock]$OnClick
    )

    $button = New-Object System.Windows.Forms.Button
    $button.Text = $Text
    $button.Width = 360
    $button.Height = 42
    $button.Left = 20
    $button.Top = $Top
    $button.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $button.Add_Click($OnClick)
    $Form.Controls.Add($button)
}

$workspaceRoot = Get-WorkspaceRoot
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$launcherExe = Join-Path $workspaceRoot "绘世启动器.exe"

$form = New-Object System.Windows.Forms.Form
$form.Text = "ComfyUI Environment Launcher"
$form.Width = 420
$form.Height = 380
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = "ComfyUI Environment Launcher"
$title.Left = 20
$title.Top = 16
$title.Width = 360
$title.Height = 24
$title.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($title)

$hint = New-Object System.Windows.Forms.Label
$hint.Text = "Start one environment at a time for heavy GPU jobs."
$hint.Left = 20
$hint.Top = 44
$hint.Width = 360
$hint.Height = 24
$hint.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Controls.Add($hint)

Add-Button -Form $form -Text "Main 8188 - Aki Launcher" -Top 78 -OnClick {
    if (-not (Test-Path $launcherExe)) {
        [System.Windows.Forms.MessageBox]::Show("Launcher not found:`n$launcherExe", "ComfyUI Environments") | Out-Null
        return
    }
    Start-Process $launcherExe -WorkingDirectory $workspaceRoot | Out-Null
    Open-Url "http://127.0.0.1:8188"
}

Add-Button -Form $form -Text "Wan Video 8189" -Top 126 -OnClick {
    Start-PowerShellScript -ScriptPath (Join-Path $PSScriptRoot "start-wan-video.ps1") -WorkingDirectory $workspaceRoot
    Open-Url "http://127.0.0.1:8189"
}

Add-Button -Form $form -Text "Flux / Kontext 8190" -Top 174 -OnClick {
    Start-PowerShellScript -ScriptPath (Join-Path $PSScriptRoot "start-flux-kontext.ps1") -WorkingDirectory $workspaceRoot
    Open-Url "http://127.0.0.1:8190"
}

Add-Button -Form $form -Text "API Bridge 8192" -Top 222 -OnClick {
    Start-PowerShellScript -ScriptPath (Join-Path $PSScriptRoot "start-api-bridge.ps1") -WorkingDirectory $workspaceRoot
    Open-Url "http://127.0.0.1:8192"
}

Add-Button -Form $form -Text "List Environments" -Top 270 -OnClick {
    Start-PowerShellScript -ScriptPath (Join-Path $PSScriptRoot "list_environments.ps1") -WorkingDirectory $workspaceRoot
}

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = "Close"
$closeButton.Width = 100
$closeButton.Height = 30
$closeButton.Left = 280
$closeButton.Top = 318
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

[void]$form.ShowDialog()
