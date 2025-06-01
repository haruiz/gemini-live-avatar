# ... [imports remain unchanged] ...
import asyncio
import base64
import logging
import os
import traceback
import uuid

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from google.genai.types import (
    LiveConnectConfig, Modality, LiveServerContent, RealtimeInputConfig, AutomaticActivityDetection, StartSensitivity,
    EndSensitivity
)
from mcp import StdioServerParameters
from starlette.websockets import WebSocketDisconnect

from gemini_live_avatar.mcp_server import MCPClient
from gemini_live_avatar.session import SessionState, create_session, remove_session
from gemini_live_avatar.config import runtime_config

# Load environment variables
load_dotenv(find_dotenv())
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"), vertexai=False)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rich")
# FastAPI Setup

async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    """
    logger.info("Starting Gemini Live Avatar API")
    yield
    logger.info("Shutting down Gemini Live Avatar API")


api = FastAPI(root_path="/api", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_system_instruction():
    return """
        You are a helpful and friendly AI assistant.
        Respond in clear, plain text using natural, conversational language.
        Keep answers short and concise. When appropriate, use emoticons to convey tone 😊.
        Avoid speculation or unsafe advice. If unsure, ask for clarification.
        DON'T ADD PUNCTUATION
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

async def create_gemini_live_session(tools):

    return client.aio.live.connect(
        model=runtime_config.model_name,
        config=LiveConnectConfig(
            tools=tools,
            system_instruction=get_system_instruction(),
            response_modalities=[Modality.TEXT],
            realtime_input_config=RealtimeInputConfig(
                automatic_activity_detection=AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=EndSensitivity.END_SENSITIVITY_LOW,
                )
            )
        )
    )


@api.websocket("/ws/live")
async def websocket_receiver(websocket: WebSocket):
    session_id = uuid.uuid4().hex
    session = create_session(session_id)

    try:
        # Define tool: Turn on the lights
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

        tools = []
        tools.extend(default_tools)
        if runtime_config.mcp_server_config:
            logger.info("MCP Server configuration found, initializing MCP client")
            mcp_server = MCPClient.from_json_config(runtime_config.mcp_server_config)
            session.mcp_server_client = mcp_server
            await mcp_server.connect_to_server()
            mcp_tools = await mcp_server.get_tools_for_gemini()
            if mcp_tools:
                logger.info(f"Using MCP tools: {[tool.function_declarations[0].name for tool in mcp_tools]}")
                tools.extend(mcp_tools)

        if runtime_config.google_search_grounding:
            logger.info("Google Search Grounding enabled")
            tools.insert(0, {"google_search": {}})


        async with await create_gemini_live_session(tools=tools) as live_session:
            session.live_session = live_session

            await handle_messages(websocket, session)
    except asyncio.TimeoutError:
        await send_error_message(websocket, {
            "message": "Session timed out.",
            "action": "Please reconnect.",
            "error_type": "timeout"
        })
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from session {session_id}")
    except Exception as e:
        if "connection closed" not in str(e).lower():
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            await send_error_message(websocket, {
                "message": "Unexpected error occurred.",
                "action": "Try again.",
                "error_type": "general"
            })
    finally:
        await cleanup_session(session, session_id)

async def handle_messages(ws: WebSocket, session: SessionState):
    try:
        await ws.accept()
        await ws.send_json({
            "type": "config",
            "ttsApikey": os.environ.get("TTS_API_KEY"),
            "ttsLang": runtime_config.tts_lang,
            "ttsVoice": runtime_config.tts_voice,
            "avatarPath": runtime_config.avatar_path
        })

        async with asyncio.TaskGroup() as tg:
            tg.create_task(handle_user_messages(ws, session))
            tg.create_task(handle_gemini_responses(ws, session))

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

async def handle_user_messages(ws: WebSocket, session: SessionState):
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

async def handle_gemini_responses(ws: WebSocket, session: SessionState):
    tool_queue = asyncio.Queue()  # Queue for tool responses
    # Start a background task to process tool calls
    tool_processor = asyncio.create_task(process_function_calls(tool_queue, ws, session))
    try:
        while True:
            try:
                async for chunk in session.live_session.receive():
                    if chunk.tool_call:
                        await tool_queue.put(chunk.tool_call)
                        continue  # Continue processing other responses while tool executes
                    await process_server_content(ws, session, chunk.server_content)

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


async def process_server_content(ws: WebSocket, session: SessionState, server_content: LiveServerContent):

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
        session.received_model_response = False; session.is_receiving_response = False