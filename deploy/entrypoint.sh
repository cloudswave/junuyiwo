#!/bin/bash
set -e

# 初始化 MariaDB 数据目录（首次运行）
if [ ! -d "/var/lib/mysql/mysql" ]; then
  echo ">> initializing MariaDB..."
  mysqld --initialize-insecure --user=mysql
  mysqld --daemonize --user=mysql
  sleep 3
  mysql -u root -e "CREATE DATABASE IF NOT EXISTS junyi_word CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
  for f in /app/sql/migration_*.sql; do
    echo ">> applying $(basename $f)"
    mysql -u root junyi_word < "$f" 2>/dev/null || true
  done
  mysqladmin shutdown
  sleep 2
else
  echo ">> MariaDB data exists, skipping init"
fi

# 启动 MariaDB（前台）
echo ">> starting MariaDB..."
mkdir -p /var/run/mysqld
chown mysql:mysql /var/run/mysqld
mysqld --user=mysql &
MYSQL_PID=$!

# 等待 MariaDB 就绪
for i in $(seq 1 60); do
  if mysqladmin ping --silent 2>/dev/null; then
    echo ">> MariaDB ready"
    break
  fi
  echo ">> waiting for MariaDB ($i/60)..."
  sleep 1
done

# 启动 supervisor（后端 + 前端 nginx）
echo ">> starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf