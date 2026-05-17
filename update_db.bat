@echo off
chcp 65001 >nul
echo ================================
echo   俊宜识字系统 - 数据库更新脚本
echo ================================
echo.

set /p DB_HOST="MySQL 主机地址 (默认 127.0.0.1): "
if "%DB_HOST%"=="" set DB_HOST=127.0.0.1

set /p DB_PORT="MySQL 端口 (默认 3306): "
if "%DB_PORT%"=="" set DB_PORT=3306

set /p DB_USER="MySQL 用户名 (默认 root): "
if "%DB_USER%"=="" set DB_USER=root

set /p DB_NAME="数据库名 (默认 junyi_word): "
if "%DB_NAME%"=="" set DB_NAME=junyi_word

echo.
echo 请确认以上信息后按任意键继续...
pause >nul

echo.
echo 正在更新数据库...

REM 按顺序运行迁移（用 IF NOT EXISTS 保证幂等性，重复运行不报错）
for %%f in (sql\migration_*.sql) do (
    echo --- 运行 %%~nxf ---
    mysql -h%DB_HOST% -P%DB_PORT% -u%DB_USER% -p %DB_NAME% < %%f
    if errorlevel 1 (
        echo [错误] %%~nxf 执行失败，请检查密码和数据库连接
        pause
        exit /b 1
    )
)

echo.
echo ================================
echo   数据库更新完成！
echo ================================
echo.
pause
