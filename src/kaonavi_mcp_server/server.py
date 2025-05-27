from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, Optional
from mcp import stdio_server
from mcp.server import Server
from mcp.types import (
    TextContent,
    Tool,
)
from pydantic import BaseModel, Field
from kaonavi_api_executor.auth.access_token import AccessToken
from kaonavi_api_executor.api_executor import ApiExecutor
from kaonavi_api_executor.api.get_members_api import GetMembersApi
from kaonavi_api_executor.api.get_sheets_api import GetSheetsApi
from kaonavi_api_executor.http_client.http_methods import Post
from kaonavi_api_executor.transformers.members_member_data_flattener import (
    MembersMemberDataFlattener,
)
from kaonavi_api_executor.transformers.sheets_member_data_flattener import (
    SheetsMemberDataFlattener,
)


# Initialize the API executor with the access token and API model
access_token = AccessToken(http_method=Post())
members_api_executor = ApiExecutor(access_token=access_token, api=GetMembersApi())
get_sheets_api = GetSheetsApi()
sheets_api_executor = ApiExecutor(access_token=access_token, api=get_sheets_api)


class DescribeMemberFields(BaseModel):
    no_cache: bool = Field(
        default=False,
        description="If true, ignores cache and fetches fresh data from Kaonavi API",
        examples=[True],
    )


class DescribeSheetFields(BaseModel):
    sheet_id: int = Field(
        description="ID of the sheet to retrieve fields from",
        examples=[1, 2, 3],
    )
    no_cache: bool = Field(
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
    no_cache: bool = Field(
        default=False,
        description="If true, ignores cache and fetches fresh data from Kaonavi API",
        examples=[True],
    )


class GetSheets(BaseModel):
    sheet_id: int = Field(
        description="ID of the sheet to retrieve",
        examples=[1, 2, 3],
    )
    query: Optional[str] = Field(
        default=None,
        description="pandas query string to filter members. "
        "Example: \"age >= 30 and city == '渋谷'\"",
        examples=["age >= 30 and department == '営業'"],
    )
    no_cache: bool = Field(
        default=False,
        description="If true, ignores cache and fetches fresh data from Kaonavi API",
        examples=[True],
    )


class GetSheetIds(BaseModel):
    pass


class KaonaviTools(str, Enum):
    DESCRIBE_MEMBER_FIELDS = "describe_member_fields"
    DESCRIBE_SHEET_FIELDS = "describe_sheet_fields"
    GET_MEMBERS = "get_members"
    GET_SHEETS = "get_sheets"
    GET_SHEET_IDS = "get_sheet_ids"


def load_sheets_config() -> Dict[str, Any]:
    config_path = Path(__file__).parent.parent.parent / "sheets_config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            "sheets_config.json not found. Please provide the file in the project root."
        )
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    if (
        not isinstance(data, dict)
        or "sheets" not in data
        or not isinstance(data["sheets"], list)
    ):
        raise ValueError(
            "sheets_config.json is invalid. 'sheets' key with a list value is required."
        )
    return data


async def describe_member_fields(no_cache: bool = False) -> str:
    result = await members_api_executor.execute(no_cache=no_cache)

    flattener = MembersMemberDataFlattener(result)
    df, _ = flattener.flatten()

    info = {
        col: {
            "dtype": str(df[col].dtype),
            "sample_values": df[col].dropna().astype(str).unique().tolist()[:5],
        }
        for col in df.columns
    }

    return json.dumps(info, indent=2, ensure_ascii=False)


async def describe_sheet_fields(sheet_id: int, no_cache: bool = False) -> str:
    get_sheets_api.set_sheet_id(sheet_id)
    result = await sheets_api_executor.execute(no_cache=no_cache)

    flattener = SheetsMemberDataFlattener(result)
    df = flattener.flatten()

    info = {
        col: {
            "dtype": str(df[col].dtype),
            "sample_values": df[col].dropna().astype(str).unique().tolist()[:5],
        }
        for col in df.columns
    }

    return json.dumps(info, indent=2, ensure_ascii=False)


async def get_members(query: str | None = None, no_cache: bool = False) -> str:
    result = await members_api_executor.execute(no_cache=no_cache)

    flattener = MembersMemberDataFlattener(result)
    df, _ = flattener.flatten()

    if query:
        try:
            df = df.query(query)
        except Exception as e:
            return json.dumps({"error": f"Invalid query: {e}"}, ensure_ascii=False)

    member_data = df.to_dict(orient="records")
    return json.dumps(member_data, indent=2, ensure_ascii=False)


async def get_sheets(
    sheet_id: int, query: str | None = None, no_cache: bool = False
) -> str:
    get_sheets_api.set_sheet_id(sheet_id)
    result = await sheets_api_executor.execute(no_cache=no_cache)

    flattener = SheetsMemberDataFlattener(result)
    df = flattener.flatten()

    if query:
        try:
            df = df.query(query)
        except Exception as e:
            return json.dumps({"error": f"Invalid query: {e}"}, ensure_ascii=False)

    member_data = df.to_dict(orient="records")
    return json.dumps(member_data, indent=2, ensure_ascii=False)


