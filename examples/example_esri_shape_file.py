"""
ESRI Shapefile形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区を
Zip圧縮したESRI Shapefileとして保存する例を示しています。
Zipファイルには、Shapefileを構成する複数のファイル（.shp, .shx, .dbfなど）が含まれる他に、
属性情報を保存するCSVファイルも含まれます。

※Esri Shapefile形式は、カラムの大きさが10バイト以内の制約がある為、カラム名が短縮されてしまい
ます。特別な理由がない限り、ESRI Shapefile形式での出力は推奨されません。GeoJSONやGeoPackage
などの形式での出力を検討してください。
"""

import sys
from pathlib import Path

# nfjパッケージのモジュールをインポートするために、親ディレクトリをsys.pathに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nfj.geospatial import GsicAddressShape

if __name__ == "__main__":
    # ──────────────────────────────────────────────────────────────────────────
    # 1.データのダウンロード
    # ダウンロードする都道府県と計画区を指定し、GsicAddressShapeクラスのインスタンスを作成します。
    # インスタンス化の時点で、指定した都道府県の国有林データのダウンロードが開始されます。
    pref = "東京都"
    plan_area = "多摩森林計画区"
    output_path = Path(__file__).resolve().parent / "output_tokyo_tama_shapefile.zip"

    shp = GsicAddressShape(prefecture=pref)

    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをESRI Shapefile形式で出力
        # to_esri_shape_fileメソッドを使って、GeoDataFrameをESRI Shapefile形式のZip
        # ファイルのバイナリデータとして取得します。main_address=True, locality=Trueと
        # する事で、それぞれのShapefileを構成します。
        memory_file = shp.to_esri_shape_file(gdf, main_address=True, locality=True)
        # 取得したバイナリデータをZipファイルとして保存します。
        output_path.write_bytes(memory_file.getvalue())

        print(f"指定した都道府県: {pref}")
        print(f"指定した森林計画区: {plan_area}")
        print(f"出力したShapefileのZip: {output_path}")
        print(f"出力したデータのサイズ: {gdf.shape}")
    finally:
        shp.cleanup()
