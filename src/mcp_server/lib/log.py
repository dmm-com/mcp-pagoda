import logging
from logging.handlers import RotatingFileHandler

from mcp.server.fastmcp import Context

# This configured considers max filesize of logfile and logrotation.
# This must be more secure than using logging.basicConfig() for
# CVE-2018-0285, CVE-2000-1127 and others.
my_handler = RotatingFileHandler(
    "mcp-pagoda.log",
    mode="a",
    maxBytes=50 * 1024 * 1024,
    backupCount=5,
    encoding=None,
    delay=0,
)
my_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

Logger = logging.getLogger(__name__)
Logger.setLevel(logging.WARNING)
Logger.addHandler(my_handler)


def get_prefix(ctx: Context | None) -> str:
    """Returns the log prefix that tells where the request came from.

    The HTTP request is available only with the "sse" transport. The "stdio" one
    has no per-request HTTP context, so an empty prefix is returned there instead
    of raising an error.
    """
    if ctx is None:
        return ""

    try:
        request = ctx.request_context.request
    except (AttributeError, ValueError):
        return ""

    if request is None or request.client is None:
        return ""

    return f"[From:{request.client.host}] "
