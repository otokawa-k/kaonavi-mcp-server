from enum import Enum
import json
from typing import Any, Optional
from mcp import stdio_server
from mcp.server import Server
from mcp.types import (
    TextContent,
    Tool,
)
from datetime import datetime, timedelta
import pandas as pd
from pydantic import BaseModel, Field
from kaonavi_api_executor.auth.api_access_token_fetcher import ApiAccessTokenFetcher
from kaonavi_api_executor.api_executor import ApiExecutor
from kaonavi_api_executor.api.get_members_api import GetMembersApi
from kaonavi_api_executor.http_client.http_methods import Post
from kaonavi_api_executor.transformers.members_member_data_flattener import (
    MembersMemberDataFlattener,
)


# --- メンバー情報のキャッシュ ---
class MembersCache:
    def __init__(self, ttl_minutes: int = 10):
        self._dataframe: pd.DataFrame | None = None
        self._timestamp: datetime | None = None
        self._ttl = timedelta(minutes=ttl_minutes)

    def get_df(self) -> pd.DataFrame | None:
        if self._timestamp and datetime.now() - self._timestamp < self._ttl:
            return self._dataframe
        return None

    def set_df(self, df: pd.DataFrame) -> None:
        self._dataframe = df
        self._timestamp = datetime.now()


# --- インスタンスをグローバルに用意 ---
members_cache = MembersCache(ttl_minutes=10)


class ListMemberFields(BaseModel):
    force_refresh: bool = Field(
        default=False,
        description="If true, ignores cache and fetches fresh data from Kaonavi API",
        examples=[True],
    )


class GetMembers(BaseModel):
    query: Optional[str] = Field(
        default=None,
        description="pandas query string to filter members. "
        "Example: \"age >= 30 and city == '渋谷'\"",
        examples=["age >= 30 and department == '営業'"],
    )
    force_refresh: bool = Field(
        default=False,
        description="If true, ignores cache and fetches fresh data from Kaonavi API",
        examples=[True],
    )


class KaonaviTools(str, Enum):
    LIST_FIELDS = "list_member_fields"
    GET_MEMBERS = "get_members"


async def get_members_df(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh:
        cached_df = members_cache.get_df()
        if cached_df is not None:
            return cached_df

    fetcher = ApiAccessTokenFetcher(Post())
    token = await fetcher.fetch_access_token()
    api = GetMembersApi(token=token)
    api_executor = ApiExecutor(api)
    result = await api_executor.execute()

    flattener = MembersMemberDataFlattener(result)
    df = flattener.flatten()

    members_cache.set_df(df)
    return df


async def list_member_fields(force_refresh: bool = False) -> str:
    df = await get_members_df(force_refresh=force_refresh)

    info = {
        col: {
            "dtype": str(df[col].dtype),
            "sample_values": df[col].dropna().astype(str).unique().tolist()[:5],
        }
        for col in df.columns
    }

    return json.dumps(info, indent=2, ensure_ascii=False)


async def get_members(query: str | None = None, force_refresh: bool = False) -> str:
    df = await get_members_df(force_refresh=force_refresh)

    if query:
        try:
            df = df.query(query)
        except Exception as e:
            return json.dumps({"error": f"Invalid query: {e}"}, ensure_ascii=False)

    members = df.to_dict(orient="records")
    return json.dumps(members, indent=2, ensure_ascii=False)


async def serve() -> None:
    server: Server[Any] = Server("kaonavi-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=KaonaviTools.LIST_FIELDS,
                description="""
                    List available fields in Kaonavi member data.

                    This tool returns metadata about each field in the member dataset,
                    including its type and example values. Useful when the user or AI needs
                    to understand what fields can be used in filtering.

                    Parameters:
                    - force_refresh: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Avoid using this unless specifically needed.
                """,
                inputSchema=ListMemberFields.model_json_schema(),
            ),
            Tool(
                name=KaonaviTools.GET_MEMBERS,
                description="""
                    Retrieve filtered member list from Kaonavi.

                    This tool returns member information, optionally filtered using a pandas-style query.
                    To know which fields are available and what values they might contain, 
                    use `list_member_fields` beforehand to inspect the structure of the data.

                    Parameters:
                    - query: (optional) A pandas-style query string
                    - force_refresh: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Only use this when explicitly instructed, as cached data is usually sufficient.

                    Examples for query:
                    - "age >= 30 and department == '営業'"
                    - "city == '渋谷'"
                    - "name.str.contains('田中')"
                """,
                inputSchema=GetMembers.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        match name:
            case KaonaviTools.LIST_FIELDS:
                info = await list_member_fields()
                return [TextContent(type="text", text=f"Available fields:\n{info}")]

            case KaonaviTools.GET_MEMBERS:
                members = await get_members(query=arguments.get("query"))
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
