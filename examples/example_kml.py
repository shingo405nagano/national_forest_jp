"""
KML形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区を
KMLファイルとして保存する例を示しています。
"""

import sys
from pathlib import Path

import fastkml

# nfjパッケージのモジュールをインポートするために、親ディレクトリをsys.pathに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nfj.geospatial import GsicAddressShape
from nfj.keyhole import SubAddressKmlKwargs

if __name__ == "__main__":
    # ──────────────────────────────────────────────────────────────────────────
    # 1.データのダウンロード
    # ダウンロードする都道府県と計画区を指定し、GsicAddressShapeクラスのインスタンスを作成します。
    # インスタンス化の時点で、指定した都道府県の国有林データのダウンロードが開始されます。
    pref = "東京都"
    plan_area = "多摩森林計画区"
    output_path = Path(__file__).resolve().parent / "output_tokyo_tama.kml"

    shp = GsicAddressShape(prefecture=pref)
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをKML形式で出力
        # to_kml_docメソッドを使って、GeoDataFrameをKML形式のDocument要素のバイナリデータ
        # として取得します。SubAddressKmlKwargsを使って、KML出力時のオプションを指定できます。
        kml_doc = shp.to_kml_doc(SubAddressKmlKwargs(gdf=gdf))

        # kml_docは、fastkmlのDocument要素のバイナリデータとして取得される為、fastkmlを
        # 使ってKMLファイルとして保存します。
        kml = fastkml.KML()
        kml.append(kml_doc)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(kml.to_string(prettyprint=True))

        print(f"指定した都道府県: {pref}")
        print(f"指定した森林計画区: {plan_area}")
        print(f"出力したKML: {output_path}")
        print(f"出力したデータのサイズ: {gdf.shape}")
    finally:
        shp.cleanup()
