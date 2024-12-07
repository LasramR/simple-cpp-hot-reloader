from threading import Lock
from typing import Set

class WeightedLock:
  """
  Keep track of ongoing running threads in a thread safe way
  """

  _acquired_ids: Set[str]

  def __init__(self):
    self._counter = 0
    self._lock = Lock()
    self._acquired_ids = set()

  def acquire(self, id : str):
    with self._lock:
      if not id in self._acquired_ids:
        self._acquired_ids.add(id)
        self._counter += 1

  def release(self, id : str):
    with self._lock:
      if id in self._acquired_ids:
        self._acquired_ids.remove(id)
        self._counter -= 1

  def is_fully_released(self):
    with self._lock:
      return self._counter == 0
