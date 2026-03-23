"""アプリ内のロギング設定を共通化するユーティリティ。"""

import logging


def get_logger(name: str) -> logging.Logger:
    """指定名のロガーを返します。"""
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO) -> None:
    """アプリ実行時の基本ロギング設定を適用します。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
