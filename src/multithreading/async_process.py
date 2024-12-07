from subprocess import Popen, PIPE
from threading import Thread
from typing import List, IO, Union, Callable, Any

from ..utils.logger import Logger

class AsyncProcess:
  """
  Asynchronously run a shell command
  """

  _command_thread : Union[Thread, None]
  _command_process : Union[Popen, None]
  _success_callback : Union[Callable[[], None], None]
  _error_callback : Union[Callable[[], None], None]

  def __init__(self, command : List[str], logger : Union[Logger, None] , monitor_stdout : bool = False, monitor_stderr : bool = False, success_callback : Callable[[], None] = None, error_callack : Callable[[], None] = None, success_exit_code : int = 0, debug : bool = True):
    self.command = command
    self.logger = logger
    self.monitor_stdout = not self.logger is None and monitor_stdout
    self.monitor_stderr = not self.logger is None and monitor_stderr
    self.success_exit_code = success_exit_code
    self.debug = debug

    self._success_callback = success_callback
    self._error_callback = error_callack
    self._trigger_callback = True
    self._command_thread = None
    self._command_process = None
    
  def run(self) -> None:
    """
    This will block if self._command_thread is alive, for restart, consider self.terminate_and_run
    """

    if self._command_thread:
      self._command_thread.join()

    if self.debug:
      self.logger.info(f'starting process: "{" ".join(self.command)}"')
    
    self._command_thread = Thread(
      target=self._watch_process,
      args=[Popen(self.command, stdout=PIPE if self.monitor_stdout else None, stderr=PIPE if self.monitor_stderr else None, text=True)]
    )
    self._command_thread.start()

  def run_with_command(self, new_command: List[str]) -> None :
    self.command = new_command
    self.run()

  def terminate(self) -> None:
    self._trigger_callback = False
    if self._command_thread is None or not self._command_thread.is_alive():
      self._command_thread = None
      return
    
    if self._command_process:
      self._command_process.terminate()
      self._command_thread.join()
      self._command_thread = None
    
    if self.debug:
      self.logger.info(f'process "{" ".join(self.command)}" terminated by force')
    self._trigger_callback = True

  def terminate_and_run(self) -> None:
    if not self._command_thread is None:
      self.terminate()
    self.run()

  def _watch_process(self, command_process : Popen) -> None :
    self._command_process = command_process
    
    stream_threads : List[Thread] = []
    if self.monitor_stdout:
      stream_threads.append(Thread(target=self._watch_process, args=[self._command_process.stdout, self.logger, False]))
    if self.monitor_stderr:
      stream_threads.append(Thread(target=self._watch_process, args=[self._command_process.stderr, self.logger, True]))

    map(lambda t : t.start(), stream_threads)
    exit_code = self._command_process.wait()
    map(lambda t : t.join(), stream_threads)

    if self.debug:
      self.logger.warn(f'process "{" ".join(self.command)}" returned with exit code {exit_code}.')
    
    self._command_process = None

    if self._trigger_callback:
      if not self._success_callback is None and self.success_exit_code == exit_code:
        self._success_callback()
      elif not self._error_callback is None and self.success_exit_code != exit_code:
        self._error_callback()

  def _watch_stream(self, stream : IO[str], logger: Logger, is_error_stream : bool = False) -> None :
    try:
      for line in iter(stream.readline(), ''):
        log = line.strip()
        if is_error_stream:
          logger.error(log)
        else:
          logger.info(log)

    finally:
      stream.close()
