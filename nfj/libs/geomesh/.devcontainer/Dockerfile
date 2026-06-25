# 最小限のPython環境
FROM python:3.13-slim

# 必要に応じて追加パッケージをインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# requirements.txt がある場合のみ有効化
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true