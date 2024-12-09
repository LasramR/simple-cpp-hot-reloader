from subprocess import Popen, PIPE
from threading import Thread
from typing import List, IO, Union, Callable, TypedDict

class AsyncProcessOptions (TypedDict) :
  name: str
  logger: Union[Callable[[str], None], None]
  stdout_logger: Union[Callable[[str], None], None]
  stderr_logger: Union[Callable[[str], None], None]
  on_success: Callable[[], None]
  on_error: Callable[[], None]

class AsyncProcess:

  _command_thread : Union[Thread, None] = None
  _command_process : Union[Popen, None] = None

  def __init__(self, command : List[str], options : AsyncProcessOptions):
    self._command = command
    self._options = options
    self._trigger_callback = True

  def is_running(self) -> bool :
    return not self._command_thread is None and self._command_thread.is_alive()

  def run(self) -> None :
    """
    This will block if self._command_thread is alive, for restart, consider self.terminate_and_run
    """
    if self.is_running():
      self._command_thread.join()

    if "logger" in self._options:
      self._options["logger"](f'starting process: "{self._options["name"]}"')

    self._command_process = Popen(
      self._command,
      stdout=PIPE if "stdout_logger" in self._options else None,
      stderr=PIPE if "stderr_logger" in self._options else None,
      text=True
    )

    self._command_thread = Thread(target=self._watch_process)
    self._command_thread.start()

  def terminate(self) -> None :
    if not self.is_running():
      return
    
    self._trigger_callback = False
    
    if self._command_process:
      self._command_process.terminate()
    
    self._command_thread.join()

    if "logger" in self._options:
      self._options["logger"](f'process "{self._options["name"]}" terminated by force')

    self._trigger_callback = True

  def run_with_command(self, new_command: List[str]) -> None :
    self._command = new_command
    self.run()

  def terminate_and_run(self) -> None:
    self.terminate()
    self.run()

  def _watch_process(self) -> None :
    
    stream_threads : List[Thread] = []
    if "stdout_logger" in self._options:
      stream_threads.append(Thread(target=self._watch_stream, args=[self._command_process.stdout, self._options["stdout_logger"]]))
    if "stderr_logger" in self._options:
      stream_threads.append(Thread(target=self._watch_stream, args=[self._command_process.stderr, self._options["stderr_logger"]]))

    for t in stream_threads:
      t.start()
    exit_code = self._command_process.wait()
    self._command_process = None
    for t in stream_threads:
      t.join()

    if "logger" in self._options:
      self._options["logger"](f'process "{self._options["name"]}" returned with exit code {exit_code}.')
    
    if self._trigger_callback:
      if exit_code == 0 and "on_success" in self._options: 
        self._options["on_success"]()
      elif "on_error" in self._options:
        self._options["on_error"]()

  def _watch_stream(self, stream : IO[str], log_func : Callable[[str], None]) -> None :
    try:
      for line in iter(stream.readline, ''):
        log_func(line.strip())
    finally:
      stream.close()
