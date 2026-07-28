import math
from functools import lru_cache
from importlib import resources
from typing import Any

import geopandas as gpd
import pydantic
import shapely
from ezdxf.enums import InsertUnits, TextEntityAlignment
from ezdxf.layouts.layout import Modelspace
from PIL import Image, ImageDraw, ImageFont

from .config import ProtectedForestCoding
from .fields import AddressFields
from .logging_config import setup_logger
from .utils import find_max_adjacent_cluster_center

logger = setup_logger(__name__)

global windows_font_path
windows_font_path = None


def _resolve_font_path() -> str:
    resource = resources.files("nfj").joinpath("others", "msgothic.ttc")
    if not resource.is_file():
        raise FileNotFoundError(f"Font resource not found: {resource}")
    return str(resource)


windows_font_path = _resolve_font_path()


def split_sub_address_name(sub_address_name: str) -> dict[str, str | None]:
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


def _compute_visual_offset_uncached(label, font_path, font_point_size, target_height):
    """
    指定したフォントで描画したときの文字列の視覚的中心を計算し、DXF座標系に変換する関数
    Args:
        label (str): 描画する文字列
        font_path (str): フォントファイルのパス
        font_point_size (float): フォントサイズ（ポイント）
        target_height (float): DXF座標系での目標高さ
    Returns:
        (offset_x, offset_y): DXF座標系での視覚的中心
    """
    # 高倍率レンダリング
    scale = 6
    font = ImageFont.truetype(font_path, int(font_point_size * scale))

    # キャンバスとベースライン
    canvas_w, canvas_h = 4000, 4000
    baseline_x = 1000
    baseline_y = 2000

    img = Image.new("L", (canvas_w, canvas_h), 0)
    draw = ImageDraw.Draw(img)

    # ascent を使ってベースラインに合わせて描画
    ascent, descent = font.getmetrics()
    draw_y = baseline_y - ascent
    draw.text((baseline_x, draw_y), label, font=font, fill=255)

    # 文字の見た目の中心を、描画されたピクセルの重心として求める
    pixels = img.load()
    count = 0
    sum_x = 0.0
    sum_y = 0.0
    for y in range(canvas_h):
        for x in range(canvas_w):
            if pixels[x, y] > 0:  # type: ignore
                count += 1
                sum_x += x
                sum_y += y

    if count == 0:
        return 0.0, 0.0

    center_x_px = sum_x / count
    center_y_px = sum_y / count

    # ベースライン原点に対する相対座標（Pillow の Y は下向き）
    rel_x_px = center_x_px - baseline_x
    rel_y_px = baseline_y - center_y_px

    # rendered height を ascent に基づいてスケール（より安定）
    rendered_ascent_px = ascent  # already scaled by 'scale'
    if rendered_ascent_px == 0:
        return 0.0, 0.0
    scale_to_dxf = target_height / rendered_ascent_px

    offset_x_dxf = rel_x_px * scale_to_dxf
    offset_y_dxf = rel_y_px * scale_to_dxf

    return offset_x_dxf, offset_y_dxf


@lru_cache(maxsize=2048)
def compute_visual_offset(label, font_path, font_point_size, target_height):
    return _compute_visual_offset_uncached(
        label, font_path, font_point_size, target_height
    )


def _rotate_point(
    x: float, y: float, center_x: float, center_y: float, angle_deg: float
):
    if abs(angle_deg) < 1e-12:
        return x, y
    angle_rad = math.radians(angle_deg)
    dx = x - center_x
    dy = y - center_y
    return (
        center_x + dx * math.cos(angle_rad) - dy * math.sin(angle_rad),
        center_y + dx * math.sin(angle_rad) + dy * math.cos(angle_rad),
    )


