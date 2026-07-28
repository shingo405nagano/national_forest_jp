import regex as re
import shapely
from shapely.ops import unary_union


def txt_normalizer(txt):
    # 全角英数字 → 半角
    txt = txt.translate(
        str.maketrans(
            "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        )
    )

    txt = txt.replace("−", "-").replace("－", "-").replace("―", "-")
    txt = txt.replace(" ", "").replace("　", "")

    # 漢字の間にある「ケ」→「ヶ」
    txt = re.sub(r"(?<=\p{Han})ケ(?=\p{Han})", "ヶ", txt)

    return txt


def find_max_adjacent_cluster_center(
    poly: shapely.Polygon, cluster_size: int = 3
) -> shapely.Point:
    """
    指定した個数 cluster_size の隣接した三角形クラスターのうち、
    面積合計が最大となるものを貪欲法で近似的に探し、
    その union の centroid を返す。

    Args:
        poly (shapely.Polygon): 入力ポリゴン
        cluster_size (int): クラスターのサイズ（隣接三角形の個数）
    Returns:
        shapely.Point: 最大面積クラスターの centroid
    """

    # --- ドロネー三角形分割 & 内部三角形抽出 ---
    triangles = shapely.delaunay_triangles(poly)
    contains_triangle_list = []
    for triangle in shapely.get_parts(triangles):
        if shapely.get_type_id(triangle) == 3 and poly.contains(triangle):
            contains_triangle_list.append(triangle)

    if len(contains_triangle_list) == 0:
        return None

    # --- 隣接判定（辺共有：LineString かつ長さ > 0） ---
    def are_adjacent(tri_a, tri_b):
        inter = tri_a.boundary.intersection(tri_b.boundary)
        return inter.geom_type == "LineString" and inter.length > 0

    n = len(contains_triangle_list)

    # --- 隣接グラフ構築 ---
    adjacency = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if are_adjacent(contains_triangle_list[i], contains_triangle_list[j]):
                adjacency[i].append(j)
                adjacency[j].append(i)

    # --- 面積リスト ---
    areas = [tri.area for tri in contains_triangle_list]

    # --- 最大面積三角形からスタートして、隣接三角形を貪欲に追加 ---
    # cluster_size 個に達するまで、隣接ノードの中から面積が大きいものを順に選ぶ
    start_idx = max(range(n), key=lambda i: areas[i])
    cluster = {start_idx}
    frontier = set(adjacency[start_idx])

    while len(cluster) < cluster_size and frontier:
        # frontier の中で面積が最大のものを選ぶ
        next_idx = max(frontier, key=lambda i: areas[i])
        cluster.add(next_idx)
        # frontier 更新：新しく追加したノードの隣接ノードを追加
        for nei in adjacency[next_idx]:
            if nei not in cluster:
                frontier.add(nei)
        frontier.remove(next_idx)

    # frontier が尽きて cluster_size に満たない場合もありうる
    # その場合は「取りうる最大サイズのクラスター」として扱う
    merged = unary_union([contains_triangle_list[idx] for idx in cluster])
    return merged.centroid
