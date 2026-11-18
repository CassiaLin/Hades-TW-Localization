@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   黑帝斯 Hades — 台灣繁體中文化安裝程式 (Player Mode)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 未在 PATH 中找到 Python。請先安裝 Python 3.10 以上版本。
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 需要 Python 3.10 以上版本。請更新 Python 後再試。
    pause
    exit /b 1
)

python -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 缺少必要套件 ^(Pillow^)。
    echo 請先執行：python -m pip install -r requirements.txt
    pause
    exit /b 1
)

python hades_mod_cli.py player status
echo.
echo [1] 安裝／更新《黑帝斯 Hades》繁體中文化
echo [2] 查看目前安裝與譯文包狀態
echo [3] 更新已安裝的譯文包 (update-pack)
echo [4] 解除安裝並還原原版簡體中文檔案
echo [0] 離開
echo.
set /p CHOICE=請選擇功能 [0-4]: 

set "CLI_RC=0"
if "%CHOICE%"=="1" (
    python hades_mod_cli.py player install
    set "CLI_RC=!ERRORLEVEL!"
    goto done
)
if "%CHOICE%"=="2" (
    python hades_mod_cli.py player status
    set "CLI_RC=!ERRORLEVEL!"
    goto done
)
if "%CHOICE%"=="3" (
    python hades_mod_cli.py player update-pack
    set "CLI_RC=!ERRORLEVEL!"
    goto done
)
if "%CHOICE%"=="4" (
    python hades_mod_cli.py player uninstall
    set "CLI_RC=!ERRORLEVEL!"
    goto done
)
exit /b 0

:done
echo.
if not "%CLI_RC%"=="0" (
    echo [失敗] 執行未完成，結束代碼：%CLI_RC%
) else (
    echo [完成] 操作已成功完成。
)
pause
exit /b %CLI_RC%
