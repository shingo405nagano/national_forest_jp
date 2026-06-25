import os

import pandas as pd
import shapely

global PREF_PNT_CSV
PREF_PNT_CSV = os.path.join(os.path.dirname(__file__), "data", "pref_pnt.csv")


class TestDataSets(object):
    def __init__(self):
        pref_pnt_df = pd.read_csv(PREF_PNT_CSV)
        pref_pnt_df["q_mesh_code"] = pref_pnt_df["q_mesh_code"].astype(str)
        self.pref_points_df = pref_pnt_df

    @property
    def pref_points(self) -> pd.DataFrame:
        """
        ## Summary:
            都道府県庁所在地データ
        Returns:
            pd.DataFrame: 都道府県庁所在地のデータフレーム
        ## DataFrame:
            prefecture,lon,lat,q_mesh_code
            (str), (float), (float), (str)
            北海道,141.3469,43.0643,6441427742
            青森県,140.7406,40.8246,6140158933
            岩手県,141.1527,39.7036,5941414213
            宮城県,140.8719,38.2688,5740362924
            秋田県,140.1024,39.7186,5940406811
            山形県,140.3633,38.2404,5740228933
            福島県,140.4676,37.7503,5640530712
        """
        return self.pref_points_df

    def get_pref_point(self, prefecture_name: str) -> shapely.Point:
        """
        ## Summary:
            指定した都道府県名に対応する都道府県庁所在地データを取得
        Args:
            prefecture_name (str):
                都道府県名
        Returns:
            shapely.Point:
                指定した都道府県庁所在地のポイントデータ
        Raises:
            ValueError: 指定した都道府県名がデータに存在しない場合
        """
        result = self.pref_points_df[
            self.pref_points_df["prefecture"] == prefecture_name
        ]
        if result.empty:
            raise ValueError(
                f"指定した都道府県名 '{prefecture_name}' はデータに存在しません。"
            )
        return shapely.Point(result.iloc[0]["lon"], result.iloc[0]["lat"])

    def get_pref_mesh_code(self, prefecture_name: str, mesh_name: str) -> str:
        """
        ## Summary:
            指定した都道府県名に対応する都道府県庁所在地の第4次メッシュコードを取得
        Args:
            prefecture_name (str):
                都道府県名
            mesh_name (str):
                メッシュ名（"1st", "2nd", "standard", "half", "quarter"のいずれか）
        Returns:
            str:
                指定した都道府県庁所在地のメッシュコード
        Raises:
            ValueError: 指定した都道府県名がデータに存在しない場合
        """
        result = self.pref_points_df[
            self.pref_points_df["prefecture"] == prefecture_name
        ]
        if result.empty:
            raise ValueError(
                f"指定した都道府県名 '{prefecture_name}' はデータに存在しません。"
            )
        code = result.iloc[0]["q_mesh_code"]
        if mesh_name == "1st":
            return code[:4]
        elif mesh_name == "2nd":
            return code[:6]
        elif mesh_name == "standard":
            return code[:8]
        elif mesh_name == "half":
            return code[:9]
        elif mesh_name == "quarter":
            return code[:10]
        else:
            raise ValueError(
                f"無効なメッシュ名 '{mesh_name}' が指定されました。有効なメッシュ名は '1st', '2nd', 'standard', 'half', 'quarter' です。"
            )
