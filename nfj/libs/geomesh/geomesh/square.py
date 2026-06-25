from typing import Optional

import geopandas as gpd
import shapely

from .data import Bounds

global DIGITS
DIGITS = 10**10


def create_square_from_length(
    x_min: float,  #
    y_max: float,
    horizontal: float,
    vertical: Optional[float] = None,
) -> Bounds:
    """
    ## Summary:
        指定した左上の座標と辺の長さから四角形の頂点座標を計算する関数
    Args:
        x_min (float):
            四角形の左上のx座標
        y_max (float):
            四角形の左上のy座標
        horizontal (float):
            水平辺の長さ(メートル)
        vertical (float, optional):
            垂直辺の長さ(メートル)
    Returns:
        Bounds:
            四角形のバウンディングボックスを格納したBoundsオブジェクト
    """
    if vertical is None:
        vertical = horizontal

    x_max = x_min + horizontal
    y_min = y_max - vertical

    return Bounds(x_min, y_min, x_max, y_max)


def create_square_from_area(
    x_min: float,  #
    y_max: float,
    area: float,
) -> Bounds:
    """
    ## Summary:
        指定した左上の座標と面積から正四角形の頂点座標を計算する関数
    Args:
        x_min (float):
            四角形の左上のx座標
        y_max (float):
            四角形の左上のy座標
        area (float):
            四角形の面積(平方メートル)
    Returns:
        Bounds:
            四角形のバウンディングボックスを格納したBoundsオブジェクト
    """
    side_length = area**0.5
    x_max = x_min + side_length
    y_min = y_max - side_length

    return Bounds(x_min, y_min, x_max, y_max)


class SquareMesh(object):
    """
    ## Summary:
        四角形メッシュを生成するクラス。面積や辺の長さを指定してメッシュを生成できる。
        面積や辺の長さをヘクタールやキロメートルで指定したい場合は、範囲の座標を経緯度ではなく
        平面直角座標系などのメートル単位の座標で指定する事。
    Args:
        x_min (float):
            メッシュ生成範囲の最小x座標
        y_min (float):
            メッシュ生成範囲の最小y座標
        x_max (float):
            メッシュ生成範囲の最大x座標
        y_max (float):
            メッシュ生成範囲の最大y座標
    """

    def __init__(
        self,  #
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
    ):
        self.bounds = Bounds(x_min, y_min, x_max, y_max)

    def create_square_from_length(
        self,
        x_min: float,
        y_max: float,
        horizontal: float,
        vertical: Optional[float] = None,
    ) -> Bounds:
        """
        ## Summary:
            指定した左上の座標と辺の長さから四角形の頂点座標を計算する関数
        Args:
            x_min (float):
                四角形の左上のx座標
            y_max (float):
                四角形の左上のy座標
            horizontal (float):
                水平辺の長さ(メートル)
            vertical (float, optional):
                垂直辺の長さ(メートル)
        Returns:
            Bounds:
                四角形のバウンディングボックスを格納したBoundsオブジェクト
        """
        return create_square_from_length(x_min, y_max, horizontal, vertical)

    def create_square_from_area(
        self,
        x_min: float,
        y_max: float,
        area: float,
    ) -> Bounds:
        """
        ## Summary:
            指定した左上の座標と面積から正四角形の頂点座標を計算する関数
        Args:
            x_min (float):
                四角形の左上のx座標
            y_max (float):
                四角形の左上のy座標
            area (float):
                四角形の面積(平方メートル)
        Returns:
            Bounds:
                四角形のバウンディングボックスを格納したBoundsオブジェクト
        """
        return create_square_from_area(x_min, y_max, area)

    def generate_squares_from_length(
        self,
        horizontal: float,
        vertical: Optional[float] = None,
    ) -> gpd.GeoDataFrame:
        """
        ## Summary:
            指定したバウンディングボックス内に四角形メッシュを生成する関数
        Args:
            horizontal (float):
                水平辺の長さ(メートル)
            vertical (float, optional):
                垂直辺の長さ(メートル)
        Returns:
            gpd.GeoDataFrame:
                生成された四角形メッシュを格納したGeoDataFrameオブジェクト。CRSは設定されて
                いない為、`crs`で必要に応じて設定すること。
        """
        if vertical is None:
            vertical = horizontal
        # 範囲のスケール変換
        x_min = int(self.bounds.x_min * DIGITS)
        y_max = int(self.bounds.y_max * DIGITS)
        x_max = int(self.bounds.x_max * DIGITS)
        y_min = int(self.bounds.y_min * DIGITS)
        horizontal = int(horizontal * DIGITS)
        vertical = int(vertical * DIGITS)
        # IDの初期化
        x_id, y_id = 0, 0
        ids = []
        squares = []
        for y in range(y_max, y_min, -vertical):
            for x in range(int(x_min), int(x_max), int(horizontal)):
                square = self.create_square_from_length(x, y, horizontal, vertical)
                # スケール変換
                square = Bounds(*[v / DIGITS for v in square])
                squares.append(square)
                ids.append(f"{x_id}/{y_id}")
                x_id += 1
            y_id += 1
            x_id = 0

        return gpd.GeoDataFrame(
            data={"id": list(range(len(squares))), "xy": ids},
            geometry=[shapely.box(*bounds) for bounds in squares],
        )

    def generate_squares_from_area(
        self,
        area: float,
    ) -> gpd.GeoDataFrame:
        """
        ## Summary:
            指定したバウンディングボックス内に四角形メッシュを生成する関数。
        Args:
            area (float):
                四角形の面積(平方メートル)
        Returns:
            gpd.GeoDataFrame:
                生成された四角形メッシュを格納したGeoDataFrameオブジェクト。CRSは設定されて
                いない為、`crs`で必要に応じて設定すること。
        """
        x_min = int(self.bounds.x_min * DIGITS)
        y_max = int(self.bounds.y_max * DIGITS)
        x_max = int(self.bounds.x_max * DIGITS)
        y_min = int(self.bounds.y_min * DIGITS)
        side_length = int(area**0.5 * DIGITS)
        x_id, y_id = 0, 0
        ids = []
        squares = []
        for y in range(y_max, y_min, -side_length):
            for x in range(x_min, x_max, side_length):
                square = self.create_square_from_length(x, y, side_length)
                square = Bounds(*[v / DIGITS for v in square])
                squares.append(square)
                ids.append(f"{x_id}/{y_id}")
                x_id += 1
            y_id += 1
            x_id = 0

        return gpd.GeoDataFrame(
            data={"id": list(range(len(squares))), "xy": ids},
            geometry=[shapely.box(*bounds) for bounds in squares],
        )
