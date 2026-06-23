from typing import Any, Optional

import geopandas as gpd
import pydantic
import shapely
from ezdxf.enums import InsertUnits
from ezdxf.layouts.layout import Modelspace

from .config import ProtectedForestCoding
from .fields import AddressFields


def split_sub_address_name(sub_address_name: str) -> dict[str, Optional[str]]:
    """
    小班名の文字列を分解し、ひらがな＆カタカナの部分と数字の部分に分ける関数
    Args:
        sub_address_name (str):
            小班名の文字列
    Returns:
        dict[str, Optional[str]]:
            ひらがな＆カタカナの部分と数字の部分を格納した辞書を返す
    ## Samples:
        - "わ" -> {"kana": "わ", "number": None}
        - "わ1" -> {"kana": "わ", "number": "1"}
    """
    # ひらがな＆カタカナの部分を抽出
    kana_part = "".join([c for c in sub_address_name if c.isalpha()])
    # 数字の部分を抽出
    number_part = "".join([c for c in sub_address_name if c.isdigit()])
    return {"kana": kana_part, "number": number_part if number_part else None}


class BaseDxf(pydantic.BaseModel):
    """DXFファイルに変換する際のオプションを定義するクラスです。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "小班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "sub_address_name"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "小班区画ラベルレイヤー"。
    """

    gdf: Optional[gpd.GeoDataFrame] = None
    geometry_column: str = "geometry"
    geometry_layer: str = "小班区画レイヤー"
    label_column: Optional[str] = "sub_address_name"
    label_size: int = 25
    label_layer: str = "小班区画ラベルレイヤー"
    model_config = pydantic.ConfigDict(
        validate_default=True,
        arbitrary_types_allowed=True,
    )

    @staticmethod
    def dxf_versions() -> list[str]:
        """サポートされているDXFのバージョンを返します。"""
        return ["R12", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018"]

    @staticmethod
    def dxf_units() -> list[InsertUnits]:
        """サポートされているDXFの単位を返します。"""
        return [
            InsertUnits.Unitless,
            InsertUnits.Millimeters,
            InsertUnits.Centimeters,
            InsertUnits.Meters,
            InsertUnits.Kilometers,
        ]

    def geometry_dxf_attributes(self) -> dict[str, Any]:
        return {
            "layer": self.geometry_layer,
        }

    def label_dxf_attributes(self) -> dict[str, Any]:
        return {
            "height": self.label_size,
            "layer": self.label_layer,
        }

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
    ) -> None:
        # 外周の座標を取得し、座標をDXFのLWPolylineとして追加
        exterior_coords = list(geom.exterior.coords)
        modelspace.add_lwpolyline(
            exterior_coords,
            close=True,
            dxfattribs=self.geometry_dxf_attributes(),
        )
        if label is not None:
            # ラベルがある場合、Polygonと交差する点を取得してテキストを追加
            centroid = shapely.point_on_surface(geom)
            modelspace.add_text(
                label, dxfattribs=self.label_dxf_attributes()
            ).set_placement((centroid.x, centroid.y))
        # Polygonに内周がある場合、内周の座標もDXFのLWPolylineとして追加
        if geom.interiors:
            for interior in geom.interiors:
                interior_coords = list(interior.coords)
                modelspace.add_lwpolyline(
                    interior_coords,
                    close=True,
                    dxfattribs=self.geometry_dxf_attributes(),
                )

    def add_geometries(
        self,
        modelspace: Modelspace,
    ) -> None:
        # ジオメトリとラベルの取り出し
        geoms = self.gdf[self.geometry_column].to_list()
        if self.label_column is not None:
            if self.label_column in self.gdf.columns:
                labels = self.gdf[self.label_column].to_list()
            else:
                raise ValueError(
                    f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                )
        else:
            labels = None

        for i, geom in enumerate(geoms):
            if geom.geom_type == "Polygon":
                # 外周の座標を取得し、座標をDXFのLWPolylineとして追加
                self._add_geometry(
                    modelspace, geom, labels[i] if labels is not None else None
                )

            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    self._add_geometry(
                        modelspace, poly, labels[i] if labels is not None else None
                    )


