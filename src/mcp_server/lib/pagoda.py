from mcp_server.lib.http import http_request_get


def is_token_valid(pagoda_url_base: str, token: str) -> bool:
    """
    Verify toekn verification

    Args:
        token (str): verifying token
        pagoda_url_base (str): Pagoda's base URL

    Returns:
        bool: whether specified token is valid or not
    """
    headers = {
        "Authorization": "Token " + token,
    }

    response = http_request_get(url=f"{pagoda_url_base}/user/api/v2/token/", headers=headers)
    if response is None:
        return False

    try:
        return response.json()["key"] == token
    except ValueError:
        return False
