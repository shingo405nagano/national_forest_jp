from enum import Enum


class OutputDtype(Enum):
    STRING = 0
    BYTES = 1
    DICT = 2


if __name__ == "__main__":
    od = 0
    if od == OutputDtype.STRING:
        print(True)
    else:
        print(False)
