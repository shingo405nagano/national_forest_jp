"""
ログの出力先を確認するためのサンプルコードです。
"""

import sys
from pathlib import Path

# nfjパッケージのモジュールをインポートするために、親ディレクトリをsys.pathに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfj.logging_config import get_log_stream

output_log_file = Path(__file__).resolve().parent / "example_check_logging.log"

log_stream = get_log_stream()

with open(output_log_file, "w", encoding="utf-8") as f:
    f.write(log_stream)
