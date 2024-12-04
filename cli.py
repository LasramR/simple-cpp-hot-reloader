#!/usr/bin/python3

from argparse import ArgumentParser, Action, Namespace, RawTextHelpFormatter
from os import getcwd
from sys import argv
from typing import List

from src.hot_reloader import HotReloader
from src.utils import is_valid_shell_command
from src.options import SimpleCppHotReloaderOptions

class EqualAssignedArgument(Action):

  def __call__(self, parser : ArgumentParser, namespace, raw_values : List[str], option_string : str):
    value = ' '.join(raw_values)
    raw_arg = next((arg for arg in argv if arg.startswith(option_string)), None)
    if not raw_arg.startswith(f"{option_string}="):
      raise parser.error(f'invalid {option_string} usage, the value must be directly assigned using \'=\' (e.g. {option_string}="-std=c++20 -I.").')
    setattr(namespace, self.dest, value)

class AlphabeticalCharactersCombinationArgument(Action):
   
  ALLOWED_CHARACTER = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
  CASE_SENSITIVE = False
  DEDUPLICATE = False
  UPPER_DEFAULT = False
  LOWER_DEFAULT = False

  def __call__(self, parser : ArgumentParser, namespace, raw_values : List[str], option_string : str):
    if self.UPPER_DEFAULT == True and self.LOWER_DEFAULT == True:
      raise ValueError("AlphabeticalCharactersCombinationArgument.__call__: could not use both UPPER_DEFAULT and LOWER_DEFAULT modes at the same time")
    
    value = "".join(raw_values)

    if self.DEDUPLICATE:
      value = "".join(set(value))
    
    if self.UPPER_DEFAULT:
      value = value.upper()
    
    if self.LOWER_DEFAULT:
      value = value.lower()

    for c in value:
      if self.CASE_SENSITIVE and c in self.ALLOWED_CHARACTER:
        continue
      elif c.lower() in self.ALLOWED_CHARACTER or c.upper() in self.ALLOWED_CHARACTER:
        continue
      raise parser.error(f'invalid {option_string} value, must be one of "{self.ALLOWED_CHARACTER}"')

    setattr(namespace, self.dest, value)

class ModeCharactersCombination (AlphabeticalCharactersCombinationArgument):

  ALLOWED_CHARACTER = "CR"
  CASE_SENSITIVE = False
  DEDUPLICATE = True
  UPPER_DEFAULT = True
  LOWER_DEFAULT = False


if __name__ == "__main__":
  working_dir = getcwd()

  argsParser = ArgumentParser(description="Simple CPP Hot Reloader (schr)", formatter_class=RawTextHelpFormatter)
  argsParser.add_argument("-c", "--compiler", help="C compiler executable\ndefaults to g++", required=False)
  argsParser.add_argument("-cf", "--cflags", action=EqualAssignedArgument, nargs='*', metavar='="CFLAGS ..."', help='CPP Compiler flags, use it with direct affectation and quoted strings (e.g. "-cf=-std=c++20")', required=False)
  argsParser.add_argument("-ld", "--ldflags", action=EqualAssignedArgument, nargs='*', metavar='="LFLAGS ..."', help='CPP Compiler linker flags, use it with direct affectation and quoted strings (e.g. "-ld=-lpthread")', required=False)
  argsParser.add_argument("-od", "--obj-dir", help="Object files output directory\nby defaults, compilation artifacts (i.e. object files) will be outputed next to the source code", required=False)
  argsParser.add_argument("-t", "--target", help="Target executable name", required=True)
  argsParser.add_argument("-ta", "--target-args", action=EqualAssignedArgument, nargs='*', metavar='="TARGET_ARGS ..."', help="Arguments passed to target when restarted", required=False)
  argsParser.add_argument("-m", "--mode", action=ModeCharactersCombination, help='A combination of characters describing the hot reloader behaviour:\n\tC - Automatically recompile on changes\n\tR - Restart the target after each build\ne.g. "-m CR" will enable both automatic compilation and restart\ndefaults to "CR"', required=False)
  argsParser.add_argument("-d", "--debug", action='store_true', help="Enable debug mode. Compilation commands will be printed", required=False)
  # TODO add a flag to print out a nice make command :)
  # TODO add a flag to print the dependency graph of the cpp project ? 

  args = argsParser.parse_args()

  hot_reload_options : SimpleCppHotReloaderOptions = {
    "CXX": "g++",
    "CFLAGS": args.cflags or "",
    "LDFLAGS": args.ldflags or "",
    "OBJ_DIR": None,
    "CXX_FILE_EXTS": [".cpp", ".cc", ".c"],
    "HXX_FILE_EXTS": [".hpp", ".h"],
    "TARGET": args.target,
    "TARGET_ARGS": args.target_args or "",
    "MODE": args.mode or "CR",
    "DEBUG": args.debug
  }

  if cxx := args.compiler:
    if not is_valid_shell_command(cxx):
      argsParser.error('invalid -c usage, please provide a valid compiler (e.g. "g++", "clang++").')
    hot_reload_options["CXX"] = cxx

  if od := args.obj_dir:
    hot_reload_options["OBJ_DIR"] = od

  HotReloader(working_dir, hot_reload_options).start()
