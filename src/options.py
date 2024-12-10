from typing import List, Union, TypedDict

class SimpleCppHotReloaderOptions(TypedDict):
  WORKING_DIR: str
  CXX: str
  CFLAGS: Union[str, None]
  LDFLAGS: Union[str, None]
  OBJ_DIR: Union[str, None]
  CXX_FILE_EXTS: List[str]
  HXX_FILE_EXTS: List[str]
  TARGET: str
  TARGET_ARGS: str
  MODE: str
  DEBUG: bool

def as_makefile(options : SimpleCppHotReloaderOptions) -> str:
    return f"""
CXX="{options["CXX"]}"
CFLAGS="{options["CFLAGS"]}"
LDFLAGS="{options["LDFLAGS"]}"
OBJ_DIR="{options["OBJ_DIR"]}"
TARGET="{options["TARGET"]}"
TARGET_ARGS="{options["TARGET_ARGS"]}"

SCHR_MODE={options["MODE"]}
SCHR_DEBUG={"-d" if options["DEBUG"] else ""}

# Run the following with make dev
dev:
\tpython ./cli.py -c $(CXX) -cf=$(CFLAGS) -ld=$(LDFLAGS) -od $(OBJ_DIR) -t $(TARGET) -ta=$(TARGET_ARGS) -m $(SCHR_MODE) $(SCHR_DEBUG)
"""