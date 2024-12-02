#!/usr/bin/python3

from os import getcwd, walk, sep, path
from hashlib import blake2b
from signal import signal, SIGINT
from typing import Callable, List, Dict, TypedDict, Union
from re import Pattern, match
import subprocess
import argparse

from watchdog.events import DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent, FileSystemEvent, RegexMatchingEventHandler
from watchdog.observers import Observer

class Arguments(TypedDict):
    CXX: str
    CFLAGS: Union[str, None]
    LDFLAGS: Union[str, None]
    OBJ_DIR: Union[str, None]
    TARGET: str

argvParser = argparse.ArgumentParser(description="Simple CPP Hot Reloader")
argvParser.add_argument("-c", "--compiler", help="C compiler", required=False)
argvParser.add_argument("-cf", "--cflags", metavar='="CFLAGS ..."', help='CPP Compiler flags, use it with direct affectation and quoted strings (e.g. "-cf=-std=c++20")', required=False)
argvParser.add_argument("-ld", "--ldflags", metavar='="LFLAGS ..."', help='CPP Compiler linker flags, use it with direct affectation and quoted strings (e.g. "-ld=-lpthread")', required=False)
argvParser.add_argument("-od", "--obj-dir", help="Object files output directory", required=False)
argvParser.add_argument("-t", "--target", help="Target executable name", required=True)

working_dir = getcwd()

class Artifact:

  def __init__(self, file_path : str, file_hash : Union[str, None] = None):
    self.file_path = file_path
    self.hash_cache = self.hash() if file_hash == None else file_hash

  def hash(self):
    file_hash = blake2b()
    with open(self.file_path, "rb") as fd:
      while chunk := fd.read(8192):
        file_hash.update(chunk)
    return file_hash.digest().hex()
  
  def is_up_to_date(self):
    return self.hash_cache == self.hash()
  
  def update(self):
    self.hash_cache = self.hash()

class Cache:
  def __init__(self, cache_file_path : str, artifact_paths : List[str]):
    self.cache_file_path = cache_file_path
    self.old_cache_table = {a.file_path: a for a in self.read_cache_file()}
    self.cache_table = {a: Artifact(a) for a in artifact_paths}

  def read_cache_file(self) -> List[Artifact]:
    if not path.exists(self.cache_file_path):
      return []

    artifacts = []
    with open(self.cache_file_path, "r") as fd:
      for line in fd.readlines():
        file_path, file_hash = line.replace("\n", "").split(":")
        artifacts.append(Artifact(file_path, file_hash))
    return artifacts

  def remove_entry(self, artifact_path : str):
    if artifact_path in self.cache_table:
      del self.cache_table[artifact_path]

  def update_entry(self, artifact_path : str):
    if artifact_path in self.cache_table:
      self.cache_table[artifact_path].update()

  def add_entry(self, artifact_path : str):
    if not artifact_path in self.cache_table:
      self.cache_table[artifact_path] = Artifact(artifact_path)

  def get_all_outdated_artifacts(self) -> List[str]:
    outdated = []
    for artifact in self.old_cache_table:
      if artifact in self.cache_table and self.old_cache_table[artifact].hash_cache != self.cache_table[artifact].hash_cache:
        outdated.append(artifact)
    return outdated

  def dump(self):
    with open(self.cache_file_path, "w") as fd:
      for artifact in self.cache_table:
        fd.write(f"{artifact}:{self.cache_table[artifact].hash()}\n")
    self.old_cache_table = self.cache_table

class CompilationQueue:
  
  def __init__(self, artifact_paths_to_compile : List[str], compile_single_command : Callable[[str], None]):
    self.queue = [*artifact_paths_to_compile]
    self.queue_values = {}
    self.compile_single_command = compile_single_command
  
  def enqueue(self, artifact : str):
    if artifact in self.queue_values:
      self.queue.remove(artifact)
    
    self.queue.append(artifact)
    self.queue_values[artifact] = True
  
  def dequeue(self) -> Union[str, None]:
    if len(self.queue) == 0:
      return None
    artifact = self.queue.pop()
    del self.queue_values[artifact]
    return artifact
  
  def process(self, n = -1) -> int:
    if n < 0:
      n = len(self.queue)
    
    for i in range(0, n):
      if artifact := self.dequeue():
        self.compile_single_command(artifact)
      return i + 1

    return n

