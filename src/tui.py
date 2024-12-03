from textual.app import App, ComposeResult
from textual import events
from textual.widgets import Static, Footer
from textual.containers import Horizontal, Vertical

class Tui(App):
    
    CSS_PATH = "tui.tcss"
    
    def compose(self) -> ComposeResult:
      with Vertical():
        with Horizontal():
          yield Static("Compilation History", classes="box")
          yield Static("Compile queue", classes="box")
        yield Static("Execution")

    def on_mount(self) -> None:
      pass

    def on_key(self, event: events.Key) -> None:
      pass

if __name__ == "__main__":
    app = Tui()
    app.run()