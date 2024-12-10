from __future__ import annotations
from typing import TypedDict, Union, Literal, Dict

Color = Literal["RED", "BLUE", "GREEN", "YELLOW", "WHITE", "BLACK", "MAGENTA", "CYAN"]
ColorTable: Dict[Color, str] = {
    "RED": "\033[31m",
    "BLUE": "\033[34m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "WHITE": "\033[37m",
    "BLACK": "\033[30m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
}
ColorReset = "\033[0m"

class LoggerOptions (TypedDict):

  NAME: Union[str, None]
  SUCCESS_COLOR: Union[Color, None]
  INFO_COLOR: Union[Color, None]
  ERROR_COLOR: Union[Color, None]
  WARN_COLOR: Union[Color, None] 

  @staticmethod
  def DefaultWithName(name : Union[str, None]) -> LoggerOptions:
    return {
      "NAME": name,
      "SUCCESS_COLOR": "GREEN",
      "INFO_COLOR": "BLUE",
      "WARN_COLOR": "YELLOW",
      "ERROR_COLOR": "RED"
    }

  @staticmethod
  def Default() -> LoggerOptions:
    return LoggerOptions.DefaultWithName(None)

class Logger:

  def __init__(self, options : LoggerOptions) -> None:
    self.options = options
  
  def success(self, log : str) -> None:
    print(f"{ColorTable[self.options["SUCCESS_COLOR"]]}{"" if self.options["NAME"] is None else f"[{self.options["NAME"]}] "}{log}{ColorReset}")

  def info(self, log : str) -> None:
    print(f"{ColorTable[self.options["INFO_COLOR"]]}{"" if self.options["NAME"] is None else f"[{self.options["NAME"]}] "}{log}{ColorReset}")

  def warn(self, log : str) -> None:
    print(f"{ColorTable[self.options["WARN_COLOR"]]}{"" if self.options["NAME"] is None else f"[{self.options["NAME"]}] "}{log}{ColorReset}")

  def error(self, log : str) -> None:
    print(f"{ColorTable[self.options["ERROR_COLOR"]]}{"" if self.options["NAME"] is None else f"[{self.options["NAME"]}] "}{log}{ColorReset}")
