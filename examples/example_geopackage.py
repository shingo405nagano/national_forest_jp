"""
GeoPackage形式で国有林データを出力するサンプルコード

ここでは、東京都の国有林データを取得し、指定した森林計画区を
GeoPackageファイルとして保存する例を示しています。

GISデータの出力先では、GeoPackage形式を推奨します。GeoPackageは、SQLiteデータベースをベース
にしたオープンなフォーマットであり、複数のレイヤーを1つのファイルに格納できる利点があります。
このサンプルコードでは、"小班区画"の他に、"森林管理署区画"、"森林事務所区画"、"国有林区画"、
"林班区画"、"保安林区画"の6つ以上のレイヤーを1つのGeoPackageファイルに格納する例を示しています。
保安林区画は、保安林の種別にレイヤーが作成されます。

また、GeoPackageでは、通常のFieldとしてのカラムの他に、Aliasとしてのカラムを定義する事が出来
ます。Aliasは、Fieldのカラム名とは別に、ユーザーが任意に定義したカラム名を持つ事が出来ます。
Aliasは、GISソフトウェアでの表示名として使用されます。
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
    output_path = Path(__file__).resolve().parent / "output_tokyo_tama.gpkg"

    shp = GsicAddressShape(prefecture=pref)
    gpkg = None
    try:
        gdf = shp.geodataframe(plan_area=plan_area)
        # ──────────────────────────────────────────────────────────────────────
        # 2.ダウンロードしたデータをGeoPackage形式で出力
        # to_geopackageメソッドを使って、GeoDataFrameをGeoPackage形式のファイルとして保
        # 存します。layer="sub_address"とする事で、レイヤー名を指定します。alias=Trueとすれば、
        # Field名と別でAlias名を定義する事ができます。
        gpkg = shp.to_geopackage(
            gdf,
            layer="sub_address",
            alias=True,
            # TrueとしたレイヤーがGeoPackageに出力されます。Falseとしたレイヤーは出力されません。
            # デフォルトはFalseです。
            office=True,
            branch_office=True,
            locality=True,
            main_address=True,
            protection_forests=True,
        )
        gpkg.save(str(output_path))

        print(f"指定した都道府県: {pref}")
        print(f"指定した森林計画区: {plan_area}")
        print(f"出力したGeoPackage: {output_path}")
        print(f"出力したデータのサイズ: {gdf.shape}")
    finally:
        if gpkg is not None:
            gpkg.delete_temp_file()
        shp.cleanup()
