#!/usr/bin/python3

from argparse import ArgumentParser, Action
from os import getcwd
from sys import argv

from src.hot_reloader import HotReloader
from src.utils import is_valid_shell_command
from src.options import SimpleCppHotReloaderOptions

class EqualAssignedArgument(Action):

    def __call__(self, parser : ArgumentParser, namespace, values : str, option_string : str):
        raw_arg = next((arg for arg in argv if arg.startswith(option_string)), None)
        if not raw_arg.startswith(f"{option_string}="):
          raise parser.error(f'invalid {option_string} usage, the value must be directly assigned using \'=\' (e.g. {option_string}="-std=c++20 -I.").')
        setattr(namespace, self.dest, ' '.join(values))

if __name__ == "__main__":
  working_dir = getcwd()

  argsParser = ArgumentParser(description="Simple CPP Hot Reloader")
  argsParser.add_argument("-c", "--compiler", help="C compiler", required=False)
  argsParser.add_argument("-cf", "--cflags", action=EqualAssignedArgument, nargs='*', metavar='="CFLAGS ..."', help='CPP Compiler flags, use it with direct affectation and quoted strings (e.g. "-cf=-std=c++20")', required=False)
  argsParser.add_argument("-ld", "--ldflags", action=EqualAssignedArgument, nargs='*', metavar='="LFLAGS ..."', help='CPP Compiler linker flags, use it with direct affectation and quoted strings (e.g. "-ld=-lpthread")', required=False)
  argsParser.add_argument("-od", "--obj-dir", help="Object files output directory", required=False)
  argsParser.add_argument("-t", "--target", help="Target executable name", required=True)

  args = argsParser.parse_args()

  hot_reload_options : SimpleCppHotReloaderOptions = {
    "CXX": "g++",
    "CFLAGS": args.cflags if args.cflags else "",
    "LDFLAGS": args.ldflags if args.ldflags else "",
    "OBJ_DIR": None,
    "CXX_FILE_EXTS": [".cpp", ".cc", ".c"],
    "HXX_FILE_EXTS": [".hpp", ".h"],
    "TARGET": args.target,
    "MODE": "AR",
    "DEBUG": False
  }

  if cxx := args.compiler:
    if not is_valid_shell_command(cxx):
      argsParser.error('invalid -c usage, please provide a valid compiler (e.g. "g++", "clang++").')
    hot_reload_options["CXX"] = cxx

  if od := args.obj_dir:
    hot_reload_options["OBJ_DIR"] = od
  
  HotReloader(working_dir, hot_reload_options).start()
