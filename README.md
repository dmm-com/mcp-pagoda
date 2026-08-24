# mcp-pagoda

A MCP Server for Pagoda.

It exposes Pagoda (a.k.a. AirOne) as MCP tools and prompts, so that MCP clients such as
Claude Desktop can search Models / Items, run Advanced Search, and inspect datacenter and
network topology information.

- [Choosing a setup pattern](#choosing-a-setup-pattern)
- [Preparation](#preparation)
- [Configuration for Claude Desktop](#configuration-for-claude-desktop)
  - [Pattern 1: uv + stdio](#pattern-1-uv--stdio)
  - [Pattern 2: uv + SSE](#pattern-2-uv--sse)
  - [Pattern 3: Docker + stdio](#pattern-3-docker--stdio)
  - [Pattern 4: Docker + SSE](#pattern-4-docker--sse)
- [Command line options](#command-line-options)
- [Tools and Prompts](#tools-and-prompts)
- [Debug](#debug)
- [Development](#development)

## Choosing a setup pattern

This server supports two transports, and each of them can be run either locally with `uv`
or inside a Docker container. That makes the four patterns below.

| Pattern | How to run | Transport | The client starts the server? | Where the Pagoda token comes from |
| ------- | ---------- | --------- | ----------------------------- | --------------------------------- |
| [1](#pattern-1-uv--stdio) | `uv` on your machine | `stdio` | Yes (per client process) | `--token` option of the server |
| [2](#pattern-2-uv--sse) | `uv` on your machine | `sse` | No (you run it beforehand) | `Authorization` header of the client |
| [3](#pattern-3-docker--stdio) | Docker container | `stdio` | Yes (per client process) | `--token` option of the server |
| [4](#pattern-4-docker--sse) | Docker container | `sse` | No (you run it beforehand) | `Authorization` header of the client |

Which one to pick:

- **stdio (Pattern 1 / 3)** is the simplest one, and it is recommended when you use the
  server only from your own machine. The client boots the server as a child process and
  talks to it through standard input/output, and the Pagoda token is embedded in the
  client configuration.
- **SSE (Pattern 2 / 4)** is for running the server as a long-lived HTTP service, e.g. to
  share one server with multiple users. The server authenticates **each request** (Bearer
  token of Pagoda, or Azure AD OAuth), so the token is not embedded in the server process.

> [!IMPORTANT]
> The default transport is `sse`. Always pass `--transport stdio` explicitly when you want
> the stdio patterns.

## Preparation

### For `uv` patterns (1 and 2)

Create a venv environment and install the dependent libraries.

```
$ cd mcp-pagoda
$ uv venv
$ uv sync
```

### For Docker patterns (3 and 4)

Build the Docker image.

```
$ docker build -t mcp/pagoda .
```

## Configuration for Claude Desktop

The configuration file is located at:

| OS | Path |
| -- | ---- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Restart Claude Desktop after editing the file.

Replace the following placeholders in every example below.

| Placeholder | Description |
| ----------- | ----------- |
| `{Repository PATH}` | Absolute path of this local repository (e.g. `/home/user/mcp-pagoda`) |
| `{Pagoda URL}` | Base URL of Pagoda (e.g. `https://pagoda.example.com`) |
| `{Access token of Pagoda}` | Your Pagoda access token, which is shown at the "Edit User" page of Pagoda |

### Pattern 1: uv + stdio

Claude Desktop starts the server as a child process, and the server accesses Pagoda with
the token that is given by the `--token` option.

```json
{
  "mcpServers": {
    "pagoda": {
      "command": "uv",
      "args": [
        "--directory", "{Repository PATH}",
        "run",
        "mcp-server",
        "--transport", "stdio",
        "--endpoint", "{Pagoda URL}",
        "--token", "{Access token of Pagoda}"
      ]
    }
  }
}
```

> [!NOTE]
> `command` must be resolvable from Claude Desktop, which does not read your shell
> configuration files. Specify the absolute path of `uv` (`which uv`, e.g.
> `/Users/user/.local/bin/uv`) when the server fails to start.

### Pattern 2: uv + SSE

In this pattern the server is a HTTP service, so it has to be started **before** Claude
Desktop connects to it.

**Step 1. Run the server.**

```
$ uv run mcp-server \
  --transport sse \
  --host localhost \
  --port 8000 \
  --endpoint "{Pagoda URL}"
```

The SSE endpoint is `http://localhost:8000/sse`. Note that `--token` is not necessary
here, because the token is taken from the `Authorization` header of each request.

**Step 2. Configure Claude Desktop.**

Claude Desktop cannot send a static `Authorization` header by itself, so
[mcp-remote](https://www.npmjs.com/package/mcp-remote) is used as a bridge between the
stdio interface of Claude Desktop and the SSE endpoint of this server. It requires
Node.js.

```json
{
  "mcpServers": {
    "pagoda": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8000/sse",
        "--header", "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer {Access token of Pagoda}"
      }
    }
  }
}
```

> [!NOTE]
> The header value is passed through the `AUTH_HEADER` environment variable on purpose.
> Claude Desktop splits an argument that contains a space into two arguments, which breaks
> `"Authorization: Bearer ..."` when it is written directly in `args`.

Claude Code can connect to the same endpoint without the bridge.

```
$ claude mcp add --transport sse pagoda http://localhost:8000/sse \
  --header "Authorization: Bearer {Access token of Pagoda}"
```

#### Using Azure AD OAuth instead of a Pagoda token

Passing `--auth azure` makes the server authenticate users with Azure AD OAuth instead of
verifying a Pagoda token. The following environment variables are required, and they can
also be written in a `.env` file at the current directory of the server.

| Environment variable | Description |
| -------------------- | ----------- |
| `MCP_AZURE_AZURE_TENANT_ID` | Tenant ID of the Azure AD application |
| `MCP_AZURE_AZURE_CLIENT_ID` | Client ID of the Azure AD application |
| `MCP_AZURE_AZURE_CLIENT_SECRET` | Client secret of the Azure AD application |
| `MCP_AZURE_AZURE_CALLBACK_PATH` | Redirect URL (default: `http://localhost:8000/azure/callback`) |
| `MCP_AZURE_SERVER_URL` | URL that this server is reachable at (default: `http://localhost:8000`) |

> [!IMPORTANT]
> `MCP_AZURE_SERVER_URL` is the base URL that the server advertises as its OAuth metadata,
> and it does **not** follow `--host` / `--port`. Set it together with
> `MCP_AZURE_AZURE_CALLBACK_PATH` whenever the server is not reachable at
> `http://localhost:8000`.

```
$ uv run mcp-server --transport sse --auth azure --endpoint "{Pagoda URL}"
```

Because this pattern advertises the OAuth metadata, `mcp-remote` performs the
authorization flow by itself and no `--header` option is necessary.

```json
{
  "mcpServers": {
    "pagoda": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/sse"]
    }
  }
}
```

### Pattern 3: Docker + stdio

Same as [Pattern 1](#pattern-1-uv--stdio), except that Claude Desktop starts a container
instead of `uv`. `-i` is mandatory because the container communicates over standard
input/output, and `--rm` removes the container when the client stops it.

```json
{
  "mcpServers": {
    "pagoda": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "mcp/pagoda",
        "--transport", "stdio",
        "--endpoint", "{Pagoda URL}",
        "--token", "{Access token of Pagoda}"
      ]
    }
  }
}
```

> [!NOTE]
> Docker (e.g. Docker Desktop) must already be running, because Claude Desktop only
> executes the `docker run` command. Specify the absolute path of `docker` when the server
> fails to start.

### Pattern 4: Docker + SSE

Run the container as a HTTP service. Two options are important here.

- `--host 0.0.0.0` : the default value `localhost` only accepts connections from inside
  the container.
- `-p 8000:8000` : publishes the port of the container to your machine.

```
$ docker run --rm -p 8000:8000 mcp/pagoda \
  --transport sse \
  --host 0.0.0.0 \
  --port 8000 \
  --endpoint "{Pagoda URL}"
```

The client configuration is exactly the same as
[Pattern 2](#pattern-2-uv--sse), since the client just connects to
`http://localhost:8000/sse`.

```json
{
  "mcpServers": {
    "pagoda": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8000/sse",
        "--header", "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer {Access token of Pagoda}"
      }
    }
  }
}
```

To use Azure AD OAuth, pass `--auth azure` and the `MCP_AZURE_*` environment variables to
the container.

```
$ docker run --rm -p 8000:8000 --env-file .env mcp/pagoda \
  --transport sse \
  --host 0.0.0.0 \
  --auth azure \
  --endpoint "{Pagoda URL}"
```

## Command line options

| option | default | description |
| ------ | ------- | ----------- |
| `--endpoint`, `-e` | (required) | Base URL of Pagoda |
| `--token`, `-t` | - | Pagoda access token. Required for `stdio`, and ignored by `sse` because each request carries its own credential |
| `--transport` | `sse` | Transport protocol, either `sse` or `stdio` |
| `--host` | `localhost` | Host to bind to (`sse` only) |
| `--port` | `8000` | Port to listen on (`sse` only) |
| `--auth` | `bearer` | Authentication method of the SSE server, either `bearer` (Pagoda token) or `azure` (Azure AD OAuth) |
| `--loglevel`, `-l` | `INFO` | Log level: `CRITICAL`, `ERROR`, `WARNING`, `INFO` or `DEBUG` |

## Tools and Prompts

These are the MCP Tools that MCP Pagoda provides, classified by categories.

| tool | category | description |
| ---- | -------- | ----------- |
| get_me | Common | Get the profile of the authenticated user |
| get_model_list | Common | List infomation about Model (a.k.a. Entity) |
| get_model_detail | Common | Get detail infomation about specified Model |
| get_item_list | Common | List infomation about Item (a.k.a. Entry) |
| get_item_detail | Common | Get detail infomation about specified Item |
| search_item | Common | List Items that are related with specified keyword |
| advanced_search | Common | Search Item infomation from specified complexed conditions |
| get_user_activity | Common | Get activity history of specified user within specified period |
| restore_item_attribute_value | Common | Restore an attribute value to its previous state |
| rollback_items | Common | Roll back Items to their state at specified datetime |
| get_rack_list | Datacenter | List all rack item infomation that contains appliances |
| ping_check | Network | Check IP reachability for a CIDR via ping |
| router_topology | Router | Get infomation that describes physical network topology |

Here is the description of each categories.

| category   | description |
| ---------- | ----------- |
| Common     | Common functions for all infomation |
| Datacenter | Features about DCIM (e.g. Rack, Appliances and so on) |
| Network    | Features about Network (e.g. IPaddress and Network) |
| Router     | Features for physical configuration diagram of Network appliances connection |

MCP Prompts are also provided.

| prompt | description |
| ------ | ----------- |
| get_vm_from_network | Investigate VMs that belong to the specified global network |

## Debug

Use MCP Inspector.

```
$ npx @modelcontextprotocol/inspector -- uv run mcp-server \
  --transport stdio \
  --endpoint "{Pagoda URL}" \
  --token "{Access token of Pagoda}"
```

The `--` separator is required so that options such as `--transport stdio` are passed to
`mcp-server`, not consumed by the Inspector CLI.

For the SSE server, start the Inspector without arguments, then choose the `SSE` transport
type and enter `http://localhost:8000/sse` with a Bearer token.

```
$ npx @modelcontextprotocol/inspector
```

## Development

Run the linter and the formatter before sending a pull request, because the CI checks them.

```
$ uv run ruff check .
$ uv run ruff format .
```

`pytest` (test files go to `tests/`) and `pyright` are also installed as dev dependencies.

```
$ uv run pytest
$ uv run pyright
```
