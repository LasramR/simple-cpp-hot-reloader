from os import sep, makedirs, path
from subprocess import run
from signal import signal, SIGINT

from watchdog.events import RegexMatchingEventHandler, DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .options import SimpleCppHotReloaderOptions
from .compilation_cache import CompilationCache
from .compilation_graph import CompilationGraph
from .compilation_queue import CompilationQueue
from .utils import get_all_files_in_dir, change_file_ext, get_relative_path_from, file_ext_regex

class HotReloader(RegexMatchingEventHandler):

  def __init__(self, working_dir : str, options : SimpleCppHotReloaderOptions):
    self.working_dir = working_dir
    self.options = options

    watched_files =  get_all_files_in_dir(self.working_dir, [*self.options["CXX_FILE_EXTS"], *self.options["HXX_FILE_EXTS"]])
    self.cache = CompilationCache(f"{self.working_dir}{sep}.simple-cpp-hr.cache", watched_files)
    self.compile_graph = CompilationGraph(self.working_dir, watched_files, self.options)
    self.compile_queue = CompilationQueue([self.compile_graph.get_node(cca) for cca in self.cache.get_all_outdated_artifacts()])
    super().__init__(regexes=file_ext_regex([*self.options['CXX_FILE_EXTS'], *self.options['HXX_FILE_EXTS']]))

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent):
    if fse.is_directory or self.cache.cache_table[fse.src_path].is_up_to_date():
      return
    
    node = self.compile_graph.get_node(fse.src_path)

    if self.options["MODE"] == "AR":
      print(f"{node.key} modified")

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

      print(" ".join(command))
      if run(command).returncode == 0:
        print(f"{node.key} recompiled!")
        self.cache.update_entry(node.key)
        self.cache.dump()
    else:
      self.compile_queue.enqueue(node)

  def start(self):
    observer = Observer()
    observer.schedule(self, self.working_dir, recursive=True)
    observer.start()
    signal(SIGINT, lambda _a, _b: observer.stop() or print())
    observer.join()


