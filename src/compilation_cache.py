from hashlib import blake2b
from os import path
from typing import List, Union

class CompilationCacheArtifact:

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

class CompilationCache:

  def __init__(self, compilation_cache_file_path : str, watched_file_paths : List[str]):
    self.compilation_cache_file_path = compilation_cache_file_path
    self.old_cache_table = {cca.file_path: cca for cca in self.read_cache_file()}
    self.cache_table = {wfp: CompilationCacheArtifact(wfp) for wfp in watched_file_paths}

  def read_cache_file(self) -> List[CompilationCacheArtifact]:
    if not path.exists(self.compilation_cache_file_path):
      return []

    artifacts = []
    with open(self.compilation_cache_file_path, "r") as fd:
      for line in fd.readlines():
        file_path, file_hash = line.replace("\n", "").split(":")
        artifacts.append(CompilationCacheArtifact(file_path, file_hash))
    return artifacts

  def remove_entry(self, artifact_path : str) -> None :
    if artifact_path in self.cache_table:
      del self.cache_table[artifact_path]

  def update_entry(self, artifact_path : str) -> None :
    if artifact_path in self.cache_table:
      self.cache_table[artifact_path].update()

  def add_entry(self, artifact_path : str) -> None :
    if not artifact_path in self.cache_table:
      self.cache_table[artifact_path] = CompilationCacheArtifact(artifact_path)

  def move_entry(self, old_artifact_path : str, new_artifact_path : str) -> None:
    self.remove_entry(old_artifact_path)
    self.add_entry(new_artifact_path)

  def get_all_outdated_artifacts(self) -> List[CompilationCacheArtifact]:
    outdated = []
    for cca in self.old_cache_table:
      if cca in self.cache_table and self.old_cache_table[cca].hash_cache != self.cache_table[cca].hash_cache:
        outdated.append(self.old_cache_table[cca])
    return outdated

  def dump(self):
    with open(self.compilation_cache_file_path, "w") as fd:
      for cca in self.cache_table:
        fd.write(f"{cca}:{self.cache_table[cca].hash()}\n")
    self.old_cache_table = self.cache_table