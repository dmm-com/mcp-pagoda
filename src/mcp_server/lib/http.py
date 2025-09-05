import requests
from urllib.parse import urlparse


def http_request_get(url, headers=None, params=None, timeout=10):
    """
    指定したURLにGETリクエストを送信する

    Args:
        url (str): リクエスト先のURL
        headers (dict, optional): リクエストヘッダー
        params (dict, optional): クエリパラメータ
        timeout (int): タイムアウト時間（秒）

    Returns:
        requests.Response: レスポンスオブジェクト
    """
    try:
        # URLの妥当性をチェック
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("無効なURLです")

        # GETリクエストを送信
        response = requests.get(
            url=url, headers=headers, params=params, timeout=timeout
        )

        # レスポンスのステータスコードをチェック
        response.raise_for_status()

        return response

    except requests.exceptions.Timeout:
        print(f"タイムアウトエラー: {url} への接続がタイムアウトしました")
        return None
    except requests.exceptions.ConnectionError:
        print(f"接続エラー: {url} に接続できませんでした")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTPエラー: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"リクエストエラー: {e}")
        return None
    except ValueError as e:
        print(f"エラー: {e}")
        return None
