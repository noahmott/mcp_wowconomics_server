"""
Security patch for resource exhaustion vulnerabilities in update_historical_database

ISSUES IDENTIFIED:
1. include_all_items=true with realms=all-us can process 124k+ items
2. No upper bound on top_items parameter
3. No rate limiting on API calls
4. Memory consumption not bounded (HISTORY_MAX_ENTRIES only limits per item)
5. No timeout protection for long-running operations

RECOMMENDED FIXES:
"""

# Configuration constants for resource limits
RESOURCE_LIMITS = {
    # Maximum realms that can be processed in a single request
    "MAX_REALMS_PER_REQUEST": 5,
    
    # Maximum items to track per realm
    "MAX_ITEMS_PER_REALM": 500,
    
    # Absolute maximum items across all realms in one request
    "MAX_TOTAL_ITEMS": 2000,
    
    # Maximum execution time for update operation (seconds)
    "MAX_EXECUTION_TIME": 300,  # 5 minutes
    
    # Rate limiting
    "MIN_SECONDS_BETWEEN_UPDATES": 60,  # Minimum 1 minute between updates
    
    # Memory limits
    "MAX_HISTORICAL_DATA_MB": 100,  # Maximum memory for historical data
    "MAX_DATA_POINTS_PER_ITEM": 288,  # 24 hours at 5-minute intervals
}

# Example implementation of secured update_historical_database
async def update_historical_database_secure(
    realms: Optional[str] = None,
    top_items: int = 100,
    include_all_items: bool = False,
    auto_expand: bool = False
) -> str:
    """
    Secured version with resource limits
    """
    import time
    from datetime import datetime, timedelta
    
    # 1. Rate limiting check
    last_update_key = "last_historical_update"
    if last_update_key in analysis_cache:
        last_update = analysis_cache[last_update_key]
        if datetime.now() - last_update < timedelta(seconds=RESOURCE_LIMITS["MIN_SECONDS_BETWEEN_UPDATES"]):
            return "Error: Rate limit exceeded. Please wait before updating again."
    
    # 2. Parameter validation and bounds checking
    if include_all_items and realms and realms.lower() == "all-us":
        return "Error: Cannot use include_all_items=true with realms='all-us' (potential DoS)"
    
    # Limit top_items
    top_items = min(top_items, RESOURCE_LIMITS["MAX_ITEMS_PER_REALM"])
    
    # 3. Realm limiting
    realm_list = []
    if realms:
        if realms.lower() == "all-us":
            # Limit to top 5 realms instead of all
            realm_list = [
                ("us", "stormrage"), ("us", "area-52"), ("us", "tichondrius"),
                ("us", "mal-ganis"), ("us", "kiljaeden")
            ]
        elif realms.lower() == "popular":
            # This is already limited to 10 realms
            realm_list = [...]  # existing code
        else:
            # Parse custom realms with limit
            parsed_realms = [r.strip() for r in realms.split(",")]
            if len(parsed_realms) > RESOURCE_LIMITS["MAX_REALMS_PER_REQUEST"]:
                return f"Error: Too many realms. Maximum {RESOURCE_LIMITS['MAX_REALMS_PER_REQUEST']} allowed."
            # ... parse realm_list
    
    # 4. Memory usage check
    current_memory_mb = calculate_historical_data_memory()
    if current_memory_mb > RESOURCE_LIMITS["MAX_HISTORICAL_DATA_MB"]:
        # Trigger cleanup of old data
        cleanup_old_historical_data()
    
    # 5. Execution with timeout
    start_time = time.time()
    total_items_processed = 0
    
    for region, realm in realm_list:
        # Check timeout
        if time.time() - start_time > RESOURCE_LIMITS["MAX_EXECUTION_TIME"]:
            return f"Error: Operation timed out after processing {total_items_processed} items"
        
        # Check total items limit
        if total_items_processed >= RESOURCE_LIMITS["MAX_TOTAL_ITEMS"]:
            return f"Warning: Reached maximum item limit ({RESOURCE_LIMITS['MAX_TOTAL_ITEMS']})"
        
        # Process realm with limits...
        items_to_process = min(
            top_items, 
            RESOURCE_LIMITS["MAX_TOTAL_ITEMS"] - total_items_processed
        )
        
        # ... existing processing code with items_to_process limit
    
    # Update rate limit cache
    analysis_cache[last_update_key] = datetime.now()
    
    return result


def calculate_historical_data_memory():
    """Calculate approximate memory usage of historical data in MB"""
    total_size = 0
    for key, data in historical_data.items():
        # Approximate: 50 bytes per data point
        total_size += len(data.get("data_points", [])) * 50
    return total_size / 1_000_000


def cleanup_old_historical_data():
    """Remove oldest data points to stay within memory limits"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Cleaning up old historical data to free memory...")
    
    # Sort items by number of data points (clean up largest first)
    items_by_size = sorted(
        historical_data.items(), 
        key=lambda x: len(x[1].get("data_points", [])), 
        reverse=True
    )
    
    for key, data in items_by_size[:100]:  # Clean up top 100 largest
        data_points = data.get("data_points", [])
        if len(data_points) > RESOURCE_LIMITS["MAX_DATA_POINTS_PER_ITEM"]:
            # Keep only recent data points
            data["data_points"] = data_points[-RESOURCE_LIMITS["MAX_DATA_POINTS_PER_ITEM"]:]


# Additional security recommendations:
"""
1. Implement request signing/authentication for the MCP endpoint
2. Add IP-based rate limiting at the web server level (nginx/Heroku)
3. Use Redis for distributed rate limiting across multiple dynos
4. Implement circuit breaker pattern for Blizzard API calls
5. Add monitoring/alerting for resource usage spikes
6. Consider using background job queue (Celery/RQ) for large updates
7. Implement graceful degradation when limits are reached
"""