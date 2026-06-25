from decimal import Decimal
from typing import Any

import pyproj


def _intermediate(arg_index, kward, *args, **kwargs) -> dict[str, Any]:
    """
    ## Summary:
        引数が args にあるか kwargs にあるかを判定するヘルパー関数。
    ## Args:
        arg_index (int):
            位置引数のインデックス。
        kward (str):
            キーワード引数の名前。
        *args:
            可変長引数リスト。
        **kwargs:
            任意のキーワード引数。
    ## Returns:
        dict:
            辞書型で、引数が args にあるかどうかとその値を含む。
            "in_args" (bool): 引数が args にある場合は True、kwargs にある場合は False。
            "value" (Any): 引数の値。引数が存在しない場合（デフォルト値を使用）は None。
    """
    in_args = True
    value = None
    if arg_index < len(args):
        value = args[arg_index]
    else:
        in_args = False
        # デフォルト引数を使用している場合はkwargsに存在しない可能性がある
        value = kwargs.get(kward, None)
    return {"in_args": in_args, "value": value}


def _return_value(value: Any, data: dict[str, Any], args, kwargs) -> Any:
    """
    ## Summary:
        Helper function to return the modified args and kwargs after type checking.
    ## Args:
        value (Any):
            The value to be set in args or kwargs.
        data (dict[str, Any]):
            The data containing information about the argument index and keyword.
        *args:
            Variable length argument list.
        **kwargs:
            Arbitrary keyword arguments.
    ## Returns:
        dict:
            A dictionary containing the modified args and kwargs.
    """
    if data["in_args"]:
        args = list(args)
        args[data["arg_index"]] = value
    else:
        kwargs[data["kward"]] = value
    return {"args": args, "kwargs": kwargs}


def type_checker_float(arg_index: int, kward: str):
    """
    ## Summary:
        引数が浮動小数点数か浮動小数点数に変換可能かをチェックするデコレーター。
    ## Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
    ## Returns:
        float:
            浮動小数点数に変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            try:
                value = float(value)
            except Exception as e:
                raise TypeError(
                    f"Argument '{kward}' must be a float or convertible to float"
                    f", got {type(value)}"
                ) from e
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator


def type_checker_integer(arg_index: int, kward: str):
    """
    ## Summary:
        関数の引数が整数か、整数に変換可能かをチェックするデコレーター。
    ## Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
    ## Returns:
        int:
            整数に変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            try:
                value = int(value)
            except Exception as e:
                raise TypeError(
                    f"Argument '{kward}' must be an integer or convertible to "
                    f"integer, got {type(value)}"
                ) from e
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator


def type_checker_decimal(arg_index: int, kward: str):
    """
    ## Summary:
        関数の引数がDecimalオブジェクトか、Decimalに変換可能な値かをチェックするデコレーター。
        Decimalは浮動小数点数の精度を保つために使用されます。
    ## Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
    ## Returns:
        float:
            Decimalに変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            if isinstance(value, Decimal):
                return func(*args, **kwargs)
            try:
                value = Decimal(f"{float(value)}")
            except Exception as e:
                raise TypeError(
                    f"Argument '{kward}' must be a decimal or convertible to "
                    "decimal, got {type(value)}"
                ) from e
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator


def type_checker_crs(arg_index: int, kward: str):
    """
    ## Summary:
        関数の引数がpyproj.CRSオブジェクトか、CRSに変換可能な文字列かをチェックするデコレーター。
    ## Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
    ## Returns:
        pyproj.CRS:
            CRSオブジェクトに変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            # デフォルト引数を使用している場合（valueがNone）はそのまま関数を呼び出す
            if value is None:
                return func(*args, **kwargs)
            if isinstance(value, pyproj.CRS):
                return func(*args, **kwargs)
            try:
                if isinstance(value, str):
                    value = pyproj.CRS(value)
                else:
                    value = pyproj.CRS.from_epsg(value)
            except Exception as e:
                raise TypeError(
                    f"Argument '{kward}' must be a CRS or convertible to CRS, got {type(value)}"
                ) from e
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator


def type_checker_zoom_level(
    arg_index: int, kward: str, min_zl: int = 0, max_zl: int = 24
):
    """
    ## Summary:
        関数の引数がズームレベルを表す整数か、整数に変換可能かをチェックするデコレーター。
    ## Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
        min_zl (int):
            ズームレベルの最小値。デフォルトは0。
        max_zl (int):
            ズームレベルの最大値。デフォルトは24。
    ## Returns:
        int:
            ズームレベルに変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            try:
                value = int(value)
                if not (min_zl <= value <= max_zl):
                    raise ValueError(
                        f"Zoom level must be between {min_zl} and {max_zl}, got {value}"
                    )
            except Exception as e:
                raise TypeError(
                    f"Argument '{kward}' must be an integer or convertible to integer, got {type(value)}"
                ) from e
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator


def valid_names(arg_index: int, kward: str, valid_names: list[str]):
    """
    ## Summary:
        関数の引数が指定された有効な名前のリストに含まれているかをチェックするデコレーター。
    Args:
        arg_index (int):
            位置引数のインデックスを指定。
        kward (str):
            キーワード引数の名前を指定。
        valid_names (list[str]):
            有効な名前のリスト。
    Returns:
        str:
            有効な名前に変換された引数の値。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            data = _intermediate(arg_index, kward, *args, **kwargs)
            data["arg_index"] = arg_index
            data["kward"] = kward
            value = data["value"]
            if value not in valid_names:
                raise ValueError(
                    f"Argument '{kward}' must be one of {valid_names}, got '{value}'"
                )
            else:
                result = _return_value(value, data, args, kwargs)
                return func(*result["args"], **result["kwargs"])

        return wrapper

    return decorator
