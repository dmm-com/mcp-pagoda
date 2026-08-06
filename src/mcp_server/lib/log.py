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


def get_prefix(ctx: Context) -> str:
    # NOTE: The stdio transport has no HTTP request, so "request" is None there.
    # It can also be None-client when the peer address is unavailable.
    request = ctx.request_context.request
    if request is None or request.client is None:
        return ""
    return f"[From:{request.client.host}] "
