@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动「外卖健康评估系统」...
start "外卖健康评估" /min cmd /c "python app.py"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5000
echo.
echo 完成：浏览器已打开 http://127.0.0.1:5000
echo 关闭那个最小化的命令行窗口即可停止服务。
echo.
pause
