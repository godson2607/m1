import structlog
import os
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
import uvicorn

try:
    # Explicitly import the provider so it is registered and available
    from fastmcp.server.auth.providers.workos import AuthKitProvider  # type: ignore
except Exception:
    AuthKitProvider = None  # type: ignore

from agents.search import SearchAgent
from agents.whistle import WhistleAgent
from agents.user import UserAgent
from middleware.logging import LoggingMiddleware
from config.settings import settings
from dotenv import load_dotenv

# Load .env next to this file (and also respect CWD .env)
load_dotenv()
load_dotenv(Path(__file__).with_name(".env"))

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
        if settings.ENVIRONMENT == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def create_app():
    """Create and configure MCP server"""

    authkit_domain = os.getenv("FASTMCP_SERVER_AUTH_AUTHKITPROVIDER_AUTHKIT_DOMAIN") or os.getenv(
        "AUTHKIT_DOMAIN"
    )
    base_url = os.getenv("FASTMCP_SERVER_AUTH_AUTHKITPROVIDER_BASE_URL") or os.getenv("BASE_URL")

    if AuthKitProvider and authkit_domain and base_url:
        auth_provider = AuthKitProvider(
            authkit_domain=authkit_domain,
            base_url=base_url,
        )
        mcp = FastMCP("Whistle MCP Server", auth=auth_provider)
        auth_enabled = True
        logger.info("AuthKit OAuth enabled")
    else:
        mcp = FastMCP("Whistle MCP Server")
        auth_enabled = False
        logger.info("Running without authentication")

    # Middleware
    mcp.add_middleware(LoggingMiddleware())

    # Agents
    SearchAgent(mcp)
    WhistleAgent(mcp)
    UserAgent(mcp)

    # Health check
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        return JSONResponse(
            {
                "status": "healthy",
                "service": "whistle-mcp-server",
                "environment": settings.ENVIRONMENT,
                "auth_enabled": auth_enabled,
            }
        )

    # Create ASGI app
    app = mcp.http_app(stateless_http=True)

    # CORS for dev
    if settings.ENVIRONMENT == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    logger.info("MCP server initialized")

    return app


# ASGI app (used by uvicorn)
app = create_app()


# 🔴 THIS IS THE CRITICAL PART (FIX)
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
