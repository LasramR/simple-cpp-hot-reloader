from os import path, remove, rmdir, listdir
from re import match
from signal import signal, SIGINT

from watchdog.events import DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileMovedEvent, FileSystemEvent, RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .options import SimpleCppHotReloaderOptions
from .utils.logger import Logger, LoggerOptions
from .utils.cpp import CppUtils
from .compilation.compilation_graph import CompilationGraph
from .multithreading.async_process import AsyncProcess
from .cache.compilation_cache import CompilationCache

class HotReloader(RegexMatchingEventHandler):

  def __init__(self, options : SimpleCppHotReloaderOptions):
    self._options = options
    self._cpp = CppUtils(self._options)
    self._logger = Logger(LoggerOptions.DefaultWithName("schr"))

    self._target_logger = Logger({"NAME": self._options["TARGET"], "SUCCESS_COLOR": "GREEN", "INFO_COLOR": "WHITE", "ERROR_COLOR": "MAGENTA", "WARN_COLOR": "CYAN"})
    self._target_process = AsyncProcess(
      self._cpp.get_target_command(),
      {
        "name": self._options["TARGET"],
        "logger": lambda l: self._target_logger.warn(l),
        "stdout_logger": lambda l: self._target_logger.info(l),
        "stderr_logger": lambda l: self._target_logger.error(l),
      }
    )

    self._logger.info(f"computing include graph of project \"{self._options['WORKING_DIR']}\"")
    self._compilation_graph = CompilationGraph(self._options, self._cpp, self._logger, self._on_compilation_graph_build_success)
    self._logger.success(f"ok")

    self._logger.info(f"initializing cshr cache with \"{self._cpp.get_compilation_cache_file_path()}\"")
    self._compilation_cache = CompilationCache(self._compilation_graph, self._cpp.get_compilation_cache_file_path())
    self._logger.success(f"ok")

    try:
      for outdated_node in self._compilation_cache.get_all_outdated_nodes():
        self._logger.warn(f"{outdated_node.key} seems out of date and will be recompiled")
        self._compilation_graph.mark_node_as_outdated(outdated_node)
    except:
      self._logger.error("could not read cache file correctly")

    super().__init__()

  def _on_compilation_graph_build_success(self) -> None:
    self._compilation_cache.write_to_cache_file()
    if 'R' in self._options["MODE"]:
      self._target_process.terminate_and_run()

  def on_created(self, fse: DirCreatedEvent | FileCreatedEvent) -> None:
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    node_key = fse.src_path
    node = self._compilation_graph.insert_node(node_key, True)
    self._compilation_cache.insert_node(node)
    
    self._logger.info(f"{node.key} created")

  def on_deleted(self, fse: DirDeletedEvent | FileDeletedEvent) -> None:
    deleted_nodes = []

    if fse.is_synthetic or fse.is_directory:
      deleted_nodes = self._compilation_graph.get_all_sub_nodes(fse.src_path)
      if len(deleted_nodes) == 0:
        return
      self._logger.warn(f"directory {fse.src_path} deleted")
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    else:
      deleted_nodes = [self._compilation_graph.get_node(fse.src_path)]
      self._logger.warn(f"{fse.src_path} deleted")


    for node in deleted_nodes:
      self._compilation_graph.remove_node(node.key)
      self._compilation_cache.remove_node(node.key)
      self._cpp.clean_object_file(node.key)

  def on_moved(self, fse: DirMovedEvent | FileMovedEvent) -> None:
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    old_node_key = fse.src_path
    moved_node_key = fse.dest_path

    self._logger.warn(f"{old_node_key} moved to {moved_node_key}")

    node = self._compilation_graph.move_node(old_node_key, moved_node_key)
    self._compilation_cache.move_node(old_node_key, node)
    self._cpp.clean_object_file(old_node_key)

    if "C" in self._options["MODE"]:
      self._compilation_graph.build()

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    node_key = fse.src_path

    if self._compilation_cache.is_node_up_to_date(node_key):
      return

    self._compilation_cache.update_node(node_key)
    node = self._compilation_graph.update_node(node_key)
    
    self._logger.info(f"{node.key} modified")

    if "C" in self._options["MODE"]:
      self._compilation_graph.build()

  def start(self):
    self._logger.info(f"running first round")

    if self._options["MODE"] == "R":
      self._logger.warn("you are using R (Run) mode only. This will only start your target once and only if it is already compiled. If that’s all you’re after, then you're all set—no compilation, no re-linking, just a good old execution!")
      if self._cpp.is_target_built():
        self._on_compilation_graph_build_success() 

    if "C" in self._options["MODE"]:
      self._compilation_graph.build() or self._on_compilation_graph_build_success() 

    self._logger.success(f"ok")


    self._logger.info(f"watching project \"{self._options['WORKING_DIR']}\"")
    observer = Observer()
    observer.schedule(self, self._options["WORKING_DIR"], recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    self._logger.success("ok")

    observer.join()
