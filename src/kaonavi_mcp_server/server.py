import asyncio
from enum import Enum
import json
from mcp import stdio_server
from mcp.server import Server
from mcp.types import (
    TextContent,
    Tool,
)
from pydantic import BaseModel
from kaonavi_api_executor.auth.api_access_token_fetcher import ApiAccessTokenFetcher
from kaonavi_api_executor.api_executor import ApiExecutor
from kaonavi_api_executor.api.get_member_api import GetMemberApi
from kaonavi_api_executor.http_client.http_methods import Post

class GetMembers(BaseModel):
    id: str

class KaonaviTools(str, Enum):
    GET_MEMBERS = "get_members"

def get_members(id: str) -> str:
    # アクセストークンの取得
    fetcher = ApiAccessTokenFetcher(Post())
    token = fetcher.fetch_access_token()

    # メンバー情報の取得
    member_api = GetMemberApi(token=token)
    api_executor = ApiExecutor(member_api)
    response = api_executor.execute()

    # メンバー情報からname、name_kana、mailを除外
    filtered_members = [
        {key: value for key, value in member.items() if key not in ['name', 'name_kana', 'mail']}
        for member in response.member_data
    ]
    return json.dumps(filtered_members, indent=2, ensure_ascii=False)


async def serve() -> None:
    server = Server("kaonavi-mcp")

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
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        match name:
            case KaonaviTools.GET_MEMBERS:
                members = await asyncio.to_thread(get_members, arguments["id"])
                return [TextContent(
                    type="text",
                    text=f"Members information:\n{members}"
                )]

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
