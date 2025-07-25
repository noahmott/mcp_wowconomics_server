"""
Simple test for WoW Analysis Server
"""
import requests
import json

MCP_SERVER_URL = "https://wow-guild-mcp-server-7f17b3f6ea0a.herokuapp.com"

def test_mcp_tool(tool_name, arguments):
    """Test a single MCP tool"""
    print(f"\nTesting: {tool_name}")
    print(f"Arguments: {json.dumps(arguments)}")
    print("-" * 50)
    
    # Prepare request
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    request_data = {
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    try:
        # Make request
        response = requests.post(
            f"{MCP_SERVER_URL}/sse",
            json=request_data,
            headers=headers,
            timeout=30,
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Read SSE stream
            full_text = ""
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        data = line_text[6:]
                        if data != "[DONE]":
                            try:
                                event = json.loads(data)
                                if "content" in event and isinstance(event["content"], list):
                                    for item in event["content"]:
                                        if "text" in item:
                                            full_text += item["text"]
                            except:
                                pass
            
            # Print first 500 chars of response
            print("Response Preview:")
            print(full_text[:500] + "..." if len(full_text) > 500 else full_text)
            return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def main():
    print("WoW Analysis Server Simple Test")
    print("=" * 50)
    
    # Test 1: Help guide (simplest)
    print("\nTEST 1: Help Guide")
    test_mcp_tool("get_analysis_help", {})
    
    # Test 2: Market opportunities
    print("\n\nTEST 2: Market Opportunities")
    test_mcp_tool("analyze_market_opportunities", {
        "realm_slug": "stormrage",
        "region": "us"
    })
    
    # Test 3: Market predictions
    print("\n\nTEST 3: Market Predictions")
    test_mcp_tool("predict_market_trends", {
        "realm_slug": "stormrage", 
        "region": "us"
    })

if __name__ == "__main__":
    main()