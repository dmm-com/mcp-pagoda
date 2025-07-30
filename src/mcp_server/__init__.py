import asyncio
import logging

import click

from mcp_server.lib import Logger

from .server import serve


@click.command()
@click.option("--endpoint", "-e", help="Pagoda endpoint URL", required=True)
@click.option("--token", "-t", help="Pagoda user token", required=True)
@click.option(
    "--loglevel",
    "-l",
    help="Log level",
    type=click.Choice(
        ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False
    ),
    default="INFO",
)
def main(
    endpoint: str,
    token: str,
    loglevel: str,
) -> None:
    Logger.setLevel(logging.getLevelName(loglevel))

    asyncio.run(serve(endpoint, token))


if __name__ == "__main__":
    main()
