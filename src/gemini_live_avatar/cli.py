import logging
import os
from typing import Optional

import typer
from typing_extensions import Annotated
from dotenv import load_dotenv, find_dotenv

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

    Args:
        app: Application import path (e.g., "myapp.main:app").
        host: Host address to bind.
        port: Port number.
        workers: Number of worker processes (default: calculated based on CPU count).
        reload: Enable hot-reload (useful for development).
    """
    if workers is None:
        workers = (os.cpu_count() or 1) * 2 + 1

    logging.info(f"Starting FastAPI app on {host}:{port} with {workers} workers (reload={reload})")
    import uvicorn
    uvicorn.run(app, host=host, port=port, workers=workers, reload=reload)


@app.command(name="start")
def start(
        host: Annotated[str, typer.Option("--host", help="Host address")] = "127.0.0.1",
        port: Annotated[int, typer.Option("--port", help="Port number")] = 8080,
        workers: Annotated[Optional[int], typer.Option("--workers", help="Number of workers")] = None,
        reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload")] = False,
        gemini_api_key: Annotated[
            Optional[str], typer.Option(envvar="GEMINI_API_KEY", help="Google Gemini API key")] = None,
        tts_api_key: Annotated[Optional[str], typer.Option(envvar="TTS_API_KEY", help="Text-to-Speech API key")] = None,
        tts_lang: Annotated[str, typer.Option(envvar="TTS_LANG", help="Text-to-Speech language")] = "en-US",
        tts_voice: Annotated[str, typer.Option(envvar="TTS_VOICE", help="Text-to-Speech voice")] = "en-GB-Standard-A",
        avatar_path: Annotated[str, typer.Option(envvar="AVATAR_PATH", help="Path to avatar image")] = "https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png",
) -> None:
    """
    Start the Quack2Tex application with optional Gemini and TTS API configurations.
    You can pass API keys via command-line flags or environment variables.
    """
    api_keys = {
        "GEMINI_API_KEY": gemini_api_key,
        "TTS_API_KEY": tts_api_key,
        "TTS_LANG": tts_lang,
        "TTS_VOICE": tts_voice,
        "AVATAR_PATH": avatar_path,
    }

    for key, value in api_keys.items():
        if value:
            os.environ[key] = value
            logging.info(f"Set {key} from input")

    dispatch_fastapi_app("gemini_live_avatar.app:app", host, port, workers, reload)


def main():
    app()


if __name__ == "__main__":
    main()
