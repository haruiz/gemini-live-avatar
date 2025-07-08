# ... [imports remain unchanged] ...
import asyncio
import base64
import io
import json
import logging
import os
import tempfile
import traceback
import uuid
import wave
from asyncio import to_thread
from pathlib import Path
from typing import Tuple, Union, List

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from google import genai
from google.genai import types
from google.genai.types import (
    LiveConnectConfig, Modality, LiveServerContent, RealtimeInputConfig, AutomaticActivityDetection, StartSensitivity,
    EndSensitivity, AudioTranscriptionConfig, LiveServerMessage, SpeechConfig, VoiceConfig, PrebuiltVoiceConfig
)
from starlette.websockets import WebSocketDisconnect

from gemini_live_avatar.config import RuntimeConfig
from gemini_live_avatar.mcp_server import MCPClient
from gemini_live_avatar.session import SessionState, create_session, remove_session
from gemini_live_avatar.word_generator import WordGenerator

# Load environment variables
load_dotenv(find_dotenv())
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"), vertexai=False)
word_generator = WordGenerator(model_size="small", compute_type="float32")


task_registry: set[asyncio.Task] = set()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rich")


def get_runtime_config() -> RuntimeConfig:
    """
    Get the runtime configuration for the application.
    This function can be extended to load configurations from a file or environment variables.
    """
    with open("runtime_config.json", "r") as f:
        data = json.load(f)
    return RuntimeConfig(**data)


async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    """
    logger.info("Starting Gemini Live Avatar API")
    yield
    logger.info("Shutting down Gemini Live Avatar API")
    for task in task_registry:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Cancelled task successfully.")


api = FastAPI(root_path="/api", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# def get_system_instruction():
#     return """
#         You are a helpful and friendly AI assistant.
#         Respond in clear, plain text using natural, conversational language.
#         Keep answers short and concise. When appropriate, use emoticons to convey tone 😊.
#         Avoid speculation or unsafe advice. If unsure, ask for clarification.
#         DON'T ADD PUNCTUATION
#     """

def get_system_instruction():
    return """
        You are a helpful and friendly AI assistant.
        Respond in clear, plain text using natural, conversational language.
    """

@api.get("/")
async def read_root():
    return {"message": "Welcome to the Gemini Live Avatar API!"}

async def send_error_message(ws: WebSocket, error_data: dict):
    try:
        await ws.send_json({"type": "error", "data": error_data})
    except RuntimeError as e:
        if "unexpected ASGI message" in str(e).lower():
            logger.warning("⚠️ Attempted to send on closed WebSocket.")
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

async def send_debug_message(ws: WebSocket, debug_data: dict):
    try:
        await ws.send_json({"type": "debug", "data": debug_data})
    except RuntimeError as e:
        if "unexpected ASGI message" in str(e).lower():
            logger.warning("⚠️ Attempted to send on closed WebSocket.")
    except Exception as e:
        logger.error(f"Failed to send debug message: {e}")

async def create_gemini_live_session(tools, runtime_config):

    logger.info(f"Creating session with Gemini Live using configurations: {runtime_config}")
    response_modalities = [Modality.AUDIO]  if runtime_config.response_modality == "audio"  else [Modality.TEXT]

    return client.aio.live.connect(
        model=runtime_config.model_name,
        config=LiveConnectConfig(
            tools=tools,
            system_instruction=get_system_instruction(),
            response_modalities=response_modalities,
            output_audio_transcription=AudioTranscriptionConfig(),
            speech_config=SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name="Kore"
                    )
                )
            ),
            realtime_input_config=RealtimeInputConfig(
                automatic_activity_detection=AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=EndSensitivity.END_SENSITIVITY_LOW,
                )
            )
        )
    )

