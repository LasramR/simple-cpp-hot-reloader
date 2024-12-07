from collections import OrderedDict
from threading import Lock
from typing import Union, List

class AsyncQueue[T]:
  
  def __init__(self, initial_queue_state: List[T]):
    self._queue = list(OrderedDict.fromkeys(initial_queue_state)) # Dedup while keeping order
    self._queue_values = set(self._queue)
    self._lock = Lock()
  
  def enqueue(self, v : T):
    with self._lock:
      if v in self._queue_values:
        self._queue.remove(v)
      self._queue.append(v)      
      self._queue_values.add(v)
  
  def dequeue(self) -> Union[T, None]:
    with self._lock:
      if len(self._queue) == 0:
        return None
      v = self._queue.pop()
      self._queue_values.discard(v)
      return v
  
  def remove(self, v : T) -> None :
    with self._lock:
      if v in self._queue_values:
        self._queue.remove(v)
        self._queue_values.discard(v)

  def is_empty(self) -> bool :
    with self._lock:
      return len(self._queue) == 0
    
  def consume_queue(self) -> List[T]:
    with self._lock:
      values = []
      while len(self._queue):
        v = self._queue.pop()
        values.append(v)
      self._queue_values.clear()
      return values