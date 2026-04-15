# ============================================================================
#  FX Signal Monitor -- create desktop shortcut with custom icon
# ----------------------------------------------------------------------------
#  1. Generate "FX.ico" in the Bank folder
#  2. Create "FX Signal Monitor.lnk" on the Desktop, pointing to start.bat
#  3. Also drop a copy next to start.bat inside the Bank folder
#
#  Usage: right-click this file -> "Run with PowerShell"
#         or from a PowerShell prompt:
#             powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
# ============================================================================

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$icoPath = Join-Path $root "FX.ico"
$target  = Join-Path $root "start.bat"

if (-not (Test-Path $target)) {
    Write-Host "ERROR: start.bat not found at $target" -ForegroundColor Red
    exit 1
}

# ---- DestroyIcon P/Invoke --------------------------------------------------
if (-not ([System.Management.Automation.PSTypeName]"Win32Icon").Type) {
    Add-Type -Namespace "" -Name "Win32Icon" -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool DestroyIcon(System.IntPtr hIcon);
"@
}

# ---- 1. Generate ICO -------------------------------------------------------
function New-FxIcon {
    param([string]$OutPath)

    $size = 256
    $bmp  = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g    = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    $g.Clear([System.Drawing.Color]::Transparent)

    # Outer rounded rect
    $rect = New-Object System.Drawing.Rectangle 8, 8, ($size - 16), ($size - 16)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r    = 48
    $path.AddArc($rect.X,            $rect.Y,            $r, $r, 180, 90)
    $path.AddArc($rect.Right - $r,   $rect.Y,            $r, $r, 270, 90)
    $path.AddArc($rect.Right - $r,   $rect.Bottom - $r,  $r, $r,   0, 90)
    $path.AddArc($rect.X,            $rect.Bottom - $r,  $r, $r,  90, 90)
    $path.CloseFigure()

    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $rect,
        ([System.Drawing.Color]::FromArgb(255, 34, 211, 238)),
        ([System.Drawing.Color]::FromArgb(255, 168, 85, 247)),
        [System.Drawing.Drawing2D.LinearGradientMode]::ForwardDiagonal)
    $g.FillPath($brush, $path)

    # Inner dark panel
    $inner = New-Object System.Drawing.Rectangle 28, 28, ($size - 56), ($size - 56)
    $pathI = New-Object System.Drawing.Drawing2D.GraphicsPath
    $rI = 36
    $pathI.AddArc($inner.X,          $inner.Y,           $rI, $rI, 180, 90)
    $pathI.AddArc($inner.Right - $rI,$inner.Y,           $rI, $rI, 270, 90)
    $pathI.AddArc($inner.Right - $rI,$inner.Bottom - $rI,$rI, $rI,   0, 90)
    $pathI.AddArc($inner.X,          $inner.Bottom - $rI,$rI, $rI,  90, 90)
    $pathI.CloseFigure()
    $innerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(240, 15, 21, 38))
    $g.FillPath($innerBrush, $pathI)

    # Candlesticks (3 bars)
    $candles = @(
        @{ x = 72;  open = 150; close = 96;  wickTop = 80;  wickBot = 168; up = $true  },
        @{ x = 118; open = 130; close = 170; wickTop = 110; wickBot = 190; up = $false },
        @{ x = 164; open = 170; close = 64;  wickTop = 56;  wickBot = 184; up = $true  }
    )
    foreach ($c in $candles) {
        if ($c.up) {
            $col = [System.Drawing.Color]::FromArgb(255, 16, 185, 129)
        } else {
            $col = [System.Drawing.Color]::FromArgb(255, 244, 63, 94)
        }
        $pen    = New-Object System.Drawing.Pen $col, 4
        $brushC = New-Object System.Drawing.SolidBrush $col
        $g.DrawLine($pen, ($c.x + 10), $c.wickTop, ($c.x + 10), $c.wickBot)
        $top = [Math]::Min($c.open, $c.close)
        $h   = [Math]::Abs($c.close - $c.open)
        $g.FillRectangle($brushC, $c.x, $top, 20, $h)
        $pen.Dispose()
        $brushC.Dispose()
    }

    # "FX" text
    $font = New-Object System.Drawing.Font "Segoe UI", 56, ([System.Drawing.FontStyle]::Bold)
    $fmt  = New-Object System.Drawing.StringFormat
    $fmt.Alignment     = [System.Drawing.StringAlignment]::Center
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
    $textBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $textRect  = New-Object System.Drawing.RectangleF 0, 150, $size, 80
    $g.DrawString("FX", $font, $textBrush, $textRect, $fmt)

    $brush.Dispose()
    $innerBrush.Dispose()
    $textBrush.Dispose()
    $font.Dispose()
    $g.Dispose()

    $hIcon = $bmp.GetHicon()
    $icon  = [System.Drawing.Icon]::FromHandle($hIcon)
    $fs    = [System.IO.File]::Open($OutPath, [System.IO.FileMode]::Create)
    $icon.Save($fs)
    $fs.Close()
    [Win32Icon]::DestroyIcon($hIcon) | Out-Null
    $bmp.Dispose()
}

Write-Host "Generating FX.ico ..." -ForegroundColor Cyan
New-FxIcon -OutPath $icoPath
Write-Host "  -> $icoPath" -ForegroundColor Green

# ---- 2. Create shortcuts ---------------------------------------------------
function New-Shortcut {
    param([string]$LinkPath, [string]$Target, [string]$IconPath, [string]$WorkingDir)
    $sh       = New-Object -ComObject WScript.Shell
    $shortcut = $sh.CreateShortcut($LinkPath)
    $shortcut.TargetPath       = $Target
    $shortcut.WorkingDirectory = $WorkingDir
    $shortcut.IconLocation     = "$IconPath,0"
    $shortcut.Description      = "FX Signal Monitor - multi-method real-time dashboard"
    $shortcut.WindowStyle      = 1
    $shortcut.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
$linkD   = Join-Path $desktop "FX Signal Monitor.lnk"
$linkL   = Join-Path $root "FX Signal Monitor.lnk"

Write-Host "Creating shortcuts ..." -ForegroundColor Cyan
New-Shortcut -LinkPath $linkD -Target $target -IconPath $icoPath -WorkingDir $root
Write-Host "  -> $linkD" -ForegroundColor Green
New-Shortcut -LinkPath $linkL -Target $target -IconPath $icoPath -WorkingDir $root
Write-Host "  -> $linkL" -ForegroundColor Green

Write-Host ""
Write-Host "Done. Double-click 'FX Signal Monitor' on your Desktop to launch." -ForegroundColor Yellow
Write-Host ""
