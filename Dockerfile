# 俊宜识字系统 — 单镜像（前后端 + MySQL）构建
# Stage 1: 构建前端
FROM node:20-bullseye AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
# 生产模式 API 走相对路径（nginx 反代同一容器）
RUN npm run build

# Stage 2: 运行环境（Python 3.11 + MariaDB + Nginx + FFmpeg + Supervisor）
FROM python:3.11-slim-bullseye AS runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# MariaDB = MySQL 协议兼容实现（Debian 上官方 MySQL 替代）
RUN apt-get update && apt-get install -y --no-install-recommends \
        mariadb-server \
        mariadb-client \
        nginx \
        ffmpeg \
        supervisor \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存）
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir websockets edge-tts jieba pypinyin setuptools

# 后端源码
COPY backend/ /app/backend/

# 前端构建产物 → nginx 静态目录
COPY --from=frontend-builder /frontend/dist/ /usr/share/nginx/html/

# nginx 配置：静态文件 + /api 反代到 uvicorn:8000
COPY deploy/nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# supervisor 配置：mysqld + uvicorn + nginx
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# SQL 初始化脚本 + 启动入口
COPY sql/ /app/sql/
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# MariaDB 数据目录
VOLUME ["/var/lib/mysql"]

EXPOSE 80
ENTRYPOINT ["/app/entrypoint.sh"]