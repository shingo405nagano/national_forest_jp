import datetime
import re
from typing import Any, NamedTuple

import geopandas as gpd
import shapely

from .config import ConservationCoding, GreenCorridorCoding
from .fetch import GsShapeFile
from .fields import FieldInfo


def zen_to_han(text: str) -> str:
    """全角文字を半角文字に変換します。

    Args:
        text: 変換対象の文字列。

    Returns:
        全角文字が半角文字に変換された文字列。
    """
    # 全角スペースを半角スペースに変換
    text = text.replace("　", " ")
    # 全角英数字を半角英数字に変換
    text = "".join(
        chr(ord(char) - 0xFEE0) if "！" <= char <= "～" else char for char in text
    )
    return text.replace("－", "-").replace("　", "")


def convert_wareki_to_seireki(wareki: str) -> int:
    """和暦を西暦に変換する関数。

    Args:
        wareki: 和暦の文字列（例: "令和５年度樹立"）。

    Returns:
        西暦の整数（例: 2023）。
    """
    if not isinstance(wareki, str):
        return wareki
    wareki = zen_to_han(wareki.strip()).replace("年度樹立", "").replace("元", "1")

    era_mapping = {
        "平成": 1989,
        "令和": 2019,
    }
    for era, start_year in era_mapping.items():
        if wareki.startswith(era):
            wy = int(re.findall(r"\d+", wareki)[0])
            return start_year + wy - 1
    raise ValueError(f"不明な和暦形式: {wareki}")


class _AddrsColumns(NamedTuple):
    """小班区画の処理にて使用する英名の属性名を定義するクラス。
    基本はfieldsを参照
    """

    city: str = "city"  # 市町村
    plan_area: str = "plan_area"  # 森林計画区
    office: str = "office"  # 森林管理署
    branch_office: str = "branch_office"  # 担当区
    locality: str = "locality"  # 国有林
    main_address: str = "main_address"  # 林班主番
    address: str = "address"  # 林小班
    sub_address: str = "sub_address"  # 小班
    establishment_year: str = "establishment_year"  # 樹立年度
    tree_age_1: str = "tree_age_1"  # 樹齢1
    tree_age_2: str = "tree_age_2"  # 樹齢2
    tree_age_3: str = "tree_age_3"  # 樹齢3
    conservation: str = "conservation"  # 保護林
    green_corridor: str = "green_corridor"  # 緑の回廊


