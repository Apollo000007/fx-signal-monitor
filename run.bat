@echo off
REM FXSignal 起動スクリプト
REM exe がある場合はそちらを優先。無ければ Python で起動。

cd /d %~dp0

if exist "dist\FXSignal.exe" (
    start "" "dist\FXSignal.exe"
    exit /b 0
)

REM 依存パッケージ確認
py -c "import yfinance, pandas, requests" 2>nul
if errorlevel 1 (
    echo [初回セットアップ] 依存パッケージをインストールします...
    py -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo [エラー] パッケージのインストールに失敗しました
        pause
        exit /b 1
    )
)

REM GUI アプリを起動 (pyw でコンソール非表示)
start "" pyw app.py
exit /b 0
