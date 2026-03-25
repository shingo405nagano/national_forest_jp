import regex as re


def txt_normalizer(txt):
    # 全角英数字 → 半角
    txt = txt.translate(
        str.maketrans(
            "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        )
    )

    txt = txt.replace("−", "-")
    txt = txt.replace(" ", "").replace("　", "")

    # 漢字の間にある「ケ」→「ヶ」
    txt = re.sub(r"(?<=\p{Han})ケ(?=\p{Han})", "ヶ", txt)

    return txt
