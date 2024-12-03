from os import sep, makedirs, path, remove, rmdir, listdir
from subprocess import run
from re import match
from signal import signal, SIGINT
from typing import List

from watchdog.events import DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileMovedEvent, FileSystemEvent, RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
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

    self.compile_graph = CompilationGraph(self.working_dir, watched_files, self.options)
    
    initialQueueSet = set()
    for node in self.compile_graph.get_all_non_header_nodes():
      node_object_file_path = f"{change_file_ext(node.key, '.o')}" if self.options["OBJ_DIR"] == None else f"{self.options["OBJ_DIR"]}{sep}{change_file_ext(get_relative_path_from(self.working_dir, node.key), '.o')}"
      if not path.exists(node_object_file_path):
        initialQueueSet.add(node)

    self.compilation_cache = CompilationCache(f"{self.working_dir}{sep}.simple-cpp-hr.cache", watched_files)
    
    for outdated_cca in self.compilation_cache.get_all_outdated_artifacts():
      initialQueueSet.add(self.compile_graph.get_node(outdated_cca.file_path))

    self.compile_queue = CompilationQueue(list(initialQueueSet))

    self.filter_path_regex = file_ext_regex([*self.options['CXX_FILE_EXTS'], *self.options['HXX_FILE_EXTS']])
    super().__init__()

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

  def recompile(self, build_target : bool) -> bool :
    node = self.compile_queue.dequeue()

    if node.is_header:
      for included_in in node.included_in:
        self.compile_queue.enqueue(included_in)
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
      else:
        print(f"{node.key} compilation error")
        self.compile_queue.enqueue(node)
        return False

    if not self.compile_queue.is_empty():
      self.recompile(False)
      if not self.compile_queue.is_empty():
        return False

    if build_target:
      return self.link_target()
    
    return True
  
  def delete_node_compilation_artifact(self, node : CompilationGraphSimpleNode) -> None :
    node_object_file_path = f"{change_file_ext(node.key, '.o')}" if self.options["OBJ_DIR"] == None else f"{self.options["OBJ_DIR"]}{sep}{change_file_ext(get_relative_path_from(self.working_dir, node.key), '.o')}"
    try:
      remove(node_object_file_path)
    except:
      pass
    try:
      node_object_dir_path = path.dirname(node_object_file_path)
      if not self.options["OBJ_DIR"] is None and len(listdir(node_object_dir_path)) == 0:
        rmdir(node_object_dir_path)
    except:
      pass

  def on_created(self, fse: DirCreatedEvent | FileCreatedEvent) -> None:
    if fse.is_synthetic or fse.is_directory:
      return
    
    if match(self.filter_path_regex, fse.src_path) is None:
      return
    
    self.compilation_cache.add_entry(fse.src_path)
    node = self.compile_graph.insert_node(fse.src_path)
    self.compile_queue.enqueue(node)

    print(f"{node.key} created")
    if self.options["MODE"] == "AR":
      if self.recompile(True):
        self.compilation_cache.dump()
  
  def on_deleted(self, fse: DirDeletedEvent | FileDeletedEvent) -> None:
    deleted_nodes = []
    if fse.is_synthetic or fse.is_directory:
      deleted_nodes = self.compile_graph.get_all_sub_nodes(fse.src_path)
      if len(deleted_nodes) == 0:
        return
    elif match(self.filter_path_regex, fse.src_path) is None:
      return
    else:
      deleted_nodes = [self.compile_graph.get_node(fse.src_path)]

    for node in deleted_nodes:
      self.compilation_cache.remove_entry(node.key)
      self.delete_node_compilation_artifact(node)
      for included_in in node.included_in:
        self.compile_queue.enqueue(included_in)
      self.compile_graph.remove_node(node.key)
      self.compile_queue.remove(node.key)

    if self.compile_queue.is_empty() or self.recompile(True):
      self.compilation_cache.dump()


  def on_moved(self, fse: DirMovedEvent | FileMovedEvent) -> None:
    if match(self.filter_path_regex, fse.src_path) is None:
      return
    
    print(f"{fse.src_path} moved to {fse.dest_path}")

    self.compile_queue.remove(fse.src_path)
    self.compilation_cache.move_entry(fse.src_path, fse.dest_path)
    self.delete_node_compilation_artifact(self.compile_graph.get_node(fse.src_path))
    node = self.compile_graph.move_node(fse.src_path, fse.dest_path)
    print(node.key)
    self.compile_queue.enqueue(node)

    if self.options["MODE"] == "AR":
      if self.recompile(True):
        self.compilation_cache.dump()

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if fse.is_directory or fse.is_synthetic:
      return

    if match(self.filter_path_regex, fse.src_path) is None or self.compilation_cache.cache_table[fse.src_path].is_up_to_date():
      return
    
    node = self.compile_graph.update_node(fse.src_path)
    self.compilation_cache.update_entry(node.key)
    self.compile_queue.enqueue(node)
    
    if self.options["DEBUG"]:
      print(f"{node.key} modified")

    if self.options["MODE"] == "AR":
      if self.recompile(True):
        self.compilation_cache.dump()

  def start(self):
    if self.options["MODE"] == "AR" and not self.compile_queue.is_empty():
      if self.recompile(False):
        if self.link_target():
          self.compilation_cache.dump()

    observer = Observer()
    observer.schedule(self, self.working_dir, recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    observer.join()