def get_all_matching_file_in_dir(working_dir : str, patterns : List[Pattern], recursive = True) -> List[str]:
  matching_files = []
  for (dirPath, _, fileNames) in walk(working_dir):
    for p in patterns:
      for f in fileNames:
        if match(p, f):
          matching_files.append(f"{dirPath}{sep}{f}")
  return matching_files

def compile_command(src_file : str, options : Arguments) -> None:
  command = [
    options["CXX"],
    *(options["CFLAGS"].split(" ") or []),
    "-c",
    src_file,
    "-o",
    f"{src_file}.o" if options["OBJ_DIR"] == None else "a.o",
    *(options["LDFLAGS"] or [])
  ]

  print(" ".join(command))
  if subprocess.run(command).returncode == 0:
    print(f"{src_file} recompiled!")

class HotReloader:

  def __init__(self, working_dir : str, options : Arguments, patterns : List[Pattern]):
    self.working_dir = working_dir
    self.options = options
    self.patterns = patterns

    self.cache = Cache(f"{self.working_dir}{sep}.simple-cpp-hr.cache", get_all_matching_file_in_dir(self.working_dir, self.patterns))
    self.compile_queue = CompilationQueue(self.cache.get_all_outdated_artifacts(), lambda src_file : compile_command(src_file, self.options))
    self.observer = Observer()
    self.observer.schedule(fsEventHandler(self, regexes=self.patterns), self.working_dir, recursive=True)
    super()

  def recompile_artifact(self, file_path : str) -> bool :
    artifact = self.cache.cache_table[file_path]

    if not artifact.is_up_to_date():
      print(f"{file_path} modified")
      self.cache.update_entry(file_path)
      self.compile_queue.enqueue(file_path)
      self.compile_queue.process(1)

  def monitor(self):
    self.observer.start()
    signal(SIGINT, lambda _a, _b: self.observer.stop() or print())
    self.observer.join()

class fsEventHandler(RegexMatchingEventHandler):
  
  def __init__(self, hot_reloader : HotReloader, regexes = []):
    self.hot_reloader = hot_reloader
    super().__init__(regexes=regexes)

  def on_created(self, fse : DirCreatedEvent | FileCreatedEvent) -> None:
    if fse.is_directory:
      return
    
    self.hot_reloader.cache.add_entry(fse.src_path)
    self.hot_reloader.recompile_artifact(fse.src_path)

  def on_modified(self, fse : DirModifiedEvent | FileModifiedEvent) -> None:
    if fse.is_directory:
      return

    self.hot_reloader.recompile_artifact(fse.src_path)

def is_valid_shell_command(command):
    try:
        result = subprocess.run(
            ["which", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

if __name__ == "__main__":
  CXX_EXT_RE = list(map(lambda ext: rf"^.*{ext.replace(".", "\\.")}$", [".cpp", ".cc", ".c"]))
  HXX_EXT_RE = list(map(lambda ext: rf"^.*{ext.replace(".", "\\.")}$", [".hpp", ".h"]))

  args = argvParser.parse_args()

  hot_reload_options : Arguments = {
    "CXX": "g++",
    "CFLAGS": args.cflags if args.cflags else "",
    "LDFLAGS": args.ldflags if args.ldflags else "",
    "OBJ_DIR": None,
    "TARGET": args.target
  }

  if cxx := args.compiler:
    if not is_valid_shell_command(cxx):
      args.error('invalid -c usage, please provide a valid compiler (e.g. "g++", "clang++").')
    hot_reload_options["CXX"] = cxx

  if od := args.obj_dir:
    hot_reload_options["OBJ_DIR"] = od
  
  HotReloader(working_dir, hot_reload_options, [*CXX_EXT_RE, *HXX_EXT_RE]).monitor()

# python simple-cpp-hr.py -t hello -c gcc -cf =-std=c++20 -od ./bin -ld=-lpthread
