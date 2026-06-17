"""
Example of GsicAddressShape.

この実行例では、青森県の津軽森林計画区のデータを例に、林野庁がG空間センターで提供している、国有林
小班区画データを取得・加工する方法を紹介します。

全体の流れとしては、以下のようになります。

 1. ``GsicAddressShape``クラスに、都道府県名を指定してインスタンス化を行います。この時点で
    データはダウンロードされる為、インターネット接続が必要です。また、北海道など面積の大きな
    都道府県では、データのダウンロードに時間がかかる場合があります。

 2. 取得したデータから、任意の森林計画区域のジオデータフレームを取得します。

 3. 取得したジオデータフレームを、地域や林班などの条件で絞り込みます。

 4. 絞り込んだジオデータフレームを、GeoPackage形式やKML/KMZ形式に変換して保存します。

"""

import os

from nfj.geospatial import GsicAddressShape

# ------------------------------------------------------------------------------
# 1. データの取得
# ``prefecture="XXX"``で指定した都道府県のデータをダウンロードします。
select_prefecture = "青森県"
shp = GsicAddressShape(prefecture=select_prefecture)


# ------------------------------------------------------------------------------
# 2. 森林計画区域のジオデータフレームを取得
# 森林計画区域の名前を指定して、ジオデータフレームを取得します。
gdf = shp.geodataframe(plan_area="津軽森林計画区")
print(f"GeoDataFrameのサイズ: {gdf.shape}")


# ------------------------------------------------------------------------------
# 3. 地域や林班での絞り込み
# 地域での絞り込み
select_1 = {
    "office": "津軽",
    "branch_office": "岩木",
    "locality": "東岩木山",
}
selected_1_gdf = shp.query(gdf, **select_1)
print(f"地域で選択されたGeoDataFrameのサイズ: {selected_1_gdf.shape}")

# 林班での絞り込み
select_2 = {"main_address": [29, 30]}
selected_2_gdf = shp.query(gdf, **select_2)
print(f"林班で選択されたGeoDataFrameのサイズ: {selected_2_gdf.shape}")


# ------------------------------------------------------------------------------
# 4. GeoPackage形式やKML/KMZ形式に変換して保存
# GeoPackage形式に変換して保存する例
del select_1["locality"]  # localityを削除して、officeとbranch_officeで絞り込み
selected_gdf = shp.query(gdf, **select_1)
gpkg = shp.to_geopackage(
    selected_gdf,
    layer="sub_addrs",
    # Fieldの他にAliasも設定。QGISなどではAliasが表示されるようになります。
    alias=True,
    # 森林管理署ごとの区画が必要な場合はTrue
    office=True,
    # 森林事務所（担当区）ごとの区画が必要な場合はTrue
    branch_office=True,
    # 国有林地域ごとの区画が必要な場合はTrue
    locality=True,
    # 林班ごとの区画が必要な場合はTrue
    main_address=True,
    # 保安林の種別に区画が必要な場合はTrue
    protected_forest=True,
)
gpkg.save("nfj_example.gpkg")
if os.path.exists("nfj_example.gpkg"):
    print("GeoPackage形式で保存しました。")


# ------------------------------------------------------------------------------
# KML形式に変換して保存する例
# SubAddressKmlKwargs
from xml.dom import minidom

import fastkml

from nfj.keyhole import Kmz, SubAddressKmlKwargs

sub_addrs_kml_kwargs = SubAddressKmlKwargs(gdf=selected_gdf)
kml_doc = shp.to_kml_doc(sub_addrs_kml_kwargs)
kml = fastkml.KML()
kml.append(kml_doc)

with open("nfj_example.kml", "w", encoding="utf-8") as f:
    row_xml = kml.to_string(prettyprint=True)
    pretty_xml = (
        minidom.parseString(row_xml)
        .toprettyxml(indent="  ", encoding="utf-8")
        .decode("utf-8")
    )
    f.write(pretty_xml)

if os.path.exists("nfj_example.kml"):
    print("KML形式で保存しました。")


# ------------------------------------------------------------------------------
# KMZ形式に変換して保存する例
kmz = shp.to_kmz(
    selected_gdf,
    folder_name="国有林データ",
    main_address=True,
    locality=True,
    branch_office=False,
    office=False,
)
if isinstance(kmz, Kmz):
    kmz.save("nfj_example.kmz")
    if os.path.exists("nfj_example.kmz"):
        print("KMZ形式で保存しました。")
