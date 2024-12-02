from typing import List, Union

from .compilation_graph import CompilationGraphSimpleNode

class CompilationQueue:
  
  def __init__(self, initial_queue_state: List[CompilationGraphSimpleNode]):
    self.queue = [node.key for node in initial_queue_state]
    self.queue_values = {node.key: node for node in initial_queue_state}
  
  def enqueue(self, node: CompilationGraphSimpleNode):
    if node.key in self.queue_values:
      self.queue.remove(node.key)
    
    self.queue.append(node.key)
    self.queue_values[node.key] = node
  
  def dequeue(self) -> Union[CompilationGraphSimpleNode, None]:
    if len(self.queue) == 0:
      return None
    node = self.queue_values[self.queue.pop()]
    del self.queue_values[node.key]
    return node
  
  def remove(self, key: str) -> None :
    if key in self.queue_values:
      self.queue.remove(key)
      del self.queue_values[key]

  def is_empty(self) -> bool :
    return len(self.queue_values) == 0