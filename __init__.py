try:
    # pytest の収集時など、トップレベルモジュールとして読み込まれる場合に備える
    from nfj.geospatial import GsicAddressShape
except ImportError:  # pragma: no cover
    from .nfj.geospatial import GsicAddressShape

__all__ = ["GsicAddressShape"]