async def get_sheet_ids() -> str:
    config = load_sheets_config()
    sheets = config["sheets"]
    return json.dumps(sheets, ensure_ascii=False, indent=2)


async def serve() -> None:
    server: Server[Any] = Server("kaonavi-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=KaonaviTools.DESCRIBE_MEMBER_FIELDS,
                description="""
                    List available fields in Kaonavi member data.

                    This tool returns metadata about each field in the member dataset,
                    including its type and example values. Useful when the user or AI needs
                    to understand what fields can be used in filtering.

                    Parameters:
                    - no_cache: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Avoid using this unless specifically needed.
                """,
                inputSchema=DescribeMemberFields.model_json_schema(),
            ),
            Tool(
                name=KaonaviTools.DESCRIBE_SHEET_FIELDS,
                description="""
                    List available fields in a specific sheet of Kaonavi member data.

                    This tool returns metadata about each field in the specified sheet,
                    including its type and example values. Useful when the user or AI needs
                    to understand what fields can be used in filtering.

                    Parameters:
                    - sheet_id: ID of the sheet to retrieve fields from
                    - no_cache: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Avoid using this unless specifically needed.
                """,
                inputSchema=DescribeSheetFields.model_json_schema(),
            ),
            Tool(
                name=KaonaviTools.GET_MEMBERS,
                description="""
                    Retrieve filtered member list from Kaonavi.

                    This tool returns member information, optionally filtered using a pandas-style query.
                    To know which fields are available and what values they might contain, 
                    use `describe_member_fields` beforehand to inspect the structure of the data.

                    Parameters:
                    - query: (optional) A pandas-style query string
                    - no_cache: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Only use this when explicitly instructed, as cached data is usually sufficient.

                    Examples for query:
                    - "age >= 30 and department == '営業'"
                    - "city == '渋谷'"
                    - "name.str.contains('田中')"
                """,
                inputSchema=GetMembers.model_json_schema(),
            ),
            Tool(
                name="get_sheets",
                description="""
                    Retrieve member data from a specific sheet in Kaonavi.

                    This tool fetches member information from a specified sheet ID,
                    optionally filtered using a pandas-style query.
                    To know which fields are available and what values they might contain, 
                    use `describe_sheet_fields` beforehand to inspect the structure of the data.

                    Note: The filtering key for members in GET_SHEETS is the employee number (社員番号).
                    Employee numbers can be obtained from GET_MEMBERS.

                    Parameters:
                    - sheet_id: ID of the sheet to retrieve
                    - query: (optional) A pandas-style query string
                    - no_cache: (optional) Boolean to bypass cache and fetch fresh data.
                                    ⚠️ Only use this when explicitly instructed, as cached data is usually sufficient.

                    Examples for query:
                    - "age >= 30 and department == '営業'"
                    - "city == '渋谷'"
                    - "name.str.contains('田中')"
                """,
                inputSchema=GetSheets.model_json_schema(),
            ),
            Tool(
                name=KaonaviTools.GET_SHEET_IDS,
                description="""
                    Get a list of available sheet IDs and names for use with get_sheets.
                    The list is loaded from sheets_config.json in the project root.
                    If the file is missing or invalid, an error will be returned.
                """,
                inputSchema=GetSheetIds.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        match name:
            case KaonaviTools.DESCRIBE_MEMBER_FIELDS:
                info = await describe_member_fields(
                    no_cache=arguments.get("no_cache", False)
                )
                return [TextContent(type="text", text=f"Available fields:\n{info}")]

            case KaonaviTools.DESCRIBE_SHEET_FIELDS:
                sheet_id = arguments.get("sheet_id")
                if sheet_id is None:
                    raise ValueError(
                        "sheet_id is required for describe_sheet_fields tool."
                    )
                info = await describe_sheet_fields(
                    sheet_id=sheet_id,
                    no_cache=arguments.get("no_cache", False),
                )
                return [
                    TextContent(
                        type="text",
                        text=f"Available fields in sheet {sheet_id}:\n{info}",
                    )
                ]

            case KaonaviTools.GET_MEMBERS:
                members = await get_members(
                    query=arguments.get("query"),
                    no_cache=arguments.get("no_cache", False),
                )
                return [
                    TextContent(type="text", text=f"Members information:\n{members}")
                ]

            case KaonaviTools.GET_SHEETS:
                sheet_id = arguments.get("sheet_id")
                if sheet_id is None:
                    raise ValueError("sheet_id is required for get_sheets tool.")
                members = await get_sheets(
                    sheet_id=sheet_id,
                    query=arguments.get("query"),
                    no_cache=arguments.get("no_cache", False),
                )
                return [
                    TextContent(
                        type="text",
                        text=f"Members information from sheet {sheet_id}:\n{members}",
                    )
                ]

            case KaonaviTools.GET_SHEET_IDS:
                try:
                    sheet_ids = await get_sheet_ids()
                except Exception as e:
                    return [TextContent(type="text", text=f"[ERROR] {e}")]
                return [TextContent(type="text", text=f"Sheet IDs:\n{sheet_ids}")]

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
