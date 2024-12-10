#!/usr/bin/python3

from argparse import ArgumentParser, Action, Namespace, RawTextHelpFormatter
from os import getcwd
from sys import argv
from typing import List

from schr.hot_reloader import HotReloader
from schr.utils.cmd import is_valid_command
from schr.options import SimpleCppHotReloaderOptions, as_makefile

class EqualAssignedArgument(Action):

  def __call__(self, parser : ArgumentParser, namespace : Namespace, raw_value : str, option_string : str):
    raw_arg = next((arg for arg in argv if arg.startswith(option_string)), None)
    if not raw_arg.startswith(f"{option_string}="):
      raise parser.error(f'invalid {option_string} usage, the value must be directly assigned using \'=\' (e.g. {option_string}="-std=c++20 -I.").')
    setattr(namespace, self.dest, raw_value)

class AlphabeticalCharactersCombinationArgument(Action):
   
  ALLOWED_CHARACTER = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
  CASE_SENSITIVE = False
  DEDUPLICATE = False
  UPPER_DEFAULT = False
  LOWER_DEFAULT = False

  def __call__(self, parser : ArgumentParser, namespace : Namespace, raw_values : List[str], option_string : str):
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


def main():
  argsParser = ArgumentParser(usage="schr", description="Simple CPP Hot Reloader (schr)", formatter_class=RawTextHelpFormatter)
  argsParser.add_argument("-c", "--compiler", help="C/C++ compiler executable to use (eg gcc, g++, clang, ...)?\ndefaults to g++", required=False)
  argsParser.add_argument("-cf", "--cflags", action=EqualAssignedArgument, metavar='="CFLAGS ..."', help='Sets additional flags for the C/C++ compiler (eg -std=c++20, -Wall, ...).\nMust be used with direct affectation and quoted strings (eg -cf="-std=c++20 ...")', required=False)
  argsParser.add_argument("-lf", "--lflags", action=EqualAssignedArgument, metavar='="LFLAGS ..."', help='Sets additional flags for the C/C++ linker (eg -lpthread, -lvulkan, ...).\nMust be used with direct affectation and quoted strings (eg -lf="-lpthread ...")', required=False)
  argsParser.add_argument("-od", "--obj-dir", help="Specifies the directory where object files (*.o) should be stored.\n If not provided, object files are outputed to the source code", required=False)
  argsParser.add_argument("-t", "--target", help="The path for the built executable of your project", required=True)
  argsParser.add_argument("-ta", "--target-args", action=EqualAssignedArgument, metavar='="TARGET_ARGS ..."', help='Command-line arguments to pass to your built executable when it is restarted by schr.\nMust be used with direct affectation and quoted strings (eg -ta="-myflag value ...")', required=False)
  argsParser.add_argument("-m", "--mode", action=ModeCharactersCombination, help='Configures schr behavior using a set of mode characters\n\tC - Automatically recompile on changes\n\tR - Restart the target after each build\ne.g. "-m CR" will enable both automatic compilation and restart\ndefaults to "CR"', required=False)
  argsParser.add_argument("-d", "--debug", action='store_true', help="Enable schr debug mode which displays compiler/linker commands during execution\ndisabled by default", required=False)
  argsParser.add_argument("--makefile", action='store_true', help="Outputs the source code for a makefile that can be used to invoke schr with the specified arguments\ndisabled by default", required=False)
  args = argsParser.parse_args()

  hot_reloader_options = SimpleCppHotReloaderOptions({
    "WORKING_DIR": getcwd(),
    "CXX": "g++",
    "CFLAGS": args.cflags or "",
    "LDFLAGS": args.lflags or "",
    "OBJ_DIR": "",
    "CXX_FILE_EXTS": [".cpp", ".cc", ".c"],
    "HXX_FILE_EXTS": [".hpp", ".h"],
    "TARGET": args.target,
    "TARGET_ARGS": args.target_args or "",
    "MODE": args.mode or "CR",
    "DEBUG": args.debug
  })

  if cxx := args.compiler:
    if not is_valid_command(cxx):
      argsParser.error('invalid -c usage, please provide a valid compiler (e.g. "g++", "clang++").')
    hot_reloader_options["CXX"] = cxx

  if od := args.obj_dir:
    hot_reloader_options["OBJ_DIR"] = od

  if args.makefile:
    print(as_makefile(hot_reloader_options))
    exit(0)

  HotReloader(hot_reloader_options).start()

if __name__ == "__main__":
  main()