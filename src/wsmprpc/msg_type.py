from enum import IntEnum, unique

@unique
class RPCMsgType(IntEnum):
    NOTIFY = 1 # reserved
    REQUEST = 2
    RESPONSE = 3
    REQUEST_STREAM_CHUNCK = 4
    RESPONSE_STREAM_CHUNCK = 5
    REQUEST_STREAM_END = 6
    RESPONSE_STREAM_END = 7
    REQUEST_CANCEL = 8
    RESPONSE_CANCEL = 9 # reserved
