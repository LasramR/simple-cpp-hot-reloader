from os import sep, makedirs, path, remove, rmdir, listdir
from subprocess import run, Popen, PIPE
from re import match
from signal import signal, SIGINT
from threading import Thread
from typing import IO

from watchdog.events import DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileMovedEvent, FileSystemEvent, RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .options import SimpleCppHotReloaderOptions
from .compilation_cache import CompilationCache
from .compilation_graph import CompilationGraph, CompilationGraphSimpleNode
from .compilation_queue import CompilationQueue
from .utils import get_all_files_in_dir, change_file_ext, get_relative_path_from, file_ext_regex
from .logger import Logger, LoggerOptions

class HotReloader(RegexMatchingEventHandler):

  def __init__(self, working_dir : str, options : SimpleCppHotReloaderOptions):
    self.working_dir = working_dir
    self.options = options
    self.logger = Logger(LoggerOptions.DefaultWithName("schr"))

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

    self.target_child_process = None
    self.target_logger = Logger({"NAME": self.options["TARGET"], "INFO_COLOR": "WHITE", "ERROR_COLOR": "MAGENTA", "WARN_COLOR": "YELLOW"})
    self.target_monitor_thread = None

    self.filter_path_regex = file_ext_regex([*self.options['CXX_FILE_EXTS'], *self.options['HXX_FILE_EXTS']])
    super().__init__()

  def print_target_output(self, stream : IO[str], error_stream : bool) -> None:
    try:
      for line in iter(stream.readline, ''):
        if error_stream:
          self.target_logger.error(line.strip())
        else:
          self.target_logger.info(line.strip())
    finally:
      stream.close()

  def monitor_target(self) -> None:
    if self.target_child_process is None:
      return
    
    target_stdout_thread = Thread(target=self.print_target_output, args=(self.target_child_process.stdout, False))
    target_stderr_thread = Thread(target=self.print_target_output, args=(self.target_child_process.stderr, True))

    target_stdout_thread.start()
    target_stderr_thread.start()

    target_exit_code = self.target_child_process.wait()
    target_stdout_thread.join()
    target_stderr_thread.join()

    self.logger.warn(f"Target {self.options['TARGET']} return with exit code {target_exit_code}.")
    self.target_child_process = None

  def run_target(self) -> bool :
    if not self.target_child_process is None:
      self.target_child_process.terminate()
      
      if not self.target_monitor_thread is None and self.target_monitor_thread.is_alive():
        self.target_monitor_thread.join()

      self.target_monitor_thread = None
      self.target_child_process = None
      self.logger.warn(f"target {self.options["TARGET"]} terminated by force")

    target_executable_path = path.abspath(path.join(self.working_dir, self.options["TARGET"]))
    
    command = [target_executable_path, *(self.options["TARGET_ARGS"].split(" ") if len(self.options["TARGET_ARGS"]) else [])]

    self.logger.info(f'restarting target: "{" ".join(command)}"')
    self.target_child_process = Popen(command, stdout=PIPE, stderr=PIPE, text=True)
    self.target_monitor_thread = Thread(target=self.monitor_target)
    self.target_monitor_thread.start()

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
      self.logger.info(" ".join(command))

    if run(command).returncode == 0:
      self.logger.info(f"target {self.options['TARGET']} relinked")
      return True
    else:
      self.logger.error(f"target {self.options['TARGET']} linking error")
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
        self.logger.info(" ".join(command))

      if run(command, stdout=None).returncode == 0:
        self.logger.info(f"{node.key} recompiled")
      else:
        self.logger.error(f"{node.key} compilation error")
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

    self.logger.info(f"{node.key} created")
    if "C" in self.options["MODE"]:
      if self.recompile(True):
        self.compilation_cache.dump()
        if "R" in self.options["MODE"]:
          self.run_target()
  
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

    if self.compile_queue.is_empty():
        self.compilation_cache.dump()
        if "C" in self.options["MODE"]:
          self.recompile(True)
          if "R" in self.options["MODE"]:
            self.run_target()


  def on_moved(self, fse: DirMovedEvent | FileMovedEvent) -> None:
    if match(self.filter_path_regex, fse.src_path) is None:
      return
    
    self.logger.warn(f"{fse.src_path} moved to {fse.dest_path}")

    self.compile_queue.remove(fse.src_path)
    self.compilation_cache.move_entry(fse.src_path, fse.dest_path)
    self.delete_node_compilation_artifact(self.compile_graph.get_node(fse.src_path))
    node = self.compile_graph.move_node(fse.src_path, fse.dest_path)
    self.compile_queue.enqueue(node)

    if "C" in self.options["MODE"]:
      if self.recompile(True):
        self.compilation_cache.dump()
        if "R" in self.options["MODE"]:
          self.run_target()  

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if fse.is_directory or fse.is_synthetic:
      return

    if match(self.filter_path_regex, fse.src_path) is None or self.compilation_cache.cache_table[fse.src_path].is_up_to_date():
      return
    
    node = self.compile_graph.update_node(fse.src_path)
    self.compilation_cache.update_entry(node.key)
    self.compile_queue.enqueue(node)
    
    if self.options["DEBUG"]:
      self.logger.info(f"{node.key} modified")

    if "C" in self.options["MODE"]:
      if self.recompile(True):
        self.compilation_cache.dump()
        if "R" in self.options["MODE"]:
          self.run_target()  

  def start(self):
    if "C" in self.options["MODE"]:
      if self.compile_queue.is_empty() or self.recompile(True):
        self.compilation_cache.dump()

    if self.options["MODE"] == "R":
      self.logger.warn("You are using R (Run) mode only. This will only start your target once and only if it is already compiled. If that’s all you’re after, then you're all set—no compilation, no re-linking, just a good old execution!")

    if "R" in self.options["MODE"] and path.exists(path.abspath(path.join(self.working_dir, self.options["TARGET"]))):
      self.run_target()            

    observer = Observer()
    observer.schedule(self, self.working_dir, recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    observer.join()