class GsicAddressShape(GsShapeFile):
    """国有林の小班区画データを扱うクラス。

    GsShapeFile クラスを継承し、国有林の小班区画に特化した機能を提供します。
    """

    def __init__(
        self,  #
        prefecture: str,
        year: int = 2025,
        endswith: str = ".shp",
    ):
        """GsicAddressShape クラスのインスタンスを初期化します。

        Args:
            prefecture: 取得対象の都道府県名。
            year: 取得対象年。
            endswith: 対象ファイルの拡張子。

        Raises:
            ValueError: URL が見つからない場合。
        """
        super().__init__(
            prefecture=prefecture,
            year=year,
            category="address",
            endswith=endswith,
        )

    def geodataframe(self, plan_area: str, **kwargs: Any) -> gpd.GeoDataFrame:
        """指定した森林計画区の小班区画データを GeoDataFrame として返します。

        ここでは、内部で以下の処理が行われます。
            1. EsriShapefile を GeoDataFrame として読み込む。
            2. GeoDataFrame のカラムを英名に変換し、必要なカラムのみを残す。
            3. 各カラムのデータ型を '.confs/fields.yaml' に定義されたものに基づいて適切に変換する。
            4. Nan 値を適切なデフォルト値に置換する。
            5. 国有林名に全角数字が含まれるため、全角を半角に変換する。
            6. 林小班名に余計な文字が含まれる為、削除してしまう。
            7. 樹立年度を和暦から西暦に変換する。
            8. 樹齢を修正する。
            9. 保護林の区分コードを正式な名称に変換する。
            10. 緑の回廊の区分コードを正式な名称に変換する。
            11. 重複する林小班が存在する場合は、1つにまとめる。
            12. Geometry のバリデーションを行い、無効なジオメトリを修正する。

        Args:
            plan_area: 森林計画区の名称。

        Returns:
            指定した森林計画区の小班区画データを含む GeoDataFrame。
        """
        # EsriShapefile を GeoDataFrame として読み込む
        gdf = self._read_file(plan_area=plan_area)
        # 樹立年度を西暦に変換する
        gdf["樹立年度"] = gdf["樹立年度"].apply(convert_wareki_to_seireki)
        # 更新年を記録
        gdf["updated_year"] = datetime.datetime.now().year
        gdf = self.__cast_geodataframe(gdf)
        org_columns = gdf.columns
        addrs_cols = _AddrsColumns()
        # 国有林名には全角数字が含まれるため、全角を半角に変換する
        gdf[addrs_cols.locality] = gdf[addrs_cols.locality].apply(zen_to_han)
        # 林小班名に余計な文字が含まれる為、削除してしまう
        gdf[addrs_cols.address] = gdf[addrs_cols.address].apply(self.__replace_address)
        # 重複する林小班が存在する場合は、1つにまとめる
        gdf = gdf.dissolve(
            by=[addrs_cols.office, addrs_cols.address], as_index=False, aggfunc="first"
        )
        # 樹齢を修正する
        gdf[addrs_cols.tree_age_1] = gdf.apply(
            lambda row: self.__fix_tree_age(
                row[addrs_cols.establishment_year], row[addrs_cols.tree_age_1]
            ),
            axis=1,
        )
        gdf[addrs_cols.tree_age_2] = gdf.apply(
            lambda row: self.__fix_tree_age(
                row[addrs_cols.establishment_year], row[addrs_cols.tree_age_2]
            ),
            axis=1,
        )
        gdf[addrs_cols.tree_age_3] = gdf.apply(
            lambda row: self.__fix_tree_age(
                row[addrs_cols.establishment_year], row[addrs_cols.tree_age_3]
            ),
            axis=1,
        )
        # 保護林の区分コードを正式な名称に変換する
        gdf[addrs_cols.conservation] = gdf[addrs_cols.conservation].apply(
            self.__decode_conservation
        )
        # 緑の回廊の区分コードを正式
        gdf[addrs_cols.green_corridor] = gdf[addrs_cols.green_corridor].apply(
            self.__decode_green_corridor
        )
        # Geometry のバリデーションを行い、無効なジオメトリを修正する
        gdf["geometry"] = gdf["geometry"].apply(self.validate_geometry)  # type: ignore
        return gdf[org_columns]  # 元の列順に戻す

    def __cast_geodataframe(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性を適切なデータ型に変換します。

        ここで処理されるデータ型は、'.confs/fields.yaml' に定義されたものに基づいています。

        Args:
            gdf: データ型を変換する GeoDataFrame。

        Returns:
            データ型が変換された GeoDataFrame。
        """
        # 属性名をオリジナルの日本語から英語に変換し、必要な属性のみを残す
        gdf.rename(columns=self.fields.rename_dict_org_to_en(), inplace=True)
        gdf = gdf[self.fields.use_default_en_fields()].copy()
        for col in gdf.columns:
            if col == "geometry":
                # geometry列は変換しない
                continue
            field_info: FieldInfo = self.fields.field_info(col)  # type: ignore
            gdf[col] = gdf[col].apply(lambda x: field_info.cast(x))
            gdf[col].fillna(field_info.default, inplace=True)
            if field_info.dtype == str:  # type: ignore
                gdf[col] = gdf[col].replace(
                    {"nan": field_info.default, "NaN": field_info.default}
                )
        return gdf

    def __replace_address(self, text: str) -> str:
        """林小班名に余計な文字が含まれる為、削除してしまう。

        Args:
            text: 変換対象の文字列。

        Returns:
            余計な文字が削除された文字列。
        """
        return text.replace("_林班_", "").strip()

    def __fix_tree_age(self, ad: int, age: int) -> int:
        """樹齢の値を修正するための関数。

        Args:
            ad: 樹立年度の西暦年。
            age: 樹齢の値

        Returns:
            修正された樹齢の値、林齢は計算結果に1を加算した値を返す。
        """
        now_year = datetime.datetime.now().year
        diff_year = now_year - ad
        return age + diff_year + 1

    def __decode_conservation(self, code: int) -> str:
        """保護林の区分コードを正式な名称に変換する関数。

        Args:
            code: 保護区分コード。

        Returns:
            保護区分のラベル。
        """
        try:
            code = int(code)
        except Exception:
            return str(code)
        else:
            coding = ConservationCoding()
            return coding.decode_original(code)

    def __decode_green_corridor(self, code: int) -> str:
        """緑の回廊の区分コードを正式な名称に変換する関数。

        Args:
            code: 緑の回廊区分コード。

        Returns:
            緑の回廊区分のラベル。
        """
        try:
            code = int(code)
        except Exception:
            return str(code)
        else:
            coding = GreenCorridorCoding()
            return coding.decode(code)

    def validate_geometry(
        self, geometry: shapely.geometry.base.BaseGeometry
    ) -> shapely.geometry.base.BaseGeometry:
        """ジオメトリのバリデーションを行い、無効なジオメトリを修正します。

        ここでは、GeometryCollectionを避ける為に、'method="structure"' を指定しています。
        Args:
            geometry: バリデーションするジオメトリ。

        Returns:
            バリデーションされたジオメトリ。
        """
        geometry = shapely.make_valid(geometry, method="structure", keep_collapsed=True)
        return geometry

    def data_summary(self, gdf: gpd.GeoDataFrame, **kwargs: Any) -> dict[str, Any]:
        """GeoDataFrame のデータ概要を返します。

        以下の情報を含む辞書を返します。

            ├─ 森林計画区
            │   ├─ 森林管理署
            │   │   ├─ 担当区
            │   │   │   ├─ 国有林
            │   │   │   ...
            │   ... ... ...
            ├─ 森林計画区2
            ...

        Args:
            gdf: データ概要を取得する GeoDataFrame。
            main_addrs: 林班主番を含めるかどうか。デフォルトは False。

        Returns:
            GeoDataFrame のデータ概要を含む辞書。

        ## Kwargs:
            - main_addrs: 林班主番を含めるかどうか。デフォルトは False。
        """
        acols = _AddrsColumns()
        grouping = [
            acols.plan_area,
            acols.office,
            acols.branch_office,
            acols.locality,
        ]
        if kwargs.get("main_addrs", False):
            grouping.append(acols.main_address)
        # 列が存在する事を確認
        for col in grouping:
            if col not in gdf.columns:
                raise ValueError(f"列 '{col}' が GeoDataFrame に存在しません。")

        smy_df = gdf.groupby(by=grouping).agg({"geometry": "count"}).fillna("-")
        summary = {}
        for _, row in smy_df.iterrows():
            plan_area, office, branch_office, locality, *main_address = row.name  # type: ignore
            (
                summary.setdefault(plan_area, {})
                .setdefault(office, {})
                .setdefault(branch_office, {})
                .setdefault(locality, [])
            )
            if main_address:
                summary[plan_area][office][branch_office][locality].append(
                    main_address[0]
                )

        return summary
