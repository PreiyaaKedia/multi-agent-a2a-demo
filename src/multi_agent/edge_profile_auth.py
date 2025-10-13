import subprocess
import urllib.parse
import secrets
import string
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

class AuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the authorization code from the callback
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        if 'code' in query_params:
            # Store the code globally so we can access it
            AuthCallbackHandler.auth_code = query_params['code'][0]
            
            # Send a response to the browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                <body>
                    <h2>Authentication Successful!</h2>
                    <p>You can close this window and return to your application.</p>
                </body>
                </html>
            ''')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h2>Authentication Failed</h2></body></html>')
    
    def log_message(self, format, *args):
        # Suppress logging
        pass

def launch_edge_with_profile(url, profile_name="Default"):
    """Launch Edge with specific profile"""
    edge_exe = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    
    # Alternative paths for Edge
    edge_paths = [
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    ]
    
    edge_exe = None
    for path in edge_paths:
        if os.path.exists(path):
            edge_exe = path
            break
    
    if not edge_exe:
        print("Microsoft Edge not found. Please install Edge or update the path.")
        return False
    
    try:
        # Launch Edge with specific profile
        subprocess.run([
            edge_exe,
            f"--profile-directory={profile_name}",
            "--new-window",
            url
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch Edge: {e}")
        return False

def get_access_token_interactive(client_id, tenant_id, profile_name="Profile 1"):
    """Get access token using interactive flow with specific Edge profile"""
    
    # Configuration
    redirect_uri = "http://localhost:8080"
    scope = "https://api.powerplatform.com/.default"
    state = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Build authorization URL
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
        'prompt': 'select_account'
    }
    
    auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    # Start local server to handle callback
    AuthCallbackHandler.auth_code = None
    server = HTTPServer(('localhost', 8080), AuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_request)
    server_thread.daemon = True
    server_thread.start()
    
    print(f"Starting authentication with Edge profile: {profile_name}")
    print("A browser window will open for authentication...")
    
    # Launch Edge with specific profile
    if not launch_edge_with_profile(auth_url_with_params, profile_name):
        print("Failed to launch Edge. Please copy and paste this URL in your preferred browser profile:")
        print(auth_url_with_params)
    
    # Wait for callback
    print("Waiting for authentication callback...")
    timeout = 300  # 5 minutes
    start_time = time.time()
    
    while AuthCallbackHandler.auth_code is None and (time.time() - start_time) < timeout:
        time.sleep(1)
    
    server.shutdown()
    
    if AuthCallbackHandler.auth_code is None:
        print("Authentication timed out or failed.")
        return None
    
    # Exchange authorization code for access token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        'client_id': client_id,
        'code': AuthCallbackHandler.auth_code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'scope': scope
    }
    
    response = requests.post(token_url, data=token_data)
    
    if response.status_code == 200:
        token_response = response.json()
        return {
            'access_token': token_response['access_token'],
            'token_type': token_response.get('token_type', 'Bearer'),
            'expires_in': token_response.get('expires_in')
        }
    else:
        print(f"Token exchange failed: {response.status_code}")
        print(response.text)
        return None

# Example usage
if __name__ == "__main__":
    # Configuration
    CLIENT_ID = "YOUR_CLIENT_ID"  # Replace with your actual client ID
    TENANT_ID = "MngEnvMCAP643700.onmicrosoft.com"
    EDGE_PROFILE = "Profile 1"  # Change this to your desired profile name
    
    # Get access token
    token_info = get_access_token_interactive(CLIENT_ID, TENANT_ID, EDGE_PROFILE)
    
    if token_info:
        print(f"\nAuthentication successful!")
        print(f"Access Token: {token_info['access_token'][:50]}...")
        print(f"Token Type: {token_info['token_type']}")
        print(f"Expires In: {token_info['expires_in']} seconds")
    else:
        print("Authentication failed.")