def get_default_tools() -> list[types.Tool]:
    """
    Define default built-in tools for the assistant.
    """

    turn_on_the_lights = types.FunctionDeclaration(
        name="turn_on_the_lights",
        description="Turn on the lights in the room.",
        parameters={
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "description": "The color to set the lights in hex format (e.g., #FFFFFF for white).",
                    "default": "#FFFFFF"
                }
            },
            "required": ["color"]
        }
    )

    # Define tool: Turn off the lights
    turn_off_the_lights = types.FunctionDeclaration(
        name="turn_off_the_lights",
        description="Turn off the lights in the room.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    )

    # Wrap in Tool class
    default_tools = [
        types.Tool(function_declarations=[
            turn_on_the_lights, turn_off_the_lights
        ])
    ]

    return default_tools

async def get_mcp_tools(mcp_server_config_path: Union[Path, str]) -> Tuple[MCPClient, list[types.Tool]]:
    """
    Placeholder for fetching MCP tools if needed.
    """
    tools = []
    try:
        mcp_server = MCPClient.from_json_config(mcp_server_config_path)
        await mcp_server.connect_to_server()
        mcp_tools = await mcp_server.get_tools_for_gemini()
        if mcp_tools:
            logger.info(f"Using MCP tools: {[tool.function_declarations[0].name for tool in mcp_tools]}")
            tools.extend(mcp_tools)
        return mcp_server, tools
    except Exception as e:
        logger.error(f"Failed to connect to MCP server or retrieve tools: {e}")
        raise


async def get_avatar_tools(runtime_config, ws) -> Tuple[MCPClient, List[types.Tool]]:
    """
    Initialize and return the list of tools for the avatar session.

    Returns:
        Tuple containing the initialized MCPClient (if any) and the list of tools.
    """
    tools= []
    mcp_client: MCPClient | None = None

    # Load default tools
    tools.extend(get_default_tools())

    # Optionally load tools from MCP server
    if runtime_config.mcp_server_config:
        logger.info("MCP Server configuration found. Initializing MCP client.")
        try:
            mcp_client, mcp_tools = await get_mcp_tools(runtime_config.mcp_server_config)
            tools.extend(mcp_tools)

            await send_debug_message(ws, {
                "message": (
                    "✅ MCP server tools loaded successfully. "
                    f"Available tools: {[tool.function_declarations[0].name for tool in mcp_tools]}"
                ),
                "action": "You can now use the available tools."
            })
        except Exception as e:
            logger.exception("Failed to load MCP server tools.")
            await send_error_message(ws, {
                "message": f"❌ Failed to load MCP server tools: {e}",
                "action": "Please check your server configuration.",
                "error_type": "mcp_connection"
            })

    # Add Google Search Grounding tool if enabled
    if runtime_config.google_search_grounding:
        logger.info("Google Search Grounding enabled.")
        tools.insert(0, {"google_search": {}})

    return mcp_client, tools



@api.websocket("/ws/live")
async def websocket_receiver(ws: WebSocket, runtime_config: RuntimeConfig = Depends(get_runtime_config)):
    session_id = uuid.uuid4().hex
    session = create_session(session_id)
    try:
        await ws.accept()
        await ws.send_json({
            "type": "config",
            "ttsApikey": os.environ.get("TTS_API_KEY"),
            "ttsLang": runtime_config.tts_lang,
            "ttsVoice": runtime_config.tts_voice,
            "avatarPath": runtime_config.avatar_path
        })
        logger.info(f"🌐 WebSocket connection accepted for session {session_id}")

        mcp_server_client, avatar_tools = await get_avatar_tools(runtime_config, ws)
        session.mcp_server_client = mcp_server_client

        async with await create_gemini_live_session(tools=avatar_tools, runtime_config=runtime_config) as live_session:
            session.live_session = live_session
            await handle_messages(ws, session, runtime_config)
    except asyncio.TimeoutError:
        await send_error_message(ws, {
            "message": "Session timed out.",
            "action": "Please reconnect.",
            "error_type": "timeout"
        })
    except WebSocketDisconnect:
        logger.info(f"Client disconnected before session {session_id} could start")
        await send_error_message(ws, {
            "message": "Client disconnected.",
            "action": "Reconnect to start a new session.",
            "error_type": "disconnection"
        })
    except Exception as e:
        if "connection closed" not in str(e).lower():
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            await send_error_message(ws, {
                "message": f"Unexpected error occurred. {e}",
                "action": "Try again.",
                "error_type": "general"
            })
    finally:
        await cleanup_session(session, session_id)



async def handle_messages(ws: WebSocket, session: SessionState, runtime_config: RuntimeConfig):
    try:
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(handle_user_messages(ws, session, runtime_config))
            task_registry.add(task)
            task = tg.create_task(handle_gemini_responses(ws, session, runtime_config))
            task_registry.add(task)

    except ExceptionGroup as eg:
        for exc in eg.exceptions:
            if "quota exceeded" in str(exc).lower():
                await send_error_message(ws, {
                    "message": "Quota exceeded.",
                    "error_type": "quota_exceeded",
                    "action": "Please try again later."
                })
            elif "connection closed" in str(exc).lower():
                logger.info("Client disconnected")
                return
        raise

async def handle_user_messages(ws: WebSocket, session: SessionState, runtime_config: RuntimeConfig = None):
    try:
        while True:
            try:
                data = await ws.receive_json()
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                return
            msg_type = data.get("type")
            ms_data = data.get("data", None)
            logger.info(f"Received message: {msg_type}")

            if msg_type == "audio":
                audio_data = base64.b64decode(ms_data)
                await session.live_session.send_realtime_input(
                    media=types.Blob(
                        mime_type='audio/pcm;rate=16000',
                        data=audio_data
                    )
                )
            elif msg_type == "image":
                image_data = base64.b64decode(ms_data)
                await session.live_session.send_realtime_input(
                    media=types.Blob(
                        mime_type="image/jpeg",
                        data=image_data
                    )
                )
            elif msg_type == "text":
                await session.live_session.send_realtime_input(
                    text=ms_data
                )
            elif msg_type == "end":
                logger.info("End of turn received")

            else:
                logger.warning(f"Unknown message type: {msg_type}")

    except Exception as e:
        if "connection closed" not in str(e).lower():
            logger.error(f"Client message error: {e}")
            logger.error(traceback.format_exc())
        raise

async def handle_gemini_responses(ws: WebSocket, session: SessionState, runtime_config: RuntimeConfig):
    tool_queue = asyncio.Queue()  # Queue for tool responses
    # Start a background task to process tool calls
    tool_processor = None
    try:
        tool_processor = asyncio.create_task(process_function_calls(tool_queue, ws, session))
        while True:
            try:
                async for chunk in session.live_session.receive():

                    if chunk.tool_call:
                        await tool_queue.put(chunk.tool_call)
                        continue  # Continue processing other responses while tool executes
                    if runtime_config.response_modality == "text":
                        await process_server_content_text_mode(ws, session, chunk.server_content)
                    elif runtime_config.response_modality == "audio":
                        await process_server_content_audio_mode(ws, session, chunk)

            except Exception as e:
                logger.error(f"Error from Gemini stream: {e}")
                logger.error(traceback.format_exc())
                raise
    finally:
        # Cancel and clean up tool processor
        if tool_processor and not tool_processor.done():
            tool_processor.cancel()
            try:
                await tool_processor
            except asyncio.CancelledError:
                pass

        # Clear any remaining items in the queue
        while not tool_queue.empty():
            try:
                tool_queue.get_nowait()
                tool_queue.task_done()
            except asyncio.QueueEmpty:
                break

async def cleanup_session(session: SessionState, session_id: str):
    try:
        if session.current_tool_execution:
            session.current_tool_execution.cancel()
            try:
                await session.current_tool_execution
            except asyncio.CancelledError:
                pass

        if session.live_session:
            try:
                await session.live_session.close()
            except Exception as e:
                logger.error(f"Error closing Gemini session: {e}")

        if session.mcp_server_client:
            try:
                await session.mcp_server_client.close()
            except Exception as e:
                logger.error(f"Error closing MCP session: {e}")

        remove_session(session_id)
        logger.info(f"Session {session_id} cleaned up.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")



async def process_function_calls(queue: asyncio.Queue, websocket: WebSocket, session: "SessionState"):
    """Continuously process function/tool calls from the queue."""
    while True:
        tool_call = await queue.get()
        logger.info(f"📥 Received tool call: {tool_call}")

        try:
            function_responses = []
            for function_call in tool_call.function_calls:
                session.current_tool_execution = asyncio.current_task()

                mcp_server_client = session.mcp_server_client
                try:
                    if mcp_server_client:
                        tool_names = await mcp_server_client.get_tools_names()
                        if function_call.name in tool_names:
                            logger.info(f"Executing MCP tool: {function_call.name} with args: {function_call.args}")
                            tool_result = await mcp_server_client.execute_tool(
                                tool_name=function_call.name,
                                tool_args=function_call.args
                            )
                        else:
                            logger.info(f"Tool {function_call.name} not found in MCP tools, handling as built-in function")
                            tool_result = await handle_builtin_function(function_call)
                    else:
                        tool_result = await handle_builtin_function(function_call)

                except Exception as tool_err:
                    logger.exception(f"❌ Error during tool execution: {tool_err}")
                    tool_result = f"Error executing function `{function_call.name}`: {tool_err}"

                await websocket.send_json({
                    "type": "function_call",
                    "data": {
                        "name": function_call.name,
                        "args": function_call.args,
                        "result": tool_result
                    }
                })
                function_responses.append(
                    types.FunctionResponse(
                        name=function_call.name,
                        id=function_call.id,
                        response={"output": tool_result}
                    )
                )
                session.current_tool_execution = None
            if function_responses:
                logger.info(f"📤 Sending function responses: {function_responses}")
                await session.live_session.send_tool_response(function_responses=function_responses)

        except Exception as e:
            logger.exception(f"❌ Exception in process_function_calls: {e}")

        finally:
            queue.task_done()


async def handle_builtin_function(function_call):
    """
    Handle built-in functions not handled by MCP tools.
    """
    match function_call.name:
        case "turn_on_the_lights":
            return "Lights turned on! 💡"
        case "turn_off_the_lights":
            return "Lights turned off! 🌙"
        case _:
            return f"Unknown function: {function_call.name}"


async def process_server_content_text_mode(ws: WebSocket, session: SessionState, server_content: LiveServerContent):
    """
    Process server content in text mode and send updates to WebSocket.
    """
    logger.info("Processing server content in text mode...")

    if not server_content:
        logger.warning("Received empty server content")
        return

    logger.info(f"Processing server content: {server_content}")

    """Process server content and send to WebSocket."""
    if server_content.interrupted:
        logger.info("Interruption detected from Gemini")
        await ws.send_json({
            "type": "interrupted",
            "data": {
                "message": "Response interrupted by user input"
            }
        })
        session.is_receiving_response = False
        return

    if server_content.output_transcription:
        transcription = server_content.output_transcription.text
        logger.info(f"Transcription received: {transcription}")
        await ws.send_json({
            "type": "text",
            "data": transcription
        })

    if server_content.model_turn:
        session.received_model_response = True
        session.is_receiving_response = True
        for part in server_content.model_turn.parts:
            if part.inline_data:
                audio_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                await ws.send_json({
                    "type": "audio",
                    "data": audio_base64
                })
            elif part.text:
                await ws.send_json({
                    "type": "text",
                    "data": part.text
                })

    if server_content.turn_complete:
        await ws.send_json({
            "type": "turn_complete"
        })
        session.received_model_response = False;
        session.is_receiving_response = False


async def process_server_content_audio_mode(ws: WebSocket, session: SessionState, response: LiveServerMessage):
    if not response:
        logger.warning("Received empty server content")
        return

    server_content = response.server_content
    data = response.data
    session.is_receiving_response = True

    # Initialize audio stream for this session if needed
    if not getattr(session, "audio_stream", None):
        session.audio_stream = io.BytesIO()
        session.audio_file = wave.open(session.audio_stream, "wb")
        session.audio_file.setnchannels(1)
        session.audio_file.setsampwidth(2)       # 16-bit audio
        session.audio_file.setframerate(24000)   # 24kHz
        logger.info("Initialized in-memory audio stream")

    # Write current chunk to memory
    if (server_content and server_content.model_turn) and data:
        session.audio_file.writeframes(data)

    if server_content and server_content.output_transcription:
        transcription = server_content.output_transcription.text
        logger.info(f"Transcription received: {transcription}")

    # Finalize and send when turn is complete
    if server_content and server_content.turn_complete:
        logger.info("Turn complete received from Gemini")
        await ws.send_json({
            "type": "turn_complete"
        })
        try:
            # Finalize audio stream
            session.audio_file.close()
            audio_bytes = session.audio_stream.getvalue()

            # Write to temp WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_path = Path(tmp_file.name)
                with wave.open(str(tmp_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio_bytes)

            # Run generate in a thread (since it's blocking and needs a file path)
            words_data = await to_thread(word_generator.generate, str(tmp_path))

            # Encode audio for transport
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            await ws.send_json({
                "type": "audio",
                "data": {
                    "audio": audio_base64,
                    "words": words_data
                }
            })
        except Exception as e:
            logger.exception("Error generating viseme data from audio")
            await ws.send_json({
                "type": "error",
                "data": {"message": f"Failed to process audio: {str(e)}"}
            })
        finally:
            # Cleanup
            session.audio_stream.close()
            session.audio_stream = None
            session.audio_file = None
            session.is_receiving_response = False

            if tmp_path and tmp_path.exists():
                tmp_path.unlink()




