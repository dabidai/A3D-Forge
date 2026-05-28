FROM python:3.11-slim

WORKDIR /app

# 1. 换用阿里云 Debian 源（速度快，稳定）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 2. 更新并安装系统依赖：libgl1 + 编译工具链（pymeshlab/sentence-transformers 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libkrb5-3 \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 其余部分保持不变...
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1