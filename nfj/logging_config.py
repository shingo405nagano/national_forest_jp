import logging
import os
from logging.handlers import TimedRotatingFileHandler

global LOG_FILE
LOG_FILE = os.path.join(os.path.dirname(__file__), "app.log")


def setup_logger(name="myapp"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # --- ファイル（DEBUG 以上すべて） ---
    fmt = "%(asctime)s [%(levelname)s](%(name)s.%(funcName)s -> ln:%(lineno)d): %(message)s"
    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt))

    # --- コンソール（INFO 以上のみ） ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(fmt))

    # --- 多重登録防止 ---
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def get_log_stream() -> str:
    """
    ログファイルの内容を文字列として取得する関数

    Returns:
        str: ログファイルの内容
    """
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return ""
