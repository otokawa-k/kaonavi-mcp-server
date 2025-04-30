from enum import Enum
import json
from typing import Any
from mcp import stdio_server
from mcp.server import Server
from mcp.types import (
    TextContent,
    Tool,
)
from pydantic import BaseModel
from kaonavi_api_executor.auth.api_access_token_fetcher import ApiAccessTokenFetcher
from kaonavi_api_executor.api_executor import ApiExecutor
from kaonavi_api_executor.api.get_members_api import GetMembersApi
from kaonavi_api_executor.http_client.http_methods import Post


class GetMembers(BaseModel):
    id: str


class KaonaviTools(str, Enum):
    GET_MEMBERS = "get_members"


async def get_members(id: str) -> str:
    # アクセストークンの取得
    fetcher = ApiAccessTokenFetcher(Post())
    token = await fetcher.fetch_access_token()

    # メンバー情報の取得
    api = GetMembersApi(token=token)
    api_executor = ApiExecutor(api)
    response = await api_executor.execute()

    # メンバー情報からname、name_kana、mailを除外
    filtered_members = [
        {
            key: value
            for key, value in member.items()
            if key not in ["name", "name_kana", "mail"]
        }
        for member in response.member_data
    ]
    return json.dumps(filtered_members, indent=2, ensure_ascii=False)


async def serve() -> None:
    server: Server[Any] = Server("kaonavi-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=KaonaviTools.GET_MEMBERS,
                description="Retrieve member list from Kaonavi API",
                inputSchema=GetMembers.model_json_schema(),
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        match name:
            case KaonaviTools.GET_MEMBERS:
                members = await get_members(id=arguments["id"])
                return [
                    TextContent(type="text", text=f"Members information:\n{members}")
                ]

            case _:
                raise ValueError(f"Unknown tool: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)


def main() -> None:
    import asyncio

    asyncio.run(serve())


if __name__ == "__main__":
    main()
