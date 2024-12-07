from subprocess import Popen, PIPE, run
from typing import List
from .fs import sanitize_file_extensions

def run_piped_command(commands : List[List[str]], printCmd : bool = False) -> List[str]:
  if printCmd:
    print(" | ".join(map( lambda e : " ".join(e), commands)))

  prevStdout = None
  for c in commands:
    cp = Popen(c, stdin=prevStdout, stdout=PIPE, stderr=PIPE)
    prevStdout = cp.stdout

  return list(map(lambda l : l.decode().strip("\n\r"), prevStdout.readlines()))

def is_valid_command(command : str) -> bool:
  try:
    result = run(
        ["which", command],
        stdout=PIPE,
        stderr=PIPE,
        text=True
    )
    return result.returncode == 0
  except Exception:
      return False
  
def grep_file_extensions_regex(file_extensions : List[str]) -> str :
  if not len(file_extensions):
    raise ValueError("grep_file_extensions_regex: file_extensions must be a non empty list")
  
  sanitized_file_extensions = sanitize_file_extensions(file_extensions)

  if len(sanitized_file_extensions) == 1:
    return rf"\".*\.{sanitized_file_extensions[0].strip('.')}\""

  return rf"\".*\.({'|'.join(sanitized_file_extensions)})\""