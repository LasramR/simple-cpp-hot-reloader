from os import sep, makedirs, path
from subprocess import run
from signal import signal, SIGINT
from typing import List

from watchdog.events import DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileMovedEvent, RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .options import SimpleCppHotReloaderOptions
from .compilation_cache import CompilationCache
from .compilation_graph import CompilationGraph, CompilationGraphSimpleNode
from .compilation_queue import CompilationQueue
from .utils import get_all_files_in_dir, change_file_ext, get_relative_path_from, file_ext_regex

class HotReloader(RegexMatchingEventHandler):

  def __init__(self, working_dir : str, options : SimpleCppHotReloaderOptions):
    self.working_dir = working_dir
    self.options = options

    watched_files =  get_all_files_in_dir(self.working_dir, [*self.options["CXX_FILE_EXTS"], *self.options["HXX_FILE_EXTS"]])
    self.cache = CompilationCache(f"{self.working_dir}{sep}.simple-cpp-hr.cache", watched_files)
    self.compile_graph = CompilationGraph(self.working_dir, watched_files, self.options)
    self.compile_queue = CompilationQueue([self.compile_graph.get_node(cca.file_path) for cca in self.cache.get_all_outdated_artifacts()])
    super().__init__(regexes=file_ext_regex([*self.options['CXX_FILE_EXTS'], *self.options['HXX_FILE_EXTS']]))

  def link_target(self) -> bool :
    command = [
      self.options["CXX"],
      *(self.options["CFLAGS"].split(" ") or []),
      "-o",
      self.options["TARGET"],
      *[f"{change_file_ext(node.key, '.o')}" if self.options["OBJ_DIR"] == None else f"{self.options["OBJ_DIR"]}{sep}{change_file_ext(get_relative_path_from(self.working_dir, node.key), '.o')}" for node in self.compile_graph.get_all_non_header_nodes()],
      *(self.options["LDFLAGS"].split(" ") or [])
    ]

    if self.options["DEBUG"]:
      print(" ".join(command))

    if run(command).returncode == 0:
      print(f"{self.options['TARGET']} relinked")
      return True
    else:
      return False

  def recompile(self, node : CompilationGraphSimpleNode, build_target : bool) -> bool :
    if node.is_header:
      compilation_ok = True
      for included_in in node.included_in:
        if self.recompile(included_in, False):
          self.compile_queue.remove(included_in.key)
        else:
          compilation_ok = False
      if not compilation_ok:
        return False
    else:
      if self.options["OBJ_DIR"]:
        makedirs(f"{self.options["OBJ_DIR"]}{sep}{path.dirname(get_relative_path_from(self.working_dir, node.key))}", exist_ok=True)
    
      command = [
        self.options["CXX"],
        *(self.options["CFLAGS"].split(" ") or []),
        "-c",
        node.key,
        "-o",
        f"{change_file_ext(node.key, '.o')}" if self.options["OBJ_DIR"] == None else f"{self.options["OBJ_DIR"]}{sep}{change_file_ext(get_relative_path_from(self.working_dir, node.key), '.o')}",
        *(self.options["LDFLAGS"].split(" ") or [])
      ]

      if self.options["DEBUG"]:
        print(" ".join(command))

      if run(command, stdout=None).returncode == 0:
        print(f"{node.key} recompiled")
        self.compile_queue.remove(node.key)
      else:
        print(f"{node.key} compilation error")
        self.compile_queue.enqueue(node)
        return False

    if build_target:
      if not self.compile_queue.is_empty():
        print("QUEUE TRIGGER")
        compilation_queue_copy = CompilationQueue(self.compile_queue.queue_values.values())
        compilation_ok = True
        while outdated_node := compilation_queue_copy.dequeue():
          compilation_ok = self.recompile(outdated_node, False)
        if not compilation_ok:
          return False
      return self.link_target()
    
    return True

  def on_created(self, fse: DirCreatedEvent | FileCreatedEvent) -> None:
    if fse.is_directory:
      return
    
    self.cache.add_entry(fse.src_path)
    node = self.compile_graph.insert_node(fse.src_path)
    print(f"{node.key} created")

    if self.options["MODE"] == "AR":
      if self.recompile(node, True):
        self.cache.dump()
    else:
      self.compile_queue.enqueue(node)
  
  def on_deleted(self, fse: DirDeletedEvent | FileDeletedEvent) -> None:
    if fse.is_directory:
      return
    
    self.cache.remove_entry(fse.src_path)
    self.compile_graph.remove_node(fse.src_path)
    self.compile_queue.remove(fse.src_path)

    print(f"{fse.src_path} deleted")

    self.cache.dump()

  def on_moved(self, fse: DirMovedEvent | FileMovedEvent) -> None:
    if fse.is_directory:
      return
    
    self.compile_queue.remove(fse.src_path)
    self.cache.move_entry(fse.src_path, fse.dest_path)
    node = self.compile_graph.move_node(fse.src_path, fse.dest_path)

    print(f"{fse.src_path} moved to {fse.dest_path}")
    if self.options["MODE"] == "AR":
      if self.recompile(node, True):
        self.cache.dump()
    else:
      self.compile_queue.enqueue(node)

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if fse.is_directory or self.cache.cache_table[fse.src_path].is_up_to_date():
      return

    node = self.compile_graph.update_node(fse.src_path)
    self.cache.update_entry(node.key)

    if self.options["MODE"] == "AR":
      if self.recompile(node, True):
        self.cache.dump()
        
    else:
      self.compile_queue.enqueue(node)

  def start(self):
    if self.options["MODE"] == "AR" and not self.compile_queue.is_empty():
      compilation_ok = True
      while outdated := self.compile_queue.dequeue():
        compilation_ok = self.recompile(outdated, False)
        if not compilation_ok:
          break
      if compilation_ok:
        if self.link_target():
          self.cache.dump()

    observer = Observer()
    observer.schedule(self, self.working_dir, recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    observer.join()


