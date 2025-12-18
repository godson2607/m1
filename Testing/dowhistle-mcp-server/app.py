import structlog
import os
from pathlib import Path
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

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
# Configure structured logging for production
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if settings.ENVIRONMENT == "production" 
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def create_app():
    """Create and configure production-grade MCP server with optional AuthKit OAuth2.0"""

    authkit_domain = os.getenv("FASTMCP_SERVER_AUTH_AUTHKITPROVIDER_AUTHKIT_DOMAIN") or os.getenv(
        "AUTHKIT_DOMAIN"
    )
    base_url = os.getenv("FASTMCP_SERVER_AUTH_AUTHKITPROVIDER_BASE_URL") or os.getenv("BASE_URL")

    if AuthKitProvider and authkit_domain and base_url:
        auth_provider = AuthKitProvider(authkit_domain=authkit_domain, base_url=base_url)
        mcp = FastMCP("Whistle MCP Server", auth=auth_provider)
        auth_enabled = True
        logger.info("AuthKit OAuth2.0 enabled", authkit_domain=authkit_domain, base_url=base_url)
    else:
        mcp = FastMCP("Whistle MCP Server")
        auth_enabled = False
        logger.info("Running without authentication")
    
    # Add middleware in correct order (first added = outermost layer)
    mcp.add_middleware(LoggingMiddleware())    # Log everything first

    # Register all agents
    SearchAgent(mcp)
    WhistleAgent(mcp)
    UserAgent(mcp)
    
    # Health check endpoint
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        return JSONResponse({
            "status": "healthy",
            "service": "whistle-mcp-server",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
            "middleware": ["logging", "rate_limit"],
            "auth": {
                "enabled": auth_enabled,
                "provider": "AuthKit" if auth_enabled else None
            }
        })

    # Get the ASGI app
    app = mcp.http_app(stateless_http=True)
    
    # Add CORS middleware for development
    if settings.ENVIRONMENT == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    logger.info(
        "Production MCP server created",
        environment=settings.ENVIRONMENT,
        middleware_count=2,
        agents_count=3,
        auth_enabled=auth_enabled
    )
    
    return app

# Create the ASGI app
app = create_app()