def _add_text_entity(
    msp, text: str, x: float, y: float, height: float, rotation: float = 0
):
    if not text:
        return None
    text_entity = msp.add_text(
        text,
        dxfattribs={
            "height": height,
            "rotation": rotation,
            "style": "STANDARD",
        },
    )
    try:
        # Use centered placement when available
        text_entity.set_pos((x, y), align="MIDDLE_CENTER")
    except Exception:
        # Fallback: set insert point
        text_entity.dxf.insert = (x, y)
    return text_entity


def add_sub_address_label(
    msp,
    x: float,
    y: float,
    addrs_label: str,
    addrs_label_size: float = 20,
    rotation: float = 0,
    number_label: str = "",
    number_label_scale: float = 0.5,
    protection_labels: list[str] | None = None,
    protection_label_scale: float = 0.5,
    font_path: str = windows_font_path,
):
    """DXFのモデル空間に林小班ラベルを追加する関数。

    Args:
        msp: DXFのモデル空間オブジェクト。
        x (float):
            ラベルのX座標。
        y (float):
            ラベルのY座標。
        addrs_label (str):
            小班主番ラベル。
            例：'い'、'ろ'、'は'、'イ' など
        addrs_label_size (float, optional):
            林小班ラベルのフォントサイズ。デフォルトは20
        rotation (float, optional):
            ラベル全体の回転角度（度単位）。デフォルトは0
        number_label (str, optional):
            小班枝番ラベルの文字列。デフォルトは空文字。このラベルは小班主番ラベルの右下に配置されます。
            例：'1'、'2'、'3'、'10' など
        number_label_scale (float, optional):
            小班枝番ラベルのスケール。デフォルトは0.5。
        protection_labels (list[str], optional):
            保安林種のラベルのリスト。このラベルは小班主番ラベルの真下に配置されます。複数ある場合は、
            左から右に配置されます。また、文字を囲むように円が描かれます。デフォルトは空リスト。
            例：['水', '土', '崩'] など
        protection_label_scale (float, optional):
            保安林種ラベルのスケール。デフォルトは0.5。
    """

    if protection_labels is None:
        protection_labels = []
    # main label
    _add_text_entity(msp, addrs_label, x, y, addrs_label_size, rotation)

    # number (枝番): place to the right/top-right of the main label
    if number_label:
        number_local_x = addrs_label_size * 1.3
        number_local_y = -addrs_label_size * 0.2
        number_x, number_y = _rotate_point(
            x + number_local_x,
            y + number_local_y,
            x,
            y,
            rotation,
        )
        num_ent = msp.add_text(
            number_label,
            dxfattribs={
                "height": addrs_label_size * number_label_scale,
                "rotation": rotation,
                "style": "STANDARD",
            },
        )
        try:
            num_ent.set_pos((number_x, number_y), align="BOTTOM_RIGHT")
        except Exception:
            num_ent.dxf.insert = (number_x, number_y)

    # protection labels: draw circles and center the text inside
    if protection_labels:
        spacing = addrs_label_size * 0.9
        total_width = (len(protection_labels) - 1) * spacing
        start_x = x + total_width * 0.85
        circle_radius = addrs_label_size * 0.9 * protection_label_scale

        for index, label in enumerate(protection_labels):
            px = start_x + index * spacing
            py = y - addrs_label_size * 0.7
            circle_center_x, circle_center_y = _rotate_point(px, py, x, y, rotation)

            # 文字ラベルは円の中心に完全に合わせて配置する。
            # 文字の実際の見た目の中央に合わせるため、フォントの描画バウンディングボックスを使う。
            text_center_x = circle_center_x
            text_center_y = circle_center_y

            msp.add_circle((circle_center_x, circle_center_y), circle_radius)
            th = addrs_label_size * protection_label_scale
            t_ent = msp.add_text(
                label,
                dxfattribs={
                    "height": th,
                    "rotation": rotation,
                    "style": "STANDARD",
                },
            )
            if font_path:
                offset_x, offset_y = compute_visual_offset(label, font_path, th, th)
                text_center_x, text_center_y = _rotate_point(
                    circle_center_x - offset_x,
                    circle_center_y - offset_y,
                    circle_center_x,
                    circle_center_y,
                    rotation,
                )
            try:
                t_ent.set_placement(
                    (text_center_x, text_center_y),
                    align=TextEntityAlignment.MIDDLE_CENTER,
                )
            except Exception:
                t_ent.dxf.insert = (text_center_x, text_center_y)


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

    gdf: gpd.GeoDataFrame | None = None
    geometry_column: str = "geometry"
    geometry_layer: str = "小班区画レイヤー"
    label_column: str | None = "sub_address_name"
    label_size: int = 20
    label_rotation: int = 0
    label_layer: str = "小班区画ラベルレイヤー"
    find_label_position: bool = False
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
        label: str | None = None,
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
            if self.find_label_position:
                centroid = find_max_adjacent_cluster_center(geom)
            else:
                centroid = shapely.point_on_surface(geom)

            modelspace.add_text(
                label,
                dxfattribs=self.label_dxf_attributes(),
                rotation=self.label_rotation,
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
        if self.gdf is None:
            msg = "gdf must be provided to add geometries."
            logger.error(msg)
            raise ValueError(msg)

        # ジオメトリとラベルの取り出し
        geoms = self.gdf[self.geometry_column].to_list()
        if self.label_column is not None:
            if self.label_column in self.gdf.columns:
                labels = self.gdf[self.label_column].to_list()
            else:
                msg = f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                logger.error(msg)
                raise ValueError(msg)
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

    label_size: int = 15
    protection_forest_mark: bool = True
    find_label_position: bool = True

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: str | None = None,
        marks: list[str] | None = None,
    ) -> None:
        exterior_coords = list(geom.exterior.coords)
        modelspace.add_lwpolyline(
            exterior_coords,
            close=True,
            dxfattribs=self.geometry_dxf_attributes(),
        )

        if geom.interiors:
            for interior in geom.interiors:
                interior_coords = list(interior.coords)
                modelspace.add_lwpolyline(
                    interior_coords,
                    close=True,
                    dxfattribs=self.geometry_dxf_attributes(),
                )

        if label is not None:
            # ラベルがある場合、Polygonと交差する点を取得してテキストを追加
            if self.find_label_position:
                centroid = find_max_adjacent_cluster_center(geom)
            else:
                centroid = shapely.point_on_surface(geom)
            splited = split_sub_address_name(label)
            kana = splited["kana"]
            number = splited["number"]
            add_sub_address_label(
                modelspace,
                centroid.x,
                centroid.y,
                addrs_label=kana if kana is not None else "",
                addrs_label_size=self.label_size,
                rotation=self.label_rotation,
                number_label=number if number is not None else "",
                number_label_scale=0.5,
                protection_labels=marks if marks is not None else [],
                protection_label_scale=0.5,
            )

    def protection_marks(self) -> dict[int, list[str] | None] | None:
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
        if self.gdf is None:
            msg = "gdf must be provided to add geometries."
            logger.error(msg)
            raise ValueError(msg)

        if self.label_column is not None:
            if self.label_column not in self.gdf.columns:
                msg = f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                logger.error(msg)
                raise ValueError(msg)

        marks_by_index = (
            self.protection_marks() if self.protection_forest_mark else None
        )

        for idx, row in self.gdf.iterrows():
            geom = row[self.geometry_column]
            label = row[self.label_column] if self.label_column is not None else None
            marks = marks_by_index.get(idx) if marks_by_index is not None else None  # type: ignore

            if geom.geom_type == "Polygon":
                self._add_geometry(modelspace, geom, label, marks)

            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    self._add_geometry(modelspace, poly, label, marks)


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
    label_column: str | None = "main_address"
    label_size: int = 40
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
    label_column: str | None = "locality"
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
    label_column: str | None = "branch_office"
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
    label_column: str | None = "office"
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
    label_column: str | None = "protected_forest_type"
    label_size: int = 20
    label_layer: str = "保安林区画ラベルレイヤー"
