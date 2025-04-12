FROM python:3.9-slim

WORKDIR /app

# 安装依赖
RUN apt-get update && apt-get install -y \
    git \
    procps \
    iptables \
    iproute2 \
    net-tools \
    iputils-ping \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install --no-cache-dir psutil

# 克隆最新版Natter
RUN git clone https://github.com/MikeWang000000/Natter.git /app/natter-repo

# 创建目录结构
RUN mkdir -p /app/natter
RUN mkdir -p /app/web
RUN mkdir -p /app/data

# 复制Natter文件
RUN cp -r /app/natter-repo/* /app/natter/ && \
    chmod +x /app/natter/natter.py

# 复制Web管理工具文件到web目录
COPY index.html script.js style.css server.py README.md DOCKER.md INTEGRATION.md /app/web/
RUN chmod -R 755 /app/web

# 单独复制启动脚本到app目录
COPY start.sh /app/
RUN chmod +x /app/start.sh

# 创建数据目录
VOLUME ["/app/data"]

# 暴露端口
EXPOSE 8080

# 设置默认环境变量
ENV PYTHONUNBUFFERED=1
ENV NATTER_PATH=/app/natter/natter.py
ENV DATA_DIR=/app/data

# 显示文件结构调试信息
RUN echo "文件结构:" && \
    find /app -type f -name "*.py" | sort && \
    echo "Web目录:" && \
    ls -la /app/web/ && \
    echo "Natter目录:" && \
    ls -la /app/natter/

# 设置启动命令
CMD ["/app/start.sh"] 