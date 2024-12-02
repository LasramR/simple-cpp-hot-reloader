from typing import List, Union, TypedDict, Literal

class SimpleCppHotReloaderOptions(TypedDict):
    CXX: str
    CFLAGS: Union[str, None]
    LDFLAGS: Union[str, None]
    OBJ_DIR: Union[str, None]
    CXX_FILE_EXTS: List[str]
    HXX_FILE_EXTS: List[str]
    TARGET: str
    MODE: Union[Literal["AR"]]