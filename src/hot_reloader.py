from os import path, remove, rmdir, listdir
from re import match
from signal import signal, SIGINT

from watchdog.events import DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileMovedEvent, FileSystemEvent, RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .options import SimpleCppHotReloaderOptions
from .compilation.compilation_graph import CompilationGraph
from .multithreading.async_process import AsyncProcess
from .utils.logger import Logger, LoggerOptions
from .utils.cpp import CppUtils

class HotReloader(RegexMatchingEventHandler):

  def __init__(self, options : SimpleCppHotReloaderOptions):
    self._options = options
    self._cpp = CppUtils(self._options)
    self._logger = Logger(LoggerOptions.DefaultWithName("schr"))

    self._target_logger = Logger({"NAME": self._options["TARGET"], "INFO_COLOR": "WHITE", "ERROR_COLOR": "MAGENTA", "WARN_COLOR": "CYAN"})
    self._target_process = AsyncProcess(
      self._cpp.get_target_command(),
      {
        "name": self._options["TARGET"],
        "logger": lambda l: self._target_logger.warn(l),
        "stdout_logger": lambda l: self._target_logger.info(l),
        "stderr_logger": lambda l: self._target_logger.error(l),
      }
    )

    self.compilation_graph = CompilationGraph(self._options, self._cpp, self._logger, self._run_target)
    
    # self.compilation_cache = CompilationCache(f"{self.working_dir}{sep}.simple-cpp-hr.cache", watched_files.copy())

    #
    # for outdated_cca in self.compilation_cache.get_all_outdated_artifacts():
    #   initialQueueSet.add(self.compilation_graph.get_node(outdated_cca.file_path))
    # command = [target_executable_path, *(self._options["TARGET_ARGS"].split(" ") if len(self._options["TARGET_ARGS"]) else [])]

    super().__init__()
  
  #def delete_node_compilation_artifact(self, node : CompilationGraphSimpleNode) -> None :
  #  try:
  #    remove(node.object_file_path)
  #  except:
  #    pass
  #  try:
  #    node_object_dir_path = path.dirname(node.object_file_path)
  #    if len(self._options["OBJ_DIR"]) and len(listdir(node_object_dir_path)) == 0:
  #      rmdir(node_object_dir_path)
  #  except:
  #    pass

  def _run_target(self) -> None:
    if 'R' in self._options["MODE"]:
      self._target_process.terminate_and_run()

  def on_created(self, fse: DirCreatedEvent | FileCreatedEvent) -> None:
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    # self.compilation_cache.add_entry(fse.src_path)
    node = self.compilation_graph.insert_node(fse.src_path)

    self._logger.info(f"{node.key} created")
    
    if "C" in self._options["MODE"]:
      self.compilation_graph.build()
        # self.compilation_cache.dump()
        # if "R" in self._options["MODE"]:
        #   self.run_target()
  
  def on_deleted(self, fse: DirDeletedEvent | FileDeletedEvent) -> None:
    deleted_nodes = []

    if fse.is_synthetic or fse.is_directory:
      deleted_nodes = self.compilation_graph.get_all_sub_nodes(fse.src_path)
      if len(deleted_nodes) == 0:
        return
      self._logger.warn(f"directory {fse.src_path} deleted")
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    else:
      deleted_nodes = [self.compilation_graph.get_node(fse.src_path)]
      self._logger.warn(f"{fse.src_path} deleted")


    for node in deleted_nodes:
      # self.compilation_cache.remove_entry(node.key)
      # self.delete_node_compilation_artifact(node)
      self.compilation_graph.remove_node(node.key)

  def on_moved(self, fse: DirMovedEvent | FileMovedEvent) -> None:
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    self._logger.warn(f"{fse.src_path} moved to {fse.dest_path}")

#    self.compilation_cache.move_entry(fse.src_path, fse.dest_path)
 #   self.delete_node_compilation_artifact(self.compilation_graph.get_node(fse.src_path))
    node = self.compilation_graph.move_node(fse.src_path, fse.dest_path)

    if "C" in self._options["MODE"]:
      self.compilation_graph.build()
#        self.compilation_cache.dump()
#        if "R" in self._options["MODE"]:
#          self.run_target()  

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if not self._cpp.is_cpp_source_file(fse.src_path):
      return
    
    node = self.compilation_graph.update_node(fse.src_path)
    #self.compilation_cache.update_entry(node.key)
    
    self._logger.info(f"{node.key} modified")

    if "C" in self._options["MODE"]:
      self.compilation_graph.build()
    #    self.compilation_cache.dump()
    #    if "R" in self._options["MODE"]:
    #      self.run_target()  

  def start(self):
    if "C" in self._options["MODE"]:
      self.compilation_graph.build()
#      if self.compile_queue.is_empty() or self.recompile(True):
#        self.compilation_cache.dump()
    if self._options["MODE"] == "R":
      self._logger.warn("You are using R (Run) mode only. This will only start your target once and only if it is already compiled. If that’s all you’re after, then you're all set—no compilation, no re-linking, just a good old execution!")

    if self._cpp.is_target_built():
      self._run_target() 

    observer = Observer()
    observer.schedule(self, self._options["WORKING_DIR"], recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    observer.join()


