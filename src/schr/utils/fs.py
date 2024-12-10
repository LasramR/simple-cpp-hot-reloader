from os import walk, sep
from os.path import relpath, abspath
from re import match
from typing import List

def file_ext_regex(extensions : List[str]) -> str :
  if not len(extensions):
    raise ValueError("file_ext_regex: exts must be a non empty list")

  if len(extensions) == 1:
    return rf"^.*\.{extensions[0].strip('.')}$"
  
  return rf"^.*\.({'|'.join(map(lambda e : e.strip('.'), extensions))})$"

def change_file_ext(file_path : str, new_ext : str) -> str:
  last_dot = file_path.rfind('.')

  return f"{file_path if last_dot < 0 else file_path[:last_dot]}.{new_ext.strip('.')}"

def get_relative_path_from(base: str, target: str) -> str:
  return relpath(target, base)

def get_all_files_in_dir(working_dir : str, filter_exts : List[str] = [], return_abs_path : bool = False) -> List[str]:
  matching_files = []

  filter_regex = None if len(filter_exts) == 0 else file_ext_regex(filter_exts)
  for (dirPath, _, fileNames) in walk(working_dir):
    for f in fileNames:
      file = f"{dirPath}{sep}{f}"
      if return_abs_path:
        file = abspath(file)

      if not filter_regex:
        matching_files.append(file)
      elif not match(filter_regex, file) is None:
        matching_files.append(file)

  return matching_files

def sanitize_file_extensions(file_extensions : List[str]) -> List[str] :
  return list(map(lambda e : e.strip('.'), file_extensions))