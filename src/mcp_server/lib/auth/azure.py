import logging
import secrets
import time

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import FastMCP
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

logger = logging.getLogger(__name__)


class AzureServerSettings(BaseSettings):
    """Settings for the simple Azure AD MCP server."""

    # Server settings
    host: str = "localhost"
    port: int = 8000
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")

    model_config = SettingsConfigDict(env_prefix="MCP_AZURE_")

    # Azure AD OAuth settings - MUST be provided via environment variables
    azure_tenant_id: str  # Type: MCP_AZURE_AZURE_TENANT_ID env var
    azure_client_id: str  # Type: MCP_AZURE_AZURE_CLIENT_ID env var
    azure_client_secret: str  # Type: MCP_AZURE_AZURE_CLIENT_SECRET env var
    azure_callback_path: str = "http://localhost:8000/azure/callback"

    # Azure AD OAuth URLs
    @property
    def azure_auth_url(self) -> str:
        """Get Azure AD authorization URL."""
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/oauth2/v2.0/authorize"

    @property
    def azure_token_url(self) -> str:
        """Get Azure AD token URL."""
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/oauth2/v2.0/token"

    mcp_scope: str = "user"
    azure_scope: str = "https://graph.microsoft.com/User.Read"

    def __init__(self, **data):
        """Initialize settings with values from environment variables.

        Note: azure_tenant_id, azure_client_id and azure_client_secret are required but can be
        loaded automatically from environment variables (MCP_AZURE_AZURE_TENANT_ID,
        MCP_AZURE_AZURE_CLIENT_ID and MCP_AZURE_AZURE_CLIENT_SECRET) and don't need to be passed explicitly.
        """
        super().__init__(**data)


