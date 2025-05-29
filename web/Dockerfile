# 使用更稳定的Python镜像版本，指定具体的digest
FROM python:3.11.8-slim

WORKDIR /app

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 更新包管理器并安装必要的依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    procps \
    nftables \
    iptables \
    iptables-persistent \
    libpcap-dev \
    netcat-openbsd \
    net-tools \
    iproute2 \
    wget \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# 安装psutil等Python依赖
RUN pip install --no-cache-dir psutil requests

# 拷贝web目录内容
COPY *.py *.html *.css *.js *.svg *.md *.sh *.yml /app/web/
COPY data/ /app/web/data/
COPY images/ /app/web/images/

# 获取natter
RUN mkdir -p /app/natter && \
    cd /app/natter && \
    wget -q https://raw.githubusercontent.com/MikeWang000000/Natter/master/natter.py -O /app/natter/natter.py && \
    chmod +x /app/natter/natter.py

# 创建数据目录和日志目录
RUN mkdir -p /app/data /app/logs && \
    chmod -R 777 /app/data /app/logs

# 设置环境变量
ENV NATTER_PATH=/app/natter/natter.py \
    DATA_DIR=/app/data \
    LOGS_DIR=/app/logs \
    WEB_PORT=8080 \
    PYTHONUNBUFFERED=1

# 暴露Web管理界面端口
EXPOSE 8080

# 设置工作目录
WORKDIR /app/web

# 启动Natter Web管理界面
CMD ["/bin/bash", "start.sh"] 