"""
GeoJSON形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区を
GeoJSONファイルとして保存する例を示しています。
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
    output_path = Path(__file__).resolve().parent / "geoj.zip"

    shp = GsicAddressShape(prefecture=pref)
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをGeoJSON形式で出力
        # to_ziped_geojsonメソッドを使って、GeoDataFrameをZip圧縮されたGeoJSON形式のバイトストリームとして取得します。
        # alias=Trueとすれば、カラム名を日本語で取得する事ができます。
        ziped_geojson = shp.to_ziped_geojson(gdf, alias=True)

        with open(output_path, "wb") as f:
            f.write(ziped_geojson.getvalue())

        print(f"指定した都道府県: {pref}")
        print(f"指定した森林計画区: {plan_area}")
        print(f"出力したGeoJSON: {output_path}")
        print(f"出力したデータのサイズ: {gdf.shape}")
    finally:
        shp.cleanup()
