# mcp-pagoda

A MCP Server for Pagoda

# Tool
These are MCP Tools that MCP Pagoda provides and classified by categories.

| tool | category | description |
| ---- | -------- | ----------- |
| get_model_list | Common | List infomation about Model (a.k.a. Entity) |
| get_model_detail | Common | Get detail infomation about specified Model |
| get_item_list | Common | List infomation about Item (a.k.a. Entry) |
| get_item_detail | Common | Get detail infomation about specified Item |
| search_item | Common | List Items that are related with specified keyword |
| advanced_search | Common | Search Item infomation from specified complexed conditions |
| get_rack_list | Datacenter | List all rack item infomation that contains appliances |
| router_topology | Router | Get infomation that describes physical network topology |

Here is the description of each categories.

| category   | description |
| ---------- | ----------- |
| Common     | Common functions for all infomation |
| Datacenter | Features about DCIM (e.g. Rack, Appliances and so on) |
| Network    | Features about Network (e.g. IPaddress and Network) |
| Router     | Features for physical configuration diagram of Network appliances connection |

# Development

## Making running environment of MCP server
Make venv environment by uv command as below
```
$ cd mcp-pagoda
$ uv venv
```

Then, install dependent libraries.
```
$ uv sync
```

## Setting configuration for Claude Desktop
Add following to your `claude_desktop_config.json`.
```
{
    "mcpServers": {
        "pagoda": {
            "command": "uv",
            "args": [
                "--directory", "{directory of this local repository}",
                "run",
                "mcp-server",
                "--endpoint", "{Pagoda URL}",
                "--token", "{Access token of Pagoda}",
             ]
        }
    }
}
```

# Build

Run following command to build docker image

```
$ docker build -t mcp/pagoda .
```

# Configuration

Add following to your `claude_desktop_config.json`.

### uv

```
{
  "mcpServers": {
    "pagoda": {
      "command": "uv",
      "args": [
        "--directory", "{Repository PATH}",
        "run",
        "mcp-server",
        "--endpoint", "{Pagoda URL}",
        "--token", "{Access token of Pagoda}"
      ]
    }
  }
}
```

### docker

```
{
  "mcpServers": {
    "pagoda": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "mcp/pagoda",
        "--endpoint", "{Pagoda URL}",
        "--token", "{Access token of Pagoda}"
      ]
    }
  }
}
```

# Debug

Use MCP Inspector

```
$ npx @modelcontextprotocol/inspector uv run mcp-server \
  --endpoint "{Pagoda URL}" \
  --token "{Access token of Pagoda}"
```
