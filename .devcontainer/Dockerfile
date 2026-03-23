# 最小限のPython環境
FROM python:3.13-slim

# 必要に応じて追加パッケージをインストール
RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get upgrade -y \
    && apt-get -y install --no-install-recommends \
        git \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace

# Python環境の設定
RUN pip3 install --upgrade pip

# requirements.txt がある場合のみ有効化
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true