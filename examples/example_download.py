"""
指定した都道府県の国有林データをダウンロードするサンプルコード

ここでは、東京都の国有林データをダウンロードする例を示しています。

最終的にこのファイルを実行しても、GeoJSONなどのファイルは出力されません。
GeoDataFrameの作成が、このサンプルコードの目的です。
"""

import sys
from pathlib import Path

import shapely

# nfjパッケージのモジュールをインポートするために、親ディレクトリをsys.pathに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfj.geospatial import GsicAddressShape

if __name__ == "__main__":
    # ──────────────────────────────────────────────────────────────────────────
    # 1.データのダウンロード
    # ダウンロードする都道府県と計画区を指定
    pref = "東京都"
    # GeoDataFrame化する際には、森林計画区を指定する必要があります。
    plan_area = "多摩森林計画区"

    # ダウンロードの実行
    shp = GsicAddressShape(prefecture=pref)

    # ダウンロードしたデータから、指定した森林計画区のGeoDataFrameを取得
    # ダウンロードしたデータは、一時ファイルとして保存されている為、他の森林計画区のGeoDataFrame
    # を取得する場合であっても、再度ダウンロードする必要はありません。'plan_area=xxx'に新たな
    # 森林計画区を指定することで、GeoDataFrameを取得することができます。
    gdf = shp.geodataframe(plan_area=plan_area)

    print(f"""
指定した都道府県: {pref}
指定した森林計画区: {plan_area}
ダウンロードしたデータのサイズ: {gdf.shape}
""")

    # ──────────────────────────────────────────────────────────────────────────
    # 2.ダウンロードしたデータから任意の場所を抽出する例
    # 2-1.森林管理署・森林事務所・国有林・林班主番などで抽出する場合
    office = "東京神奈川"
    branch_office = "高尾"
    locality = "裏高尾町1304番"
    main_addrs_codes = [212, 213, 214]

    selected_gdf = shp.query(
        gdf,
        office=office,
        branch_office=branch_office,
        locality=locality,
        main_addrs_codes=main_addrs_codes,
    )
    print(f"指定した条件で抽出したデータのサイズ: {selected_gdf.shape}")

    # 2-2.緯度経度で抽出する場合
    gdf = gdf.to_crs(epsg=4326)  # 緯度経度に変換
    min_lon, max_lon = 139.211567435, 139.236955196
    min_lat, max_lat = 35.643881910, 35.661121019
    # cxメソッドを使って、指定した緯度経度の範囲で抽出
    _ = gdf.cx[min_lon:max_lon, min_lat:max_lat]
    print(f"cxメソッドで抽出したデータのサイズ: {_.shape}")

    # 2-3.intersectsメソッドを使って、指定した緯度経度の範囲で抽出
    scope = shapely.geometry.box(min_lon, min_lat, max_lon, max_lat)
    _ = gdf[gdf.intersects(scope)]
    print(f"intersectsメソッドで抽出したデータのサイズ: {_.shape}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3.GeoDataFrameの要素をエンコードする場合
    # エンコードは、データを文字列から数値に変換する事で、データのサイズを小さくする事が出来ます。
    encoded_gdf = shp.encode(gdf)
    decoded_gdf = shp.decode(encoded_gdf)
    print(f"""
Original: {gdf["branch_office"].iloc[0]}
Encoded: {encoded_gdf["branch_office"].iloc[0]}
Decoded: {decoded_gdf["branch_office"].iloc[0]}
""")

    # ──────────────────────────────────────────────────────────────────────────
    # 4.カラムを英語から日本語に変換する場合
    ja_gdf = gdf.rename(columns=shp.field_and_alias())
    print(f"""
Original columns: {gdf.columns.tolist()[:5]}
Japanese columns: {ja_gdf.columns.tolist()[:5]}
""")
    # ──────────────────────────────────────────────────────────────────────────
    # 5.ダウンロードしたデータの一時ファイルを削除
    shp.cleanup()
