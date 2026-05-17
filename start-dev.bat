@echo off
REM ====================================
REM 开发/测试环境
REM 数据库: junyi_word_dev (独立于正式库)
REM 后端  :8001 (独立于正式 8000)
REM 使用: 双击启动，关闭窗口即停止
REM ====================================
echo === 开发环境 ===
echo 数据库: junyi_word_dev
echo 后端: http://localhost:8001
echo.

cd /d %~dp0backend
set DB_NAME=junyi_word_dev
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
