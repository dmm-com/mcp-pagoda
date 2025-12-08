import asyncio
import logging
from typing import Literal

import click
from dotenv import load_dotenv

from mcp_server.lib.log import Logger

from .server_sse import serve as serve_sse
from .server_stdio import serve as serve_stdio

load_dotenv()


@click.command()
@click.option("--host", default="localhost", help="Host to bind to")
@click.option("--port", default=8000, help="Port to listen on")
@click.option("--endpoint", "-e", help="Pagoda endpoint URL", required=True)
@click.option("--token", "-t", help="Pagoda user token", required=False)
@click.option(
    "--loglevel",
    "-l",
    help="Log level",
    type=click.Choice(
        ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False
    ),
    default="INFO",
)
@click.option(
    "--transport",
    default="sse",
    type=click.Choice(["sse", "stdio"]),
    help="Transport protocol to use ('sse' or 'stdio')",
)
@click.option(
    "--auth",
    default="bearer",
    type=click.Choice(["bearer", "azure"]),
    help="Authentication method to use ('bearer' or 'azure')",
)
def main(
    host: str,
    port: int,
    endpoint: str,
    token: str,
    loglevel: str,
    transport: Literal["sse", "stdio"],
    auth: Literal["bearer", "azure"],
) -> None:
    Logger.setLevel(logging.getLevelName(loglevel))

    match transport:
        case "stdio":
            asyncio.run(serve_stdio(endpoint, token))

        case "sse":
            asyncio.run(serve_sse(host, port, auth, endpoint, token))


if __name__ == "__main__":
    main()
