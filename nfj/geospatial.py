import datetime
import re
from typing import Any

import geopandas as gpd
import shapely

from .config import (  # noqa: F401
    AuthorityCoding,
    BranchOfficeCoding,
    CityCoding,
    ConservationCoding,
    ForestFeatureTypeCoding,
    ForestTypeDetailCoding,
    GreenCorridorCoding,
    LocalityCoding,
    OfficeCoding,
    PlanAreaCoding,
    ProtectedForestCoding,
    TreeNameCoding,
)
from .fetch import GsShapeFile
from .fields import FieldInfo, _AddrsColumns
from .utils import txt_normalizer


def convert_wareki_to_seireki(wareki: str) -> int:
    """和暦を西暦に変換する関数。

    Args:
        wareki: 和暦の文字列（例: "令和５年度樹立"）。

    Returns:
        西暦の整数（例: 2023）。
    """
    if not isinstance(wareki, str):
        return wareki
    wareki = txt_normalizer(wareki.strip()).replace("年度樹立", "").replace("元", "1")

    era_mapping = {
        "平成": 1989,
        "令和": 2019,
    }
    for era, start_year in era_mapping.items():
        if wareki.startswith(era):
            wy = int(re.findall(r"\d+", wareki)[0])
            return start_year + wy - 1
    raise ValueError(f"不明な和暦形式: {wareki}")


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
        addrs_cols = _AddrsColumns()
        # EsriShapefile を GeoDataFrame として読み込む
        gdf = self._read_file(plan_area=plan_area)
        # 樹立年度を西暦に変換する
        gdf["樹立年度"] = gdf["樹立年度"].apply(convert_wareki_to_seireki)
        # 更新年を記録
        gdf[addrs_cols.updated_year] = datetime.datetime.now().year
        gdf = self.__cast_geodataframe(gdf)
        org_columns = gdf.columns
        # 森林管理局名に”森林管理局”が含まれている場合は削除する
        gdf[addrs_cols.authority] = (
            gdf[addrs_cols.authority].str.replace("森林管理局", "").str.strip()
        )
        # 正規化が必要なカラムの値を正規化する（「市町村名」「担当区」「国有林名」）
        for col in [addrs_cols.city, addrs_cols.branch_office, addrs_cols.locality]:
            gdf[col] = gdf[col].apply(txt_normalizer)

        # 林小班名に余計な文字が含まれる為、削除してしまう
        gdf[addrs_cols.address] = gdf[addrs_cols.address].apply(self.__replace_address)
        # 重複する林小班が存在する場合は、1つにまとめる
        gdf = gdf.dissolve(
            by=[addrs_cols.office, addrs_cols.address], as_index=False, aggfunc="first"
        )
        # 樹齢を修正する
        for col in [
            addrs_cols.tree_age_1,
            addrs_cols.tree_age_2,
            addrs_cols.tree_age_3,
        ]:
            gdf[col] = gdf.apply(
                lambda row: self.__fix_tree_age(
                    row[addrs_cols.establishment_year], row[col]
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
            gdf[col] = gdf[col].fillna(field_info.default)
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
        return txt_normalizer(text.replace("_林班_", "").strip())

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

    def query(self, gdf: gpd.GeoDataFrame, **kwargs: Any) -> gpd.GeoDataFrame:
        """GeoDataFrame に対してクエリを実行するための関数。

        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。クエリの条件は、キーワード引数として指定されます。

        Args:
            gdf: クエリを実行する対象の GeoDataFrame。
            **kwargs: クエリの条件を指定するキーワード引数。

        Returns:
            クエリの条件に一致する行を含む GeoDataFrame。

        ## Kwargs:
            - plan_area: 森林計画区の名称でフィルタリングします
            - office: 森林管理署の名称でフィルタリングします
            - branch_office: 担当区の名称でフィルタリングします
            - locality: 国有林の所在地でフィルタリングします
            - main_address: 林班主番でフィルタリングします
            - city: 市町村名でフィルタリングします
        """
        self.__check_geodataframe(gdf)
        q = []
        if "plan_area" in kwargs:
            q.append(self.__make_query_string("plan_area", kwargs["plan_area"]))
        if "office" in kwargs:
            q.append(self.__make_query_string("office", kwargs["office"]))
        if "branch_office" in kwargs:
            q.append(self.__make_query_string("branch_office", kwargs["branch_office"]))
        if "locality" in kwargs:
            q.append(self.__make_query_string("locality", kwargs["locality"]))
        if "main_address" in kwargs:
            q.append(self.__make_query_string("main_address", kwargs["main_address"]))
        if "city" in kwargs:
            q.append(self.__make_query_string("city", kwargs["city"]))
        query_string = " and ".join(q)
        return gdf.query(query_string)

    def __make_query_string(self, column: str, value: str | int | list[Any]) -> str:
        """DataFrameのクエリ文字列を生成するための関数。SQLとは異なります。

        Args:
            column: クエリ対象のカラム名。
            value: クエリ条件の値。文字列、整数、またはそれらのリストで指定できます。

        Returns:
            クエリ文字列。
        """
        if isinstance(value, list):
            q = " or ".join([self.__make_query_string(column, v) for v in value])
            return q
        elif isinstance(value, str):
            return f"{column} == {repr(value)}"
        elif isinstance(value, int):
            return f"{column} == {value}"

    def __check_geodataframe(self, gdf: gpd.GeoDataFrame) -> None:
        """GeoDataFrame の内容をチェックするための関数。

        Args:
            gpd.GeoDataFrame: チェック対象の GeoDataFrame。

        Returns:
            なし。エラーがある場合は例外を発生させる。
        """
        assert set(gdf.columns) == set(self.fields.use_default_en_fields())
        assert gdf["geometry"].dtype.name == "geometry"

    def encode(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性をコード化します。

        ここで処理されるコード化は、'.confs/nf_coding.yaml' に定義されたものに基づいています。
        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。

        Args:
            gdf: コード化する GeoDataFrame。

        Returns:
            コード化された GeoDataFrame。
        """

        def _encode(gdf, col, coding, dtype):
            gdf[col] = gdf[col].apply(coding.encode).astype(dtype)
            return gdf

        self.__check_geodataframe(gdf)
        gdf = gdf.copy()
        cols = _AddrsColumns()
        city_coding = CityCoding()
        gdf = _encode(gdf, cols.city, city_coding, "int")
        authority_coding = AuthorityCoding()
        gdf = _encode(gdf, cols.authority, authority_coding, "int")
        plan_area_coding = PlanAreaCoding()
        gdf = _encode(gdf, cols.plan_area, plan_area_coding, "int")
        office_coding = OfficeCoding()
        gdf = _encode(gdf, cols.office, office_coding, "int")
        branch_office_coding = BranchOfficeCoding()
        gdf = _encode(gdf, cols.branch_office, branch_office_coding, "int")
        locality_coding = LocalityCoding()
        gdf = _encode(gdf, cols.locality, locality_coding, "int")
        tree_name_coding = TreeNameCoding()
        gdf = _encode(gdf, cols.tree_name_1, tree_name_coding, "int")
        gdf = _encode(gdf, cols.tree_name_2, tree_name_coding, "int")
        gdf = _encode(gdf, cols.tree_name_3, tree_name_coding, "int")
        ftd_coding = ForestTypeDetailCoding()
        gdf = _encode(gdf, cols.forest_type_detail, ftd_coding, "int")
        fft_coding = ForestFeatureTypeCoding()
        gdf = _encode(gdf, cols.forest_feature_type, fft_coding, "int")
        protected_coding = ProtectedForestCoding()
        gdf = _encode(gdf, cols.protection_forest_1, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_2, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_3, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_4, protected_coding, "int")
        conservation_coding = ConservationCoding()
        gdf = _encode(gdf, cols.conservation, conservation_coding, "int")
        green_corridor_coding = GreenCorridorCoding()
        gdf = _encode(gdf, cols.green_corridor, green_corridor_coding, "int")
        return gdf

    def decode(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性をコード化します。
        ここで処理されるコード化は、'.confs/nf_coding.yaml' に定義されたものに基づいています。
        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。

        Args:
            gdf: デコードする GeoDataFrame。

        Returns:
            デコードされた GeoDataFrame。
        """

        def _decode(gdf, col, coding, dtype):
            gdf[col] = gdf[col].apply(coding.decode).astype(dtype)
            return gdf

        self.__check_geodataframe(gdf)
        gdf = gdf.copy()
        cols = _AddrsColumns()
        city_coding = CityCoding()
        gdf = _decode(gdf, cols.city, city_coding, "str")
        authority_coding = AuthorityCoding()
        gdf = _decode(gdf, cols.authority, authority_coding, "str")
        plan_area_coding = PlanAreaCoding()
        gdf = _decode(gdf, cols.plan_area, plan_area_coding, "str")
        office_coding = OfficeCoding()
        gdf = _decode(gdf, cols.office, office_coding, "str")
        branch_office_coding = BranchOfficeCoding()
        gdf = _decode(gdf, cols.branch_office, branch_office_coding, "str")
        locality_coding = LocalityCoding()
        gdf = _decode(gdf, cols.locality, locality_coding, "str")
        tree_name_coding = TreeNameCoding()
        gdf = _decode(gdf, cols.tree_name_1, tree_name_coding, "str")
        gdf = _decode(gdf, cols.tree_name_2, tree_name_coding, "str")
        gdf = _decode(gdf, cols.tree_name_3, tree_name_coding, "str")
        ftd_coding = ForestTypeDetailCoding()
        gdf = _decode(gdf, cols.forest_type_detail, ftd_coding, "str")
        fft_coding = ForestFeatureTypeCoding()
        gdf = _decode(gdf, cols.forest_feature_type, fft_coding, "str")
        protected_coding = ProtectedForestCoding()
        gdf = _decode(gdf, cols.protection_forest_1, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_2, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_3, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_4, protected_coding, "str")
        conservation_coding = ConservationCoding()
        gdf = _decode(gdf, cols.conservation, conservation_coding, "str")
        green_corridor_coding = GreenCorridorCoding()
        gdf = _decode(gdf, cols.green_corridor, green_corridor_coding, "str")
        return gdf
