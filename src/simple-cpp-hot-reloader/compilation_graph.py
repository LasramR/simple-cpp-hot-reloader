from __future__ import annotations
from os import path
from typing import Set, Dict, List
from re import match

from .utils import file_ext_regex, run_piped_command
from .options import SimpleCppHotReloaderOptions

class CompilationGraphSimpleNode:

  def __init__(self, key : str, is_header : bool, includes : Set[CompilationGraphSimpleNode] = [], included_in : Set[CompilationGraphSimpleNode] = []):
    self.key = key
    self.is_header = is_header
    self.includes = set(includes)
    self.included_in = set(included_in)

def get_all_includes_from_file(file_path : str, cflags : List[str], source_file_exts: List[str]) -> List[str] :
  if not len(source_file_exts):
    raise ValueError("get_all_includes_from_file: source_file_ext must be a non empty list")

  commands = [
    ["cpp", *cflags.split(' '), "-H", file_path],
    ["grep", "-oP", file_ext_regex(source_file_exts)],
    ["tr", "-d", "'\"'"],
    ["sort"],
    ["uniq"],
  ]
  return list(map(lambda f : path.abspath(f.strip("\r\n")), run_piped_command(commands, True)[1:]))

class CompilationGraph:

  def __init__(self, working_dir : str, initial_keys_set : List[str], options : SimpleCppHotReloaderOptions):
    self.options = options    
    self.working_dir = working_dir
    self.nodes : Dict[str, CompilationGraphSimpleNode]= {}
    self.visited = set()

    header_file_regex = file_ext_regex(self.options["HXX_FILE_EXTS"])
    keys_to_visit = initial_keys_set
    while len(keys_to_visit):
      key = keys_to_visit.pop()
      if key in self.visited or not key.startswith(self.working_dir):
        continue
      
      links = get_all_includes_from_file(key, self.options["CFLAGS"], [*self.options["CXX_FILE_EXTS"], *self.options["HXX_FILE_EXTS"]])

      if not key in self.nodes:
        self.nodes[key] = CompilationGraphSimpleNode(key, not match(header_file_regex, key) is None)

      for l in links:
        if not l.startswith(self.working_dir):
          continue
        if not l in self.nodes:
          self.nodes[l] = CompilationGraphSimpleNode(l, not match(header_file_regex, l) is None, included_in=[self.nodes[key]])
        else:
          self.nodes[l].included_in.add(self.nodes[key])
        self.nodes[key].includes.add(self.nodes[l])

      self.visited.add(key)
      keys_to_visit = [*keys_to_visit, *links]

  def get_node(self, key : str) -> CompilationGraphSimpleNode:
    return self.nodes[key]

  def get_node_includes(self, key : str) -> CompilationGraphSimpleNode:
    return self.nodes[key].includes
  
  def get_node_included_in(self, key : str) -> CompilationGraphSimpleNode:
    return self.nodes[key].included_in

