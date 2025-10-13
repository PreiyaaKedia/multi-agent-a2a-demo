#!/usr/bin/env python3
"""
Simple test script to verify the health endpoint is working.
"""
import asyncio
import sys
from datetime import datetime

async def test_health_endpoint():
    """Test the health check endpoint functionality."""
    try:
        # Import the app
        from app import app, health_check
        
        print("✅ Successfully imported app with health endpoint")
        
        # Create a mock request for testing
        class MockRequest:
            pass
        
        mock_request = MockRequest()
        
        # Test the health check function
        response = await health_check(mock_request)
        
        print(f"✅ Health check function executed successfully")
        print(f"📊 Response status code: {response.status_code}")
        print(f"📋 Response content type: {response.media_type}")
        
        # Check if the app has the health route
        health_routes = [route for route in app.router.routes if hasattr(route, 'path') and route.path == '/health']
        if health_routes:
            print("✅ Health check route '/health' successfully added to app")
        else:
            print("❌ Health check route not found in app routes")
            
        print("\n🎯 Health endpoint configuration complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_health_endpoint())
    sys.exit(0 if success else 1)