from os import walk, sep, path
from subprocess import Popen, PIPE, run
from re import match
from typing import List

def run_piped_command(commands : List[List[str]], printCmd : bool = False) -> List[str]:
  if printCmd:
    print(" | ".join(map( lambda e : " ".join(e), commands)))

  prevStdout = None
  for c in commands:
    cp = Popen(c, stdin=prevStdout, stdout=PIPE, stderr=PIPE)
    prevStdout = cp.stdout

  return list(map(lambda l : l.decode().strip("\n\r"), prevStdout.readlines()))

def is_valid_shell_command(command : str) -> bool:
  try:
    result = run(
        ["which", command],
        stdout=PIPE,
        stderr=PIPE,
        text=True
    )
    return result.returncode == 0
  except Exception:
      return False

def file_ext_regex(exts : List[str]) -> str :
  if not len(exts):
    raise ValueError("file_ext_regex: exts must be a non empty list")

  if len(exts) == 1:
    return rf"^.*\.{exts.pop().strip('.')}$"
  
  return rf"^.*\.({'|'.join(map(lambda e : e.strip('.'), exts))})$"

def change_file_ext(file_path : str, new_ext : str) -> str:
  last_dot = file_path.rfind('.')

  return f"{file_path if last_dot < 0 else file_path[:last_dot]}.{new_ext.strip('.')}"

def get_relative_path_from(base: str, target: str) -> str:
  return path.relpath(target, base)

def get_all_files_in_dir(working_dir : str, filter_exts : List[str] = [], return_abs_path : bool = False) -> List[str]:
  matching_files = []

  filter_regex = None if len(filter_exts) == 0 else file_ext_regex(filter_exts)
  for (dirPath, _, fileNames) in walk(working_dir):
    for f in fileNames:
      file = f"{dirPath}{sep}{f}"
      if return_abs_path:
        file = path.abspath(file)

      if not filter_regex:
        matching_files.append(file)
      elif not match(filter_regex, file) is None:
        matching_files.append(file)
  
  return matching_files

