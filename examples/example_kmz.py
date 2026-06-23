"""
KMZ形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区を
KMZファイルとして保存する例を示しています。

KMZは、KMLファイルをZIP圧縮した形式であり、Google Earthなどの地理情報ソフトウェアで利用できます。
KMZはZip化したディレクトリに'doc.kml'という名前のKMLファイルが含まれており、さまざまなKMLファイル
の内容がその一つのファイルにまとめられています。KMZ形式として出力する場合は、オプションで色などを
変更する事はできません。色などを変更したい場合は、KML形式で出力する事を検討してください。
"""

import sys
from pathlib import Path

# nfjパッケージのモジュールをインポートするために、親ディレクトリをsys.pathに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nfj.geospatial import GsicAddressShape
from nfj.keyhole import Kmz

if __name__ == "__main__":
    # ──────────────────────────────────────────────────────────────────────────
    # 1.データのダウンロード
    # ダウンロードする都道府県と計画区を指定し、GsicAddressShapeクラスのインスタンスを作成します。
    # インスタンス化の時点で、指定した都道府県の国有林データのダウンロードが開始されます。
    pref = "東京都"
    plan_area = "多摩森林計画区"
    output_path = Path(__file__).resolve().parent / "output_tokyo_tama.kmz"

    shp = GsicAddressShape(prefecture=pref)
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをKMZ形式で出力
        # to_kmzメソッドを使って、GeoDataFrameをKMZ形式のファイルとして保存します。
        # KMZ形式として出力する場合は、オプションで色などを変更する事はできません。色などを変
        # 更したい場合は、KML形式で出力する事を検討してください。
        kmz = shp.to_kmz(
            gdf, folder_name="国有林データ", main_address=True, return_memory_file=False
        )
        if isinstance(kmz, Kmz):
            kmz.save(str(output_path))

    finally:
        shp.cleanup()
