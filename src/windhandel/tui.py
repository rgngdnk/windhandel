import asyncio
import httpx
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Header, Footer, Static, Input, LoadingIndicator
from textual.message import Message
from textual.containers import Horizontal

API_BASE = "http://127.0.0.1:8000"


MNEMONICS = {}


class CommandBar(Horizontal):
    """Reusable 4-letter mnemonic input, dockable at the bottom of any screen."""

    DEFAULT_CSS = """
    CommandBar {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    CommandBar Input {
        width: 12;
    }
    """

    class Submitted(Message):
        def __init__(self, code: str) -> None:
            self.code = code
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="MNEM", max_length=4)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        code = event.value.strip().upper()
        event.input.value = ""
        self.post_message(self.Submitted(code))


class LoadingScreen(Screen):
    class Ready(Message):
        """Posted when the health check succeeds."""

    def compose(self) -> ComposeResult:
        yield Static("Starting API — please wait...", id="status")
        yield LoadingIndicator()

    async def on_mount(self) -> None:
        self.run_worker(self.wait_for_api(), exclusive=True)

    async def wait_for_api(self) -> None:
        async with httpx.AsyncClient() as client:
            for _ in range(60):
                try:
                    r = await client.get(f"{API_BASE}/health", timeout=1)
                    if r.status_code == 200:
                        self.post_message(self.Ready())
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(0.5)
            self.query_one("#status", Static).update("API failed to start.")


class HomeScreen(Screen):
    CSS = """
    #title {
        content-align: center middle;
        text-style: bold;
        height: 5;
    }
    #fluff {
        content-align: center middle;
        color: $text-muted;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("W I N D H A N D E L", id="title")
        yield Static("Your portfolio, inside the terminal.", id="fluff")
        yield CommandBar()
        yield Footer()


class WindhandelApp(App):
    def on_mount(self) -> None:
        self.push_screen(LoadingScreen())

    def on_loading_screen_ready(self, message: LoadingScreen.Ready) -> None:
        self.push_screen(HomeScreen())

    def on_command_bar_submitted(self, message: CommandBar.Submitted) -> None:
        code = message.code
        if len(code) != 4:
            self.notify("Enter exactly 4 letters.", severity="warning")
            return
        screen_cls = MNEMONICS.get(code)
        if screen_cls:
            self.push_screen(screen_cls())
        else:
            self.notify(f"Unknown command: {code}", severity="error")


if __name__ == "__main__":
    WindhandelApp().run()