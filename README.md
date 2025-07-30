# mcp-pagoda

A MCP Server for Pagoda

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
