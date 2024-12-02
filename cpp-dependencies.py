#!/usr/bin/python3

from __future__ import annotations

from re import Pattern, match
import subprocess
from typing import Dict, List, Set, Union
from os import getcwd, path, sep, walk

def run_piped_command(commands, printCmd = False):
  if printCmd:
    print(" | ".join(map( lambda e : " ".join(e), commands)))

  prevStdout = None
  for c in commands:
    cp = subprocess.Popen(c, stdin=prevStdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prevStdout = cp.stdout
  return list(map(lambda l : l.decode(), prevStdout.readlines()))

def get_all_includes_from_file(file_path : str, source_file_exts: List[str]) -> List[str] :
  if not len(source_file_exts):
    raise ValueError("get_all_includes_from_file: source_file_ext must be a non empty list")

  commands = [
    ["cpp", "-I./src", "-H", file_path],
    ["grep", "-oP", f'\"\\S+\\.{source_file_exts.pop().strip(".") if len(source_file_exts) == 1 else f"({'|'.join(map(lambda e : e.strip('.'),source_file_exts))})" }\"'],
    ["tr", "-d", "'\"'"],
    ["sort"],
    ["uniq"],
  ]
  return list(map(lambda f : path.abspath(f.strip("\r\n")), run_piped_command(commands)[1:]))

def get_all_files_in_dir(working_dir : str, filter_exts : List[str] = [], return_abs_path : bool = False) -> List[str]:
  matching_files = []

  filter_regex = None if not len(filter_exts) else rf"^.*\.{filter_exts.pop().strip('.') if len(filter_exts) == 1 else f"({'|'.join(map(lambda e : e.strip('.'), filter_exts))})"}$"
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

class CompilationGraphSimpleNode:

  def __init__(self, key : str, is_header : bool, includes : Set[CompilationGraphSimpleNode] = [], included_in : Set[CompilationGraphSimpleNode] = []):
    self.key = key
    self.is_header = is_header
    self.includes = set(includes)
    self.included_in = set(included_in)

class CompilationGraph:

  def __init__(self, working_dir : str, initial_keys_set : List[str], cpp_exts : List[str], hpp_exts : List[str]):
    if not len(cpp_exts):
      raise ValueError("CompilationGraph.__init__: cpp_exts must be a non empty list")
    if not len(hpp_exts):
      raise ValueError("CompilationGraph.__init__: hpp_exts must be a non empty list")

    self.working_dir = working_dir
    self.nodes : Dict[str, CompilationGraphSimpleNode]= {}
    self.visited = set()

    header_file_regex = rf".*\.{hpp_exts.pop().strip('.') if len(hpp_exts) == 1 else f"({'|'.join(map(lambda e : e.strip('.'), hpp_exts))})"}$"
    keys_to_visit = initial_keys_set
    while len(keys_to_visit):
      key = keys_to_visit.pop()
      if key in self.visited or not key.startswith(self.working_dir):
        continue
      
      links = get_all_includes_from_file(key, [*cpp_exts, *hpp_exts])

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

  def get_node(self, key : str) -> Union[CompilationGraphSimpleNode, None]:
    if key in self.nodes:
      return self.nodes[key]
    return None

  def get_node_includes(self, key : str) -> Union[List[CompilationGraphSimpleNode], None]:
    if key in self.nodes:
      return self.nodes[key].includes
    return None
  
  def get_node_included_in(self, key : str) -> Union[List[CompilationGraphSimpleNode], None] :
    if key in self.nodes:
      return self.nodes[key].included_in
    return None

working_dir = getcwd()

CPP_EXTS = [".cpp", ".cc", ".c"]
HPP_EXTS = [".hpp", ".hh", ".h"]

cg = CompilationGraph(working_dir, list(map(lambda f : path.abspath(f), get_all_files_in_dir("./src", CPP_EXTS))), CPP_EXTS, HPP_EXTS)

for n in cg.nodes:
  print(f"{n} is header {cg.nodes[n].is_header}")
  
  includes = cg.get_node_includes(n)
  if len(includes):
    print(f"includes ({len(includes)}):")
    for i in includes:
      print(f"\t- {i.key}")

  included_in = cg.get_node_included_in(n)
  if len(included_in):
    print(f"included in ({len(included_in)}):")
    for i in included_in:
      print(f"\t- {i.key}")