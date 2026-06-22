from typing import Any, Optional

import geopandas as gpd
import pydantic
import shapely
from ezdxf.enums import InsertUnits
from ezdxf.layouts.layout import Modelspace


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
    label_size: int = 15
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

    Example:
        ```python
        import ezdxf
        from nfj.dxf import SubAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        sub_addrs_dxf = SubAddrsDxf(gdf=gdf)
        sub_addrs_dxf.add_geometries(modelspace)
        doc.saveas("sub_addrs.dxf")
        ```
    """

    protected_forest: bool = True

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
    ) -> None:
        """
        小班区画だけは、小班名
        """
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
    label_column: Optional[str] = "protection_forests"
    label_size: int = 20
    label_layer: str = "保安林区画ラベルレイヤー"