class SubAddrsDxf(BaseDxf):
    """小班区画のDXFファイルに変換する際のオプションを定義するクラスです。
    小班区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        version(str, optional):
            DXFのバージョン。デフォルトは "R2013"。他には "R12", "R2000", "R2004",
            "R2007", "R2010", "R2018" が使用可能です。
        unit(InsertUnits, optional):
            DXFの単位。デフォルトは InsertUnits.Meters。InsertUnits.Unitless,
            InsertUnits.Millimeters, InsertUnits.Centimeters, InsertUnits.Kilometers
            も使用可能です。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "小班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "sub_address_name"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "小班区画ラベルレイヤー"。
        protection_forest_mark(bool, optional):
            保安林の短縮コードを円囲みで描画するかどうか。デフォルトは True。
        protection_mark_layer(str, optional):
            保安林の短縮コードを描画するレイヤー名。デフォルトは "保安林コードレイヤー"。
        protection_mark_circle_layer(str, optional):
            保安林の短縮コードを円囲みで描画するレイヤー名。デフォルトは "保安林コード円レイヤー"。
        protection_mark_offset_x_factor(float, optional):
            保安林の短縮コードを円囲みで描画する際の、円の中心と文字の左下のX方向のオフセット係数。デフォルトは 0.6。
        protection_mark_offset_y_factor(float, optional):
            保安林の短縮コードを円囲みで描画する際の、円の中心と文字の左下のY方向のオフセット係数。デフォルトは 0.4。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import SubAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        sub_addrs_dxf = SubAddrsDxf(gdf=gdf, protection_forest_mark=True)
        sub_addrs_dxf.add_geometries(modelspace)
        doc.saveas("sub_addrs.dxf")
        ```
    """

    protection_forest_mark: bool = True
    protection_mark_layer: str = "保安林コードレイヤー"
    protection_mark_circle_layer: str = "保安林コード円レイヤー"
    protection_mark_offset_x_factor: float = 0.5
    protection_mark_offset_y_factor: float = 0.4

    def protection_mark_dxf_attributes(self) -> dict[str, Any]:
        return {
            "height": self.label_size * 0.6,
            "layer": self.protection_mark_layer,
        }

    def protection_mark_circle_dxf_attributes(self) -> dict[str, Any]:
        return {
            "layer": self.protection_mark_circle_layer,
        }

    def _add_label_text(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
    ) -> None:
        if label is None:
            return

        parts = split_sub_address_name(label)
        centroid = shapely.point_on_surface(geom)

        if parts["kana"]:
            modelspace.add_text(
                parts["kana"],
                dxfattribs=self.label_dxf_attributes(),
            ).set_placement((centroid.x, centroid.y))

        if parts["number"] is not None:
            number_attributes = self.label_dxf_attributes()
            number_attributes["height"] = self.label_size * 0.6
            number_offset_x = self.label_size * 1.4
            modelspace.add_text(
                parts["number"],
                dxfattribs=number_attributes,
            ).set_placement((centroid.x + number_offset_x, centroid.y))

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
    ) -> None:
        exterior_coords = list(geom.exterior.coords)
        modelspace.add_lwpolyline(
            exterior_coords,
            close=True,
            dxfattribs=self.geometry_dxf_attributes(),
        )
        if label is not None:
            self._add_label_text(modelspace, geom, label)

        if geom.interiors:
            for interior in geom.interiors:
                interior_coords = list(interior.coords)
                modelspace.add_lwpolyline(
                    interior_coords,
                    close=True,
                    dxfattribs=self.geometry_dxf_attributes(),
                )

    def _add_protection_marks(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        marks: Optional[list[str]],
    ) -> None:
        """保安林の短縮コードを、重ならないように円囲みで描画します。"""
        if not marks:
            return

        marker_size = self.label_size * 0.7

        base = shapely.point_on_surface(geom)
        radius = marker_size * 0.75
        spacing = radius * 2.5

        # 小班名ラベルとの重なりを避けるため、中心点より下側に保安林コードを配置する
        start_x = base.x - (spacing * (len(marks) - 1) / 2)
        center_y = base.y - (marker_size * 1.8) + spacing * 0.2

        for i, mark in enumerate(marks):
            center_x = start_x + spacing * i + spacing * 0.5
            center = (center_x, center_y)
            # 円は文字の左下に書かれてしまう為、中心点を円の中心にするために、円の中心と文字の左下が重なるように配置する
            circle_center_x = center_x + (
                marker_size * self.protection_mark_offset_x_factor
            )
            circle_center_y = center_y + (
                marker_size * self.protection_mark_offset_y_factor
            )
            circle_center = (circle_center_x, circle_center_y)
            modelspace.add_circle(
                circle_center,
                radius,
                dxfattribs=self.protection_mark_circle_dxf_attributes(),
            )
            modelspace.add_text(
                mark,
                dxfattribs=self.protection_mark_dxf_attributes(),
            ).set_placement(center)

    def protection_marks(self) -> Optional[dict[int, Optional[list[str]]]]:
        """
        小班区画に保安林が含まれている場合、保安林の種別に応じた短縮コードをリスト化して返します。
        保安林が含まれていない場合は None を返します。
        """
        pf_coding = ProtectedForestCoding()

        if self.protection_forest_mark:
            if not isinstance(self.gdf, gpd.GeoDataFrame):
                # GeoDataFrameでない場合はエラーを返す
                raise ValueError(
                    "gdf must be a GeoDataFrame to calculate protection marks."
                )

            # 保安林の要素が含まれているカラムを取得
            addrs_fields = AddressFields()
            pf_cols = [
                field.en
                for field in addrs_fields.fields.values()
                if "protection_forest" in field.en
            ]
            # 保安林の種別に応じた短縮コードをリスト化して返す
            marks = {}
            for idx, row in self.gdf.iterrows():
                pfs = [pf for pf in row[pf_cols].tolist() if "-" != pf]
                if len(pfs) == 0:
                    marks[idx] = None
                else:
                    codes = []
                    for pf in pfs:
                        code = pf_coding.mark(pf)
                        if code is not None:
                            codes.append(code)
                    marks[idx] = codes if len(codes) > 0 else None
            return marks
        else:
            return None

    def add_geometries(
        self,
        modelspace: Modelspace,
    ) -> None:
        # ジオメトリとラベルの取り出し
        if self.label_column is not None:
            if self.label_column not in self.gdf.columns:
                raise ValueError(
                    f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                )

        marks_by_index = (
            self.protection_marks() if self.protection_forest_mark else None
        )

        for idx, row in self.gdf.iterrows():
            geom = row[self.geometry_column]
            label = row[self.label_column] if self.label_column is not None else None
            marks = marks_by_index.get(idx) if marks_by_index is not None else None

            if geom.geom_type == "Polygon":
                self._add_geometry(modelspace, geom, label)
                self._add_protection_marks(modelspace, geom, marks)

            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    self._add_geometry(modelspace, poly, label)
                    self._add_protection_marks(modelspace, poly, marks)


