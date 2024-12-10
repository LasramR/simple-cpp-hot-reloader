from os import sep, makedirs, remove, listdir, rmdir
from os.path import abspath, exists, dirname, join
from re import match
from typing import List

from .fs import change_file_ext, get_relative_path_from, file_ext_regex, get_all_files_in_dir
from .cmd import grep_file_extensions_regex, run_piped_command
from ..options import SimpleCppHotReloaderOptions

class CppUtils  :

  def __init__(self, options : SimpleCppHotReloaderOptions):
    if not len(options["HXX_FILE_EXTS"]):
      raise ValueError("CppUtils.__init__: options.HXX_FILE_EXTS must be a non empty list")
    if not len(options["CXX_FILE_EXTS"]):
      raise ValueError("CppUtils.__init__: options.CXX_FILE_EXTS must be a non empty list")
    
    self._options = options

    self._cpp_source_file_extensions = [*self._options['CXX_FILE_EXTS'], *self._options['HXX_FILE_EXTS']]
    self._cpp_source_file_regex = file_ext_regex(self._cpp_source_file_extensions)
    self._header_file_regex = file_ext_regex(self._options["HXX_FILE_EXTS"])
    self._grep_extract_includes_regex = grep_file_extensions_regex(self._cpp_source_file_extensions)
  
  def get_cpp_source_file(self) -> List[str] :
    return get_all_files_in_dir(self._options["WORKING_DIR"], self._cpp_source_file_extensions)

  def is_cpp_source_file(self, file_path : str) -> bool :
    return not match(self._cpp_source_file_regex, file_path) is None

  def is_header(self, cpp_source_path : str) -> bool:
    return not match(self._header_file_regex, cpp_source_path) is None

  def get_compile_command(self, cpp_source_path : str) -> List[str] :
    return [
      self._options["CXX"],
      *(self._options["CFLAGS"].split(" ") or []),
      "-c",
      cpp_source_path,
      "-o",
      self.get_object_file_path(cpp_source_path),
      *(self._options["LDFLAGS"].split(" ") or [])
    ]

  def get_object_file_path(self, cpp_source_path : str) -> str:
    if not len(self._options["OBJ_DIR"]):
      return change_file_ext(cpp_source_path, ".o")
    return f"{self._options['OBJ_DIR']}{sep}{change_file_ext(get_relative_path_from(self._options['WORKING_DIR'], cpp_source_path), '.o')}"

  def get_object_file_dir(self, cpp_source_path : str) -> str :
    return dirname(get_relative_path_from(self._options["WORKING_DIR"], self.get_object_file_path(cpp_source_path)))

  def create_object_file_dir(self, cpp_source_path : str) -> None :
    if len(self._options["OBJ_DIR"]):
      makedirs(self.get_object_file_dir(cpp_source_path), exist_ok=True)    

  def clean_object_file(self, cpp_source_path : str) -> None :
    cpp_object_file_path = self.get_object_file_path(cpp_source_path)
    cpp_object_file_dir = self.get_object_file_dir(cpp_source_path)

    try:
      remove(cpp_object_file_path)
    except:
      pass

    try:
      if len(self._options["OBJ_DIR"]) and len(listdir(cpp_object_file_dir)) == 0:
        rmdir(cpp_object_file_dir)
    except:
      pass

  def get_cpp_command(self, cpp_source_path : str) -> List[str] :
    return [
      "cpp",
      "-H",
      cpp_source_path,
      *(self._options["CFLAGS"].split(" ") or []),
    ]

  def get_link_command(self, object_file_paths : List[str]) -> List[str] :
    return [
      self._options["CXX"],
      *(self._options["CFLAGS"].split(" ") or []),
      "-o",
      self._options["TARGET"],
      *object_file_paths,
      *(self._options["LDFLAGS"].split(" ") or [])
    ]
   
  def get_source_includes(self, cpp_source_path : str) -> List[str] :
    commands = [
      self.get_cpp_command(cpp_source_path),
      ["grep", "-oP", self._grep_extract_includes_regex],
      ["tr", "-d", "'\"'"],
      ["sort"],
      ["uniq"],
    ]

    includes = list(map(lambda f : abspath(f), run_piped_command(commands)))
    if len(includes):
      includes.remove(cpp_source_path)
    return includes
  
  def is_user_include(self, cpp_include : str) -> bool :
    return cpp_include.startswith(self._options["WORKING_DIR"])

  def is_external_include(self, cpp_include : str) -> bool :
    return not self.is_user_include(cpp_include)

  def is_compiled(self, cpp_source_path : str) -> bool :
    return exists(self.get_object_file_path(cpp_source_path))
  
  def get_target_command(self) -> List[str] :
    return [
      abspath(join(self._options["WORKING_DIR"], self._options["TARGET"])),
      *(self._options["TARGET_ARGS"].split(" ") or []),
    ]

  def is_target_built(self) -> bool :
    return exists(abspath(join(self._options["WORKING_DIR"], self._options["TARGET"])))
  
  def get_compilation_cache_file_path(self) -> str :
    return f"{self._options['WORKING_DIR']}{sep}.schr.cache"