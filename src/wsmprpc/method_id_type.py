from enum import IntEnum, unique

@unique
class RPCMethodIDType(IntEnum):
    STR = 1
    NUM = 2
    STR_NUM = 3
