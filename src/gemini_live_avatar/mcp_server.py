import asyncio
import logging
import json
from typing import Optional, Tuple, List, Dict
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google.genai import types

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MCPClient:
    def __init__(self, server_params: Optional[StdioServerParameters] = None):
        self.server_params = server_params
        self._exit_stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None
        self.stdio: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connected: bool = False

    @classmethod
    def from_json_config(cls, config_path: str) -> "MCPClient":
        """
        Create an MCPClient instance from a JSON config file.

        Args:
            config_path (str): Path to the JSON configuration file.

        Returns:
            MCPClient: An initialized MCPClient with server_params.
        """
        config = json.loads(Path(config_path).read_text())

        command: str = config.get("command", "mcp-proxy")
        args: List[str] = config.get("args", [])
        env: Optional[Dict[str, str]] = config.get("env")

        server_params = StdioServerParameters(command=command, args=args, env=env)
        return cls(server_params=server_params)

    async def connect_to_server(self):
        if self._connected:
            logger.warning("Already connected to server.")
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        try:
            stdio_transport: Tuple[asyncio.StreamReader, asyncio.StreamWriter] = \
                await self._exit_stack.enter_async_context(stdio_client(self.server_params))

            self.stdio, self.writer = stdio_transport

            self.session = await self._exit_stack.enter_async_context(
                ClientSession(self.stdio, self.writer)
            )
            await self.session.initialize()

            response = await self.session.list_tools()
            tool_names = [tool.name for tool in response.tools]
            logger.info("✅ Connected to server. Available tools: %s", tool_names)

            self._connected = True
        except Exception as e:
            logger.error("❌ Failed to connect to server: %s", str(e))
            await self.close()
            raise

    async def get_tools_names(self) -> List[str]:
        """
        Returns a list of tool names available in the MCP server.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")

        response = await self.session.list_tools()
        tool_names = [tool.name for tool in response.tools]
        return tool_names

    async def execute_tool(self, tool_name: str, tool_args: Dict) -> str:
        """
        Executes a tool with the given name and input data.

        Args:
            tool_name (str): The name of the tool to execute.
            input_data (Dict): The input data for the tool.

        Returns:
            Dict: The output data from the tool execution.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")

        try:
            response = await self.session.call_tool(tool_name, arguments=tool_args)
            response_text =  response.content[0].text
            logger.info("✅ Successfully executed tool '%s'. Response: %s", tool_name, response_text)
            return response_text
        except Exception as e:
            logger.error("❌ Failed to execute tool '%s': %s", tool_name, str(e))
            raise

    async def get_tools_for_gemini(self) -> List[types.Tool]:
        """
        Returns tools in a format compatible with Gemini function calling.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")

        mcp_tools = await self.session.list_tools()

        gemini_tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters={
                            k: v
                            for k, v in (tool.inputSchema or {}).items()
                            if k not in ["additionalProperties", "$schema"]
                        },
                    )
                ]
            )
            for tool in mcp_tools.tools
        ]

        return gemini_tools

    async def close(self):
        if self._exit_stack:
            await self._exit_stack.__aexit__(None, None, None)
            self._exit_stack = None
            self._connected = False
            logger.info("🔌 Disconnected from server and cleaned up resources.")
