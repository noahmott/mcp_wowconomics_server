# WoW Classic API Integration Notes

## Overview
This document outlines the differences between WoW Classic and Retail APIs and how they are handled in this codebase.

## Namespace Differences

### Classic Namespaces
- **Data endpoints**: `static-classic-{region}` (e.g., `static-classic-us`)
- **Profile endpoints**: `profile-classic-{region}` (e.g., `profile-classic-us`)

### Retail Namespaces
- **Data endpoints**: `dynamic-{region}` (e.g., `dynamic-us`)
- **Profile endpoints**: `profile-{region}` (e.g., `profile-us`)

## Response Format Differences

### Item Names
- **Classic**: Names are returned as simple strings
  ```json
  {
    "name": "Thunderfury, Blessed Blade of the Windseeker"
  }
  ```
- **Retail**: Names are returned as nested objects with language codes
  ```json
  {
    "name": {
      "en_US": "Thunderfury, Blessed Blade of the Windseeker",
      "es_MX": "Trueno Furioso, Espada Bendita del Hijo del Viento"
    }
  }
  ```

### Available Endpoints

#### Working Classic Endpoints
- `/data/wow/item/{itemId}` - Item data (uses `static-classic-{region}`)
- `/data/wow/realm/{realmSlug}` - Realm information (uses `dynamic-classic-{region}`)
- `/data/wow/connected-realm/{id}/auctions` - **Auction house data** (uses `dynamic-classic-{region}`)
- `/data/wow/guild/{realmSlug}/{guildName}` - Guild information
- `/data/wow/guild/{realmSlug}/{guildName}/roster` - Guild roster
- `/data/wow/search/realm` - Realm search

#### Not Available in Classic
- `/data/wow/realm/index` - Returns 404 (use search endpoint instead)
- `/data/wow/auctions/commodities` - Retail only
- Various modern features like Mythic+ data

#### Confirmed Working Classic Realms (US)
- Mankrik (Connected Realm ID: 4384)
- Faerlina (Connected Realm ID: 4408) 
- Benediction (Connected Realm ID: 4728)
- Grobbulus (Connected Realm ID: 4647)

## Configuration

### Environment Variables
- `WOW_VERSION`: Set to `"classic"` or `"retail"` (defaults to `"classic"`)
- `UPDATE_BOTH_VERSIONS`: Set to `"true"` to update both Classic and Retail data in scheduled updates

### Database Schema
All tables include a `game_version` field to differentiate between Classic and Retail data:
- `game_version`: String field with values `"classic"` or `"retail"`

## Testing

### Docker Test Commands
```bash
# Build test container
docker compose -f docker-compose.simple-test.yml build

# Test Classic API
docker compose -f docker-compose.simple-test.yml run --rm test-classic python test_classic_fixed.py

# Test auction data collection
python test_classic_auction_final.py
```

### Test Results (July 2025)
- **Classic Auction House API**: ✓ Working perfectly
  - Mankrik: 61,592 auctions, 8,817 unique items
  - Faerlina: 59,556 auctions, 8,052 unique items
  - Benediction: 56,632 auctions, 8,221 unique items
  - Grobbulus: 19,838 auctions, 4,930 unique items
- **Retail Auction House API**: ✓ Working perfectly
  - Area-52: 112,019 auctions, 16,258 unique items
  - Stormrage: 118,318 auctions, 16,204 unique items
- **Classic Items API**: ✓ Working (5/5 legendary items found)
- **Classic Realm Data**: ✓ Working with `dynamic-classic-{region}` namespace

## Implementation Details

### BlizzardAPIClient
The client automatically switches namespaces based on:
1. Constructor parameter: `BlizzardAPIClient(game_version="classic")`
2. Environment variable: `WOW_VERSION`
3. Default: `"classic"`

### Response Parsing
When parsing API responses, always check the data format:
```python
# Handle both Classic (string) and Retail (object) name formats
if isinstance(data.get('name'), str):
    name = data['name']  # Classic format
else:
    name = data.get('name', {}).get('en_US', 'Unknown')  # Retail format
```

## Known Issues
1. Classic realm endpoints may return 404
2. Some item IDs exist only in Classic or only in Retail
3. Response formats differ between versions requiring careful parsing