@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0PlantNexusCncDemo.exe" start
set "DEMO_EXIT_CODE=%ERRORLEVEL%"
if not "%DEMO_EXIT_CODE%"=="0" (
  echo.
  echo 启动失败。请查看上方错误信息及 runtime\logs。
  if not defined PLANTNEXUS_DEMO_NO_PAUSE pause
  exit /b %DEMO_EXIT_CODE%
)
echo.
echo 服务已启动且不会自动打开浏览器。请双击“查看状态.cmd”确认端口，再由局域网终端手工访问。
if not defined PLANTNEXUS_DEMO_NO_PAUSE (
  echo 按任意键关闭此窗口，演示服务会继续运行。
  pause >nul
)
exit /b 0
