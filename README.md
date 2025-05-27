# Kaonavi MCP Server

## Overview
Provides an MCP server that utilizes the Kaonavi API.

## Tools
1. DescribeMemberFields
   - Retrieves field information from the Members API.
2. DescribeSheetFields
   - Retrieves field information from the Sheets API.
3. GetMembers
   - Retrieves a list of members registered in Kaonavi.
4. GetSheets
   - Retrieves sheet information registered in Kaonavi.
5. GetSheetIds
   - Retrieves a list of sheet IDs set in sheets_config.json.

## Installation
1. Download [kaonavi_api_executor-0.3.0-py3-none-any.whl](https://github.com/otokawa-k/kaonavi-api-executor/releases/download/v0.3.0/kaonavi_api_executor-0.3.0-py3-none-any.whl) and install it with the following command:
```bash
uv pip install kaonavi_api_executor-0.3.0-py3-none-any.whl
```

## Debug
1. Install [Node.js](https://nodejs.org/).
2. Run the following command to start the MCP server:
```bash
npx @modelcontextprotocol/inspector
```

## License
This project is licensed under the [MIT License](./LICENSE).
