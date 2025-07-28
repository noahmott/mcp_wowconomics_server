"""
Constants and configuration values for WoW Guild MCP Server
"""

# ============================================================================
# REALM CONSTANTS
# ============================================================================

# Known Classic realm IDs (hardcoded for reliability)
KNOWN_CLASSIC_REALMS = {
    # US Classic Realms
    "atiesh": 4372,
    "mankrik": 4373,
    "pagle": 4374,
    "westfall": 4376,
    "whitemane": 4395,
    "grobbulus": 4408,
    "bloodsail-buccaneers": 4410,
    "faerlina": 4647,
    "benediction": 4648,
    
    # Add more as needed
}

# Known Retail realm connected IDs (for fallback when API search fails)
KNOWN_RETAIL_REALMS = {
    # US Realms
    "area-52": 3676,
    "stormrage": 60,
    "illidan": 57,
    "tichondrius": 11,
    "mal'ganis": 3684,
    "zul'jin": 3683,
    "moonguard": 3675,
    "wyrmrest-accord": 1171,
    "thrall": 3678,
    "frostmourne": 3725,
    "barthilas": 3723,
    "ragnaros": 3726,
    "lightbringer": 3694,
    
    # EU Realms  
    "draenor": 1403,
    "kazzak": 1305,
    "twisting-nether": 1400,
    "ragnaros-eu": 1301,
    "tarren-mill": 1303,
    "silvermoon": 1096,
    "ravencrest": 1329,
    "argent-dawn": 3702
}

# ============================================================================
# CACHE SETTINGS
# ============================================================================

# Cache TTL values (in seconds)
CACHE_TTL_GUILD_ROSTER = 15 * 24 * 60 * 60  # 15 days
CACHE_TTL_ECONOMY_SNAPSHOT = 30 * 24 * 60 * 60  # 30 days
CACHE_TTL_CONNECTED_REALM = 7 * 24 * 60 * 60  # 7 days

# ============================================================================
# API LIMITS AND DEFAULTS
# ============================================================================

# Guild analysis limits
MAX_GUILD_MEMBERS_ANALYSIS = 25  # Reduced from 50 to prevent timeouts
MAX_ERRORS_BEFORE_STOP = 10  # Stop fetching member data after this many errors

# Auction house settings
DEFAULT_AUCTION_RESULTS = 100  # Default number of auction results to return
AUCTION_HOUSE_PAGE_SIZE = 1000  # Items per page when fetching auction data
MAX_MARKET_OPPORTUNITIES = 20  # Maximum profitable items to return

# Chart generation settings
CHART_MAX_MEMBERS = 20  # Maximum members to show in comparison charts
CHART_DPI = 100  # DPI for generated charts
CHART_DEFAULT_FIGSIZE = (10, 6)  # Default figure size (width, height)

# ============================================================================
# REDIS KEY PATTERNS
# ============================================================================

REDIS_KEY_GUILD_ROSTER = "guild:roster:{realm}:{guild_name}"
REDIS_KEY_ECONOMY_SNAPSHOT = "economy:snapshot:{realm}:{timestamp}"
REDIS_KEY_ECONOMY_LATEST = "economy:latest:{realm}"
REDIS_KEY_CONNECTED_REALM = "realm:connected:{realm_slug}"

# ============================================================================
# ERROR MESSAGES
# ============================================================================

ERROR_REALM_NOT_FOUND = "Could not find connected realm ID for {realm}"
ERROR_GUILD_NOT_FOUND = "Guild '{guild_name}' not found on realm '{realm}'"
ERROR_CHARACTER_NOT_FOUND = "Character '{character_name}' not found on realm '{realm}'"
ERROR_REDIS_CONNECTION = "Failed to connect to Redis: {error}"
ERROR_API_REQUEST = "API request failed: {error}"

# ============================================================================
# DEFAULT VALUES
# ============================================================================

DEFAULT_REGION = "us"
DEFAULT_LOCALE = "en_US"
DEFAULT_GAME_VERSION = "retail"

# API Timeout settings (seconds)
API_TIMEOUT_TOTAL = 300
API_TIMEOUT_CONNECT = 10
API_TIMEOUT_READ = 60

# Rate limiting
RATE_LIMIT_REQUESTS = 100  # requests per time window
RATE_LIMIT_WINDOW = 1  # time window in seconds