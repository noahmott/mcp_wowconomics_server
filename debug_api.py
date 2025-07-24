#!/usr/bin/env python3
"""
Debug API endpoint issues
"""

import os
import asyncio
from dotenv import load_dotenv
from app.api.blizzard_client import BlizzardAPIClient

async def debug_guild_lookup():
    """Debug guild lookup issues"""
    load_dotenv()
    
    async with BlizzardAPIClient() as client:
        # Test the exact same guild that worked in our test
        realm = "area-52"
        guild = "ethereal"
        
        print(f"[DEBUG] Testing guild lookup: {guild} on {realm}")
        print(f"[DEBUG] Region: {client.region}")
        print(f"[DEBUG] Locale: {client.locale}")
        
        try:
            # Test basic guild info
            print("\n[TEST] Getting guild info...")
            guild_info = await client.get_guild_info(realm, guild)
            print(f"[OK] Guild info retrieved: {guild_info.get('name')}")
            
            # Test guild roster
            print("\n[TEST] Getting guild roster...")
            guild_roster = await client.get_guild_roster(realm, guild)
            print(f"[OK] Roster retrieved: {len(guild_roster.get('members', []))} members")
            
            # Test full comprehensive data (what the bot actually calls)
            print("\n[TEST] Getting comprehensive guild data...")
            comprehensive_data = await client.get_comprehensive_guild_data(realm, guild)
            print(f"[OK] Comprehensive data retrieved")
            print(f"   - Guild: {comprehensive_data['guild_info'].get('name')}")
            print(f"   - Members processed: {len(comprehensive_data['members_data'])}")
            
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_guild_lookup())