class MainAddrsDxf(BaseDxf):
    """林班区画のDXFファイルに変換する際のオプションを定義するクラスです。
    林班区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。
    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "林班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "main_address"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 50。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "林班区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import MainAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        main_addrs_dxf = MainAddrsDxf(gdf=gdf)
        main_addrs_dxf.add_geometries(modelspace)
        doc.saveas("main_addrs.dxf")
        ```
    """

    geometry_layer: str = "林班区画レイヤー"
    label_column: Optional[str] = "main_address"
    label_size: int = 35
    label_layer: str = "林班区画ラベルレイヤー"


class LocalityDxf(BaseDxf):
    """国有林区画のDXFファイルに変換する際のオプションを定義するクラスです。
    国有林区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "国有林区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "locality"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 70。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "国有林名ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import LocalityAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        locality_dxf = LocalityDxf(gdf=gdf)
        locality_dxf.add_geometries(modelspace)
        doc.saveas("locality.dxf")
        ```
    """

    geometry_layer: str = "国有林区画レイヤー"
    label_column: Optional[str] = "locality"
    label_size: int = 50
    label_layer: str = "国有林名ラベルレイヤー"


class BranchOfficeDxf(BaseDxf):
    """森林事務所（担当区）のDXFファイルに変換する際のオプションを定義するクラスです。
    森林事務所（担当区）のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "森林事務所区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "branch_office"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 100。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "森林事務所区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import BranchOfficeAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        branch_office_dxf = BranchOfficeDxf(gdf=gdf)
        branch_office_dxf.add_geometries(modelspace)
        doc.saveas("branch_office.dxf")
        ```
    """

    geometry_layer: str = "森林事務所レイヤー"
    label_column: Optional[str] = "branch_office"
    label_size: int = 70
    label_layer: str = "森林事務所区画ラベルレイヤー"


class OfficeDxf(BaseDxf):
    """森林管理署のDXFファイルに変換する際のオプションを定義するクラスです。
    森林管理署のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "森林管理署区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "office"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 120。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "森林管理署区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import OfficeAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        office_dxf = OfficeDxf(gdf=gdf)
        office_dxf.add_geometries(modelspace)
        doc.saveas("office.dxf")
        ```
    """

    geometry_layer: str = "森林管理署レイヤー"
    label_column: Optional[str] = "office"
    label_size: int = 90
    label_layer: str = "森林管理署区画ラベルレイヤー"


class ProtectionForestDxf(BaseDxf):
    """保安林のDXFファイルに変換する際のオプションを定義するクラスです。
    保安林のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "保安林区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "protection_forests"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "保安林区画ラベルレイヤー"。
    Example:
        ```python
        import ezdxf
        from nfj.dxf import ProtectionForestDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        protection_forest_dxf = ProtectionForestDxf(gdf=gdf)
        protection_forest_dxf.add_geometries(modelspace)
        doc.saveas("protection_forest.dxf")
        ```
    """

    geometry_layer: str = "保安林区画レイヤー"
    label_column: Optional[str] = "protected_forest_type"
    label_size: int = 20
    label_layer: str = "保安林区画ラベルレイヤー"
