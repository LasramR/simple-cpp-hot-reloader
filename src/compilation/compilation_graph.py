from __future__ import annotations
from subprocess import run
from typing import Set, Dict, List, Union

from ..multithreading.async_process import AsyncProcess
from ..multithreading.async_queue import AsyncQueue
from ..multithreading.weighted_lock import WeightedLock
from ..utils.cpp import CppUtils
from ..utils.logger import Logger
from ..options import SimpleCppHotReloaderOptions

class CompilationGraphSimpleNode:

  _compilation_process : Union[AsyncProcess, None] = None

  def __init__(self, compilation_graph : CompilationGraph, key : str):
    self._compilation_graph = compilation_graph
    self.key = key
    self.is_header = self._compilation_graph._cpp.is_header(self.key)
    self.object_file_path = self._compilation_graph._cpp.get_object_file_path(self.key)

    self.includes = set()
    self.included_in = set()

    if not self.is_header:
      self._compilation_process = AsyncProcess(
        self._compilation_graph._cpp.get_compile_command(self.key),
        {
          "stderr_logger": print,
          "on_success": self._on_compilation_success,
          "on_error": self._on_compilation_error
        }
      )

  def _on_compilation_success(self) -> None :
    self._compilation_graph._logger.info(f"{self.key} recompiled")
    self._compilation_graph._weighted_lock.release(self.key)
    self._compilation_graph._link_target()

  def _on_compilation_error(self) -> None :
    self._compilation_graph._logger.error(f"{self.key} compilation error")
    self._compilation_graph._weighted_lock.release(self.key)
    self._compilation_graph._compilation_queue.enqueue(self)

  def recompile(self) -> None:
    if self.is_header:
      for node in self.included_in:
        node.recompile()
    else:
      self._compilation_graph._weighted_lock.acquire(self.key)
      self._compilation_graph._cpp.create_object_file_dir(self.key)
      self._compilation_process.terminate_and_run()

class CompilationGraph:

  _nodes : Dict[str, CompilationGraphSimpleNode]
  _visited : Set[str]
  _compilation_queue : AsyncQueue[CompilationGraphSimpleNode]
  _link_process : AsyncProcess

  def __init__(self, options: SimpleCppHotReloaderOptions, logger: Logger):
    self._options = options
    self._cpp = CppUtils(self._options)

    self._logger = logger

    self._nodes = {}
    self._visited = set()
    self._compilation_queue = AsyncQueue([])
    self._weighted_lock = WeightedLock()
    self._link_process = AsyncProcess(
      self._cpp.get_link_command([]),
      {
        "on_success": self._on_link_success,
        "on_error": self._on_link_error,
        "stderr_logger": print
      }
    )

    keys_to_visit = self._cpp.get_cpp_source_file()
    while len(keys_to_visit):
      key = keys_to_visit.pop()
      if key in self._visited or self._cpp.is_external_include(key):
        continue
      
      new_node = self.get_node(key) or self.insert_node(key, True)

      keys_to_visit = [*keys_to_visit, *[node.key for node in new_node.includes]]

    for node in self.get_all_non_header_nodes():
      if not self._cpp.is_compiled(node.key):
        self._compilation_queue.enqueue(node)

  def has_node(self, key : str) -> bool :
    return key in self._nodes

  def get_node(self, key : str) -> Union[CompilationGraphSimpleNode, None] :
    if self.has_node(key):
      return self._nodes[key]
    return None
  
  def get_all_nodes(self) -> List[CompilationGraphSimpleNode]:
    all_nodes = []
    for k in self._nodes:
      all_nodes.append(self._nodes[k])
    return all_nodes
  
  def get_all_header_nodes(self) -> List[CompilationGraphSimpleNode] :
    return filter(lambda n : n.is_header, self.get_all_nodes())
  
  def get_all_non_header_nodes(self) -> List[CompilationGraphSimpleNode] :
    return filter(lambda n : not n.is_header, self.get_all_nodes())

  def get_all_sub_nodes(self, key_prefix : str) -> List[CompilationGraphSimpleNode] :
    return filter(lambda n : n.key.startswith(key_prefix), self.get_all_nodes())

  def _visit_node(self, node : CompilationGraphSimpleNode, disable_enqueue : bool = False) -> CompilationGraphSimpleNode :
    links = self._cpp.get_source_includes(node.key)    

    for l in links:
      if self._cpp.is_external_include(l):
        continue
      
      link_node = self.get_node(l) or self.insert_node(l, disable_enqueue)
      
      link_node.included_in.add(node)
      node.includes.add(link_node)

    self._visited.add(node.key)

    return node

  def insert_node(self, key : str, disable_enqueue : bool = False) -> CompilationGraphSimpleNode :
    new_node = CompilationGraphSimpleNode(self, key)
    self._nodes[key] = new_node

    if new_node.is_header:
      for node in self.get_all_nodes():
        self.update_node(node.key, disable_enqueue)

    self._visit_node(new_node, disable_enqueue)
    
    if not disable_enqueue and not new_node.is_header and not self._cpp.is_compiled(key):
      self._compilation_queue.enqueue(new_node)
    
    return new_node

  def update_node(self, key : str, disable_enqueue : bool = False) -> Union[CompilationGraphSimpleNode, None]:
    if not self.has_node(key):
      return None
    
    updated_node = self.get_node(key)
    
    updated_node.includes.clear()
    self._visit_node(updated_node, disable_enqueue)
    
    if not disable_enqueue:
      self._compilation_queue.enqueue(updated_node)

    return updated_node 
  
  def remove_node(self, key : str) -> None:
    if not self.has_node(key):
      return

    removed_node = self.get_node(key)

    for includes in removed_node.includes:
      includes.included_in.discard(removed_node)

    for included_in in removed_node.included_in:
      included_in.includes.discard(removed_node)
    
    self._compilation_queue.remove(removed_node)
    self._weighted_lock.release(key)
    del self.nodes[key]
  
  def move_node(self, old_key : str, new_key : str) -> CompilationGraphSimpleNode :
    moved_node = self.get_node(new_key) or self.insert_node(new_key)
    
    self._visit_node(moved_node)

    if removed_node := self.get_node(old_key):
      for old_included_in_node in removed_node.included_in:
        if self.has_node(old_included_in_node):
          moved_node.included_in.add(old_included_in_node)
      self.remove_node(old_key)

    self._compilation_queue.enqueue(moved_node)

    return moved_node
  
  def _on_link_success(self) -> None : 
    self._logger.info(f"target {self._options['TARGET']} relinked")
  
  def _on_link_error(self) -> None :
    self._logger.error(f"target {self._options['TARGET']} linking error")


  def _link_target(self) -> None :
    if self._weighted_lock.is_fully_released() and self._compilation_queue.is_empty():
      command = self._cpp.get_link_command(list(map(lambda n: n.object_file_path, self.get_all_non_header_nodes())))
      self._link_process.terminate()
      self._link_process.run_with_command(command)

  def build(self):
    for node in self._compilation_queue.consume_queue():
      node.recompile()

    
  