FROM python:3.11.8-slim

WORKDIR /app

# 安装必要的依赖
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
    && rm -rf /var/lib/apt/lists/*

# 安装psutil等Python依赖
RUN pip install psutil requests --no-cache-dir

# 拷贝web目录内容
COPY . /app/web/

# 获取natter
RUN mkdir -p /app/natter && \
    cd /app/natter && \
    wget -q https://raw.githubusercontent.com/MikeWang000000/Natter/master/natter.py -O /app/natter/natter.py && \
    chmod +x /app/natter/natter.py

# 创建数据目录
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data

# 设置环境变量
ENV NATTER_PATH=/app/natter/natter.py \
    DATA_DIR=/app/data \
    WEB_PORT=8080 \
    ADMIN_PASSWORD="" \
    GUEST_ENABLED=true \
    PYTHONUNBUFFERED=1

# 暴露Web管理界面端口
EXPOSE 8080

# 设置工作目录
WORKDIR /app/web

# 启动Natter Web管理界面
CMD ["/bin/bash", "start.sh"] 