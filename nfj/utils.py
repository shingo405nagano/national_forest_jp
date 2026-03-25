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
