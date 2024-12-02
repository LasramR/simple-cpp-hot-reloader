from __future__ import annotations
from os import path
from typing import Set, Dict, List
from re import escape, match

from .utils import file_ext_regex, run_piped_command
from .options import SimpleCppHotReloaderOptions

class CompilationGraphSimpleNode:

  def __init__(self, key : str, is_header : bool, includes : Set[CompilationGraphSimpleNode] = [], included_in : Set[CompilationGraphSimpleNode] = []):
    self.key = key
    self.is_header = is_header
    self.includes = set(includes)
    self.included_in = set(included_in)

def get_all_includes_from_file(file_path : str, cflags : str, source_file_exts: List[str]) -> List[str] :
  if not len(source_file_exts):
    raise ValueError("get_all_includes_from_file: source_file_ext must be a non empty list")

  grepRegex = rf"\".*\.{source_file_exts.pop().strip('.')}\"" if len(source_file_exts) == 1 else rf"\".*\.({'|'.join(map(lambda e : e.strip('.'), source_file_exts))})\""
  commands = [
    ["cpp", "-H", file_path, *cflags.split(' ')],
    ["grep", "-oP", grepRegex],
    ["tr", "-d", "'\"'"],
    ["sort"],
    ["uniq"],
  ]
  
  includes = list(map(lambda f : path.abspath(f), run_piped_command(commands)))
  includes.remove(file_path)
  return includes
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

  def get_all_nodes(self) -> List[CompilationGraphSimpleNode]:
    return self.nodes.values()

  def get_all_non_header_nodes(self) -> List[CompilationGraphSimpleNode]:
    all_nodes = self.nodes.values()
    non_header_nodes = set()
    for node in all_nodes:
      if not node.is_header:
        non_header_nodes.add(node)
    return non_header_nodes

  def get_node(self, key : str) -> CompilationGraphSimpleNode:
    return self.nodes[key]

  def get_node_includes(self, key : str) -> Set[CompilationGraphSimpleNode]:
    return self.nodes[key].includes
  
  def get_node_included_in(self, key : str) -> Set[CompilationGraphSimpleNode]:
    return self.nodes[key].included_in
  
  def insert_node(self, key: str) -> CompilationGraphSimpleNode:
    header_file_regex = file_ext_regex(self.options["HXX_FILE_EXTS"])
  
    links = get_all_includes_from_file(key, self.options["CFLAGS"], [*self.options["CXX_FILE_EXTS"], *self.options["HXX_FILE_EXTS"]])
    self.nodes[key] = CompilationGraphSimpleNode(key, not match(header_file_regex, key) is None)

    for l in links:
      if not l.startswith(self.working_dir):
        continue
      if not l in self.nodes:
        self.insert_node(l)
      else:
        self.nodes[l].included_in.add(self.nodes[key])
      self.nodes[key].includes.add(self.nodes[l])

    self.visited.add(key)

    return self.nodes[key]
  
  def remove_node(self, key : str) -> None:
    for includes in self.get_node_includes(key):
      includes.included_in.remove(key)
    for included_in in self.get_node_included_in(key):
      included_in.includes.remove(key)
    del self.nodes[key]
  
  def update_node(self, key : str) -> CompilationGraphSimpleNode:
    node = self.get_node(key)
    
    node.includes.clear()
    for included_in in node.included_in:
      included_in.included_in.remove(node)

    links = get_all_includes_from_file(node.key, self.options["CFLAGS"], [*self.options["CXX_FILE_EXTS"], *self.options["HXX_FILE_EXTS"]])

    for l in links:
      if not l.startswith(self.working_dir):
        continue
      link_node = self.get_node(l)
      node.includes.add(link_node)
      link_node.included_in.add(node)
    
    return node