class SimpleAzureADOAuthProvider(OAuthAuthorizationServerProvider):
    """Simple Azure AD OAuth provider with essential functionality."""

    def __init__(self, settings: BaseSettings):
        self.settings = settings
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.state_mapping: dict[str, dict[str, str]] = {}
        self.token_mapping: dict[str, str] = {}
        # Store refresh tokens
        self.refresh_tokens: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get OAuth client information."""
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        """Register a new OAuth client."""
        self.clients[client_info.client_id] = client_info

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Generate an authorization URL for Azure AD OAuth flow."""
        state = params.state or secrets.token_hex(16)

        # Store the state mapping
        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": str(
                params.redirect_uri_provided_explicitly
            ),
            "client_id": client.client_id,
        }

        # Build Azure AD authorization URL
        auth_url = (
            f"{self.settings.azure_auth_url}"
            f"?client_id={self.settings.azure_client_id}"
            f"&response_type=code"
            f"&redirect_uri={self.settings.azure_callback_path}"
            f"&response_mode=query"
            f"&scope={self.settings.azure_scope}"
            f"&state={state}"
        )

        return auth_url

    async def handle_azure_callback(self, code: str, state: str) -> str:
        """Handle Azure AD OAuth callback."""
        state_data = self.state_mapping.get(state)
        if not state_data:
            raise HTTPException(400, "Invalid state parameter")

        redirect_uri = state_data["redirect_uri"]
        code_challenge = state_data["code_challenge"]
        redirect_uri_provided_explicitly = (
            state_data["redirect_uri_provided_explicitly"] == "True"
        )
        client_id = state_data["client_id"]

        # Exchange code for token with Azure AD
        async with create_mcp_http_client() as client:
            response = await client.post(
                self.settings.azure_token_url,
                data={
                    "client_id": self.settings.azure_client_id,
                    "client_secret": self.settings.azure_client_secret,
                    "code": code,
                    "redirect_uri": self.settings.azure_callback_path,
                    "grant_type": "authorization_code",
                    "scope": self.settings.azure_scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise HTTPException(
                    400, f"Failed to exchange code for token: {response.text}"
                )

            data = response.json()

            if "error" in data:
                raise HTTPException(400, data.get("error_description", data["error"]))

            azure_token = data["access_token"]
            azure_refresh_token = data.get("refresh_token")

            # Create MCP authorization code
            new_code = f"mcp_{secrets.token_hex(16)}"
            auth_code = AuthorizationCode(
                code=new_code,
                client_id=client_id,
                redirect_uri=AnyHttpUrl(redirect_uri),
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                expires_at=time.time() + 300,
                scopes=[self.settings.mcp_scope],
                code_challenge=code_challenge,
            )
            self.auth_codes[new_code] = auth_code

            # Store Azure AD token - we'll map the MCP token to this later
            self.tokens[azure_token] = AccessToken(
                token=azure_token,
                client_id=client_id,
                scopes=[self.settings.azure_scope],
                expires_at=int(time.time() + data.get("expires_in", 3600)),
            )

            # Store refresh token if provided
            if azure_refresh_token:
                self.refresh_tokens[azure_token] = azure_refresh_token

        del self.state_mapping[state]
        return construct_redirect_uri(redirect_uri, code=new_code, state=state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        """Load an authorization code."""
        return self.auth_codes.get(authorization_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """Exchange authorization code for tokens."""
        if authorization_code.code not in self.auth_codes:
            raise ValueError("Invalid authorization code")

        # Generate MCP access token
        mcp_token = f"mcp_{secrets.token_hex(32)}"

        # Store MCP token
        self.tokens[mcp_token] = AccessToken(
            token=mcp_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 3600,
        )

        # Find Azure AD token for this client
        azure_token = next(
            (
                token
                for token, data in self.tokens.items()
                if not token.startswith("mcp_") and data.client_id == client.client_id
            ),
            None,
        )

        # Store mapping between MCP token and Azure AD token
        if azure_token:
            self.token_mapping[mcp_token] = azure_token

        del self.auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=mcp_token,
            token_type="bearer",
            expires_in=3600,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load and validate an access token."""
        access_token = self.tokens.get(token)
        if not access_token:
            return None

        # Check if expired
        if access_token.expires_at and access_token.expires_at < time.time():
            # Try to refresh if this is an MCP token with Azure mapping
            if token.startswith("mcp_") and token in self.token_mapping:
                azure_token = self.token_mapping[token]
                if azure_token in self.refresh_tokens:
                    # Attempt to refresh the Azure token
                    new_azure_token = await self._refresh_azure_token(azure_token)
                    if new_azure_token:
                        # Update mappings
                        self.token_mapping[token] = new_azure_token
                        return self.tokens.get(token)

            del self.tokens[token]
            return None

        return access_token

    async def _refresh_azure_token(self, azure_token: str) -> str | None:
        """Refresh an Azure AD token."""
        refresh_token = self.refresh_tokens.get(azure_token)
        if not refresh_token:
            return None

        async with create_mcp_http_client() as client:
            response = await client.post(
                self.settings.azure_token_url,
                data={
                    "client_id": self.settings.azure_client_id,
                    "client_secret": self.settings.azure_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": self.settings.azure_scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            new_azure_token = data["access_token"]
            new_refresh_token = data.get("refresh_token", refresh_token)

            # Update tokens
            token_data = self.tokens[azure_token]
            del self.tokens[azure_token]
            del self.refresh_tokens[azure_token]

            self.tokens[new_azure_token] = AccessToken(
                token=new_azure_token,
                client_id=token_data.client_id,
                scopes=token_data.scopes,
                expires_at=time.time() + data.get("expires_in", 3600),
            )
            self.refresh_tokens[new_azure_token] = new_refresh_token

            return new_azure_token

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        """Load a refresh token - not supported."""
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Exchange refresh token"""
        raise NotImplementedError("Not supported")

    async def revoke_token(
        self, token: str, token_type_hint: str | None = None
    ) -> None:
        """Revoke a token."""
        if token in self.tokens:
            del self.tokens[token]
        if token in self.token_mapping:
            del self.token_mapping[token]


def get_azure_mcp_server(host: str, port: int) -> FastMCP:
    try:
        # No hardcoded credentials - all from environment variables
        settings = AzureServerSettings(host=host, port=port)
    except ValueError as e:
        logger.error(
            "Failed to load settings. Make sure environment variables are set:"
        )
        logger.error("  MCP_AZURE_AZURE_TENANT_ID=<your-tenant-id>")
        logger.error("  MCP_AZURE_AZURE_CLIENT_ID=<your-client-id>")
        logger.error("  MCP_AZURE_AZURE_CLIENT_SECRET=<your-client-secret>")
        logger.error(f"Error: {e}")
        return 1

    oauth_provider = SimpleAzureADOAuthProvider(settings)

    auth_settings = AuthSettings(
        issuer_url=settings.server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[settings.mcp_scope],
            default_scopes=[settings.mcp_scope],
        ),
        required_scopes=[settings.mcp_scope],
        resource_server_url=None,
    )

    server = FastMCP(
        name="Simple Azure AD MCP Server",
        instructions="A simple MCP server with Azure AD OAuth authentication",
        auth_server_provider=oauth_provider,
        host=settings.host,
        port=settings.port,
        debug=True,
        auth=auth_settings,
    )

    @server.custom_route("/azure/callback", methods=["GET"])
    async def azure_callback_handler(request: Request) -> Response:
        """Handle Azure AD OAuth callback."""
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            error_description = request.query_params.get(
                "error_description", "Unknown error"
            )
            raise HTTPException(400, f"Azure AD error: {error} - {error_description}")

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter")

        try:
            redirect_uri = await oauth_provider.handle_azure_callback(code, state)
            return RedirectResponse(status_code=302, url=redirect_uri)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected error", exc_info=e)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "server_error",
                    "error_description": "Unexpected error",
                },
            )

    def get_azure_token() -> str:
        """Get the Azure AD token for the authenticated user."""
        access_token = get_access_token()
        if not access_token:
            raise ValueError("Not authenticated")

        # Get Azure AD token from mapping
        azure_token = oauth_provider.token_mapping.get(access_token.token)

        if not azure_token:
            raise ValueError("No Azure AD token found for user")

        return azure_token

    return server
