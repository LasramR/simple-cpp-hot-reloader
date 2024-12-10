from hashlib import blake2b
from os import path
from typing import List

from ..compilation.compilation_graph import CompilationGraph, CompilationGraphSimpleNode

class CompilationCacheNode:

  def __init__(self, node : CompilationGraphSimpleNode):
    self._node = node
    self._node_hash = self._hash()

  def _hash(self):
    hash = blake2b()
    with open(self._node.key, "rb") as fd:
      while chunk := fd.read(8192):
        hash.update(chunk)
    return hash.digest().hex()
  
  def is_up_to_date(self) -> bool:
    return self._node_hash == self._hash()

  def update(self) -> None:
    self._node_hash = self._hash()

class CompilationCache:

  def __init__(self, compilation_graph : CompilationGraph, compilation_cache_file_path : str):
    self._compilation_cache_file_path = compilation_cache_file_path
    self._cache_table = {node.key: CompilationCacheNode(node) for node in compilation_graph.get_all_nodes()}

  def insert_node(self, node : CompilationGraphSimpleNode) -> None :
    self._cache_table[node.key] = CompilationCacheNode(node)

  def remove_node(self, node_key : str) -> None :
    del self._cache_table[node_key]

  def update_node(self, node_key : str) -> None :
    self._cache_table[node_key].update()

  def move_node(self, old_node_key : str, new_node : CompilationGraphSimpleNode) -> None:
    self.remove_node(old_node_key)
    self.insert_node(new_node)

  def is_node_up_to_date(self, node_key : str) -> None :
    return node_key in self._cache_table and self._cache_table[node_key].is_up_to_date()

  def get_all_outdated_nodes(self) -> List[CompilationGraphSimpleNode]:
    outdated_nodes = set(self._cache_table.keys())

    if path.exists(self._compilation_cache_file_path):
      with open(self._compilation_cache_file_path, "r") as fd:
        for line in fd.readlines():
          node_key, node_hash = line.replace("\n", "").split(":")
          if node_key in self._cache_table and self._cache_table[node_key]._node_hash == node_hash:
            outdated_nodes.remove(node_key)

    return [self._cache_table[node_key]._node for node_key in outdated_nodes]

  def write_to_cache_file(self):
    with open(self._compilation_cache_file_path, "w") as fd:
      for node_key in self._cache_table:
        fd.write(f"{node_key}:{self._cache_table[node_key]._node_hash}\n")
