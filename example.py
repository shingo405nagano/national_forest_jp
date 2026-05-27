"""
Example of GsicAddressShape.

この実行例では、滋賀県の
"""

from nfj.geospatial import GsicAddressShape

# ``prefecture="XXX"``で指定した都道府県のデータをダウンロードします。
select_prefecture = "滋賀県"
shp = GsicAddressShape(prefecture=select_prefecture)

# 森林計画区域の名前を指定して、ジオデータフレームを取得します。
gdf = shp.geodataframe(plan_area="湖南森林計画区")
print(f"GeoDataFrameのサイズ: {gdf.shape}")

# 地域での絞り込み
select = {
    "office": "滋賀",
    "branch_office": "大津",
    "locality": "西山",
}
selected_gdf = shp.query(gdf, **select)
print(f"地域で選択されたGeoDataFrameのサイズ: {selected_gdf.shape}")

# 林班での絞り込み
select = {"main_address": [25, 26]}
selected_gdf = shp.query(gdf, **select)
print(f"林班で選択されたGeoDataFrameのサイズ: {selected_gdf.shape}")
