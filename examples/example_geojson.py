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
    output_path = Path(__file__).resolve().parent / "output_tokyo_tama.geojson"

    shp = GsicAddressShape(prefecture=pref)
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをGeoJSON形式で出力
        # to_geojsonメソッドを使って、GeoDataFrameをGeoJSON形式の文字列として取得します。
        # output_dtype="string"とする事で、文字列型でGeoJSON形式の文字列を取得します。
        # alias=Trueとすれば、カラム名を日本語で取得する事ができます。
        geojson_str = shp.to_geojson(gdf, output_dtype="string", alias=False)
        if isinstance(geojson_str, str):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(geojson_str)

        print(f"指定した都道府県: {pref}")
        print(f"指定した森林計画区: {plan_area}")
        print(f"出力したGeoJSON: {output_path}")
        print(f"出力したデータのサイズ: {gdf.shape}")
    finally:
        shp.cleanup()
