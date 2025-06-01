import logging
import os
from typing import Optional

import typer
from typing_extensions import Annotated
from dotenv import load_dotenv, find_dotenv

from .config import runtime_config  # <-- import the global config instance

# Load environment variables from a .env file
load_dotenv(find_dotenv())

# Initialize Typer CLI
app = typer.Typer(invoke_without_command=True)

# Configure logging
logging.basicConfig(level=logging.INFO)


def dispatch_fastapi_app(
        app: str,
        host: str,
        port: int,
        workers: Optional[int] = None,
        reload: bool = True
) -> None:
    """
    Launch a FastAPI application using Uvicorn.
    """
    if workers is None:
        workers = (os.cpu_count() or 1) * 2 + 1

    logging.info(f"Starting FastAPI app on {host}:{port} with {workers} workers (reload={reload})")
    import uvicorn
    uvicorn.run(app, host=host, port=port, workers=workers, reload=reload)


@app.command(name="start")
def start(
    # fastapi parameters
    host: Annotated[str, typer.Option("--host", help="Host address")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port number")] = 8080,
    workers: Annotated[Optional[int], typer.Option("--workers", help="Number of workers")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload")] = False,
    # API keys
    gemini_api_key: Annotated[Optional[str], typer.Option(envvar="GEMINI_API_KEY", help="Google Gemini API key")] = None,
    tts_api_key: Annotated[Optional[str], typer.Option(envvar="TTS_API_KEY", help="Text-to-Speech API key")] = None,
    # runtime configuration
    tts_lang: Annotated[str, typer.Option("--tts-lang", help="Text-to-Speech language")] = "en-US",
    tts_voice: Annotated[str, typer.Option("--tts-voice", help="Text-to-Speech voice")] = "en-GB-Standard-A",
    avatar_path: Annotated[str, typer.Option("--avatar-path", help="Path to avatar model")] = "https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb",
    google_search_grounding: Annotated[bool, typer.Option("--google-search-grounding", help="Enable Google Search grounding")] = False,
    mcp_server_config: Annotated[Optional[str], typer.Option("--mcp-server-config", help="MCP server configuration file path")] = None,
) -> None:
    """
    Start the FastAPI-based Gemini Avatar app with runtime configurations.
    """

    # Set config values from CLI args into the global config instance
    runtime_config.google_search_grounding = google_search_grounding
    runtime_config.tts_lang = tts_lang
    runtime_config.tts_voice = tts_voice
    runtime_config.avatar_path = avatar_path
    runtime_config.mcp_server_config = mcp_server_config

    logging.info(f"RuntimeConfig: {runtime_config}")

    # Set environment variables if keys are passed
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        logging.info("Set GEMINI_API_KEY from input")

    if tts_api_key:
        os.environ["TTS_API_KEY"] = tts_api_key
        logging.info("Set TTS_API_KEY from input")

    dispatch_fastapi_app("gemini_live_avatar.app:app", host, port, workers, reload)


def main():
    app()


if __name__ == "__main__":
    main()
