import typing
from dataclasses import dataclass

@dataclass
class RuntimeConfig:
    google_search_grounding: bool = False
    tts_lang: str = "en-US"
    tts_voice: str = "en-GB-Standard-A"
    avatar_path: str = "https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb"
    model_name: str = "gemini-2.0-flash-live-001"
    mcp_server_config: typing.Optional[str] = None

runtime_config = RuntimeConfig()