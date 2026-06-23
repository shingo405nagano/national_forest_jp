"""
DXF形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区をDXFファイルとしてZipファイルに圧縮
して保存する例を示しています。
DXF形式は、CADソフトウェアで利用できる形式であり、国有林データをCADソフトウェアで利用する場合に便利です。
DXF形式として出力する場合は、オプションで保安林の短縮コードを小班名のラベルの下に円囲みで描画する
かどうかを指定できます。

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
    output_path = Path(__file__).resolve().parent / "output.zip"

    shp = GsicAddressShape(prefecture=pref)
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # 平面直角座標系に変換します
        gdf.to_crs(epsg=6677, inplace=True)

        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをDXF形式で出力
        # to_ziped_dxfメソッドを使って、 GeoDataFrameをDXF形式のZipファイルとして保存します。
        # Zipファイルは ByteIOオブジェクトとして取得される為、write_bytesメソッドを使ってZipファイルとして保存します。
        dxf = shp.to_ziped_dxf(
            gdf,
            dxfversion="R2010",
            main_address=True,
            locality=True,
            office=True,
            branch_office=True,
            protection_forests=True,
        )
        # # ──────────────────────────────────────────────────────────────────────
        # # 3.文字サイズの調整方法
        # # デフォルトのサイズから大きくするには、Kwargsにて各レイヤーの文字サイズを指定します。
        # # 文字サイズ以外にも調整は可能ですが、ほぼ使用しないと思われます。
        # from nfj.dxf import MainAddrsDxf, SubAddrsDxf
        # sub_addrs_dxf = SubAddrsDxf(label_size=40)
        # main_addrs_dxf = MainAddrsDxf(label_size=50)
        # dxf = shp.to_ziped_dxf(
        #     gdf,
        #     dxfversion="R2010",
        #     main_address=True,
        #     locality=True,
        #     office=True,
        #     branch_office=True,
        #     protection_forests=True,
        #     sub_address_dxf=sub_addrs_dxf,
        #     main_address_dxf=main_addrs_dxf,
        # )

        with open(output_path, "wb") as f:
            f.write(dxf.getvalue())

    finally:
        shp.cleanup()
