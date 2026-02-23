"""
spotify_api.py - Spotify API Wrapper
-----------------------------------
Production-ready Spotify API integration with token management.
"""

import requests
import base64
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json
import time
import os
import threading
import socket


class SpotifyAPI:
    """Spotify Web API wrapper with OAuth2 authentication"""
    
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.auth_code = None
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from persistent storage"""
        try:
            if os.path.exists('spotify_tokens.json'):
                with open('spotify_tokens.json', 'r') as f:
                    tokens = json.load(f)
                    self.access_token = tokens.get('access_token')
                    self.refresh_token = tokens.get('refresh_token')
                    self.token_expiry = tokens.get('expiry_time')
                    
                    # Check if token is still valid
                    if self.token_expiry and time.time() < self.token_expiry:
                        return True
                    elif self.refresh_token:
                        # Token expired but we have refresh token
                        return self._refresh_access_token()
        except Exception as e:
            print(f"Error loading tokens: {e}")
        return False

    def _save_tokens(self):
        """Save tokens to persistent storage"""
        try:
            tokens = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expiry_time': self.token_expiry
            }
            with open('spotify_tokens.json', 'w') as f:
                json.dump(tokens, f)
        except Exception as e:
            print(f"Error saving tokens: {e}")

    def _make_auth_header(self):
        """Create Basic Auth header"""
        auth_string = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        return {'Authorization': f'Basic {encoded}'}

    def authorize(self):
        """Start OAuth2 authorization flow"""
        # Generate auth URL
        scope = 'user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private'
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': scope,
            'show_dialog': 'true'
        }
        
        auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
        webbrowser.open(auth_url)
        
        # Start local server to handle callback
        if self._start_callback_server():
            print("Successfully authenticated with Spotify")
        else:
            raise Exception("Authorization failed or was cancelled")

    def _start_callback_server(self):
        """Start local HTTP server to capture OAuth callback"""
        class CallbackHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.spotify_api = kwargs.pop('spotify_api')
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                # Parse callback URL
                parsed_path = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_path.query)
                
                if 'code' in query_params:
                    self.spotify_api.auth_code = query_params['code'][0]
                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    # Use ASCII-only characters for compatibility
                    success_html = '''
                        <html>
                        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                            <h1>Authentication Successful!</h1>
                            <p>You can now close this window and return to the Spotify Overlay.</p>
                        </body>
                        </html>
                    '''
                    self.wfile.write(success_html.encode('utf-8'))
                    
                    # Exchange code for tokens
                    self.spotify_api._exchange_code_for_tokens()
                else:
                    # Error handling
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Authentication failed: No code received')
                
                # Signal server to shutdown
                self.server.shutdown_signal = True
            
            def log_message(self, format, *args):
                # Suppress server logs
                pass
        
        # Find an available port
        port = 8888
        max_attempts = 10
        
        for attempt in range(max_attempts):
            try:
                server = HTTPServer(('localhost', port), 
                                  lambda *args, **kwargs: CallbackHandler(*args, spotify_api=self, **kwargs))
                server.shutdown_signal = False
                break
            except OSError as e:
                if e.errno == 48 or e.errno == 10048:  # Port already in use
                    port += 1
                    continue
                else:
                    raise e
        else:
            raise Exception("Could not find an available port for callback server")
        
        print(f"Waiting for Spotify authorization on port {port}...")
        
        # Start server in a thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for shutdown signal with timeout
        timeout = 120  # 2 minutes timeout
        start_time = time.time()
        
        while not server.shutdown_signal:
            if time.time() - start_time > timeout:
                server.shutdown()
                raise Exception("Authorization timeout - please try again")
            time.sleep(0.1)
        
        server.shutdown()
        server_thread.join(timeout=1)
        
        return self.auth_code is not None

    def _exchange_code_for_tokens(self):
        """Exchange authorization code for access and refresh tokens"""
        url = 'https://accounts.spotify.com/api/token'
        headers = self._make_auth_header()
        data = {
            'grant_type': 'authorization_code',
            'code': self.auth_code,
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens['access_token']
            self.refresh_token = tokens['refresh_token']
            self.token_expiry = time.time() + tokens['expires_in'] - 60  # 60 second buffer
            self._save_tokens()
            return True
        else:
            raise Exception(f"Token exchange failed: {response.text}")

    def _refresh_access_token(self):
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            return False
            
        url = 'https://accounts.spotify.com/api/token'
        headers = self._make_auth_header()
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens['access_token']
            self.token_expiry = time.time() + tokens['expires_in'] - 60
            # Refresh token may be renewed
            if 'refresh_token' in tokens:
                self.refresh_token = tokens['refresh_token']
            self._save_tokens()
            return True
        else:
            # Refresh token invalid, need reauthentication
            self.access_token = None
            self.refresh_token = None
            self._save_tokens()
            return False

    def _ensure_valid_token(self):
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expiry and time.time() >= self.token_expiry):
            if not self._refresh_access_token():
                raise Exception("Authentication required - please reauthorize")

    def _api_request(self, endpoint, method='GET', data=None):
        """Make authenticated API request with token refresh"""
        self._ensure_valid_token()
        
        url = f'https://api.spotify.com/v1{endpoint}'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        response = requests.request(method, url, headers=headers, json=data)
        
        if response.status_code == 401:  # Token might be expired
            self._refresh_access_token()
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.request(method, url, headers=headers, json=data)
        
        return response

    # Public API Methods
    def get_current_playback(self):
        """Get current playback state"""
        response = self._api_request('/me/player')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            return None  # No active playback
        else:
            raise Exception(f"Playback request failed: {response.status_code}")

    def get_queue(self):
        """Get current queue"""
        response = self._api_request('/me/player/queue')
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Queue request failed: {response.status_code}")

    def get_playlists(self, limit=20):
        """Get user's playlists"""
        response = self._api_request(f'/me/playlists?limit={limit}')
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Playlists request failed: {response.status_code}")

    def play_playlist(self, playlist_id):
        """Start playing a playlist"""
        data = {'context_uri': f'spotify:playlist:{playlist_id}'}
        response = self._api_request('/me/player/play', 'PUT', data)
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Play playlist failed: {response.status_code}")

    def next_track(self):
        """Skip to next track"""
        response = self._api_request('/me/player/next', 'POST')
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Next track failed: {response.status_code}")

    def previous_track(self):
        """Go to previous track"""
        response = self._api_request('/me/player/previous', 'POST')
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Previous track failed: {response.status_code}")

    def pause(self):
        """Pause playback"""
        response = self._api_request('/me/player/pause', 'PUT')
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Pause failed: {response.status_code}")

    def play(self):
        """Resume playback"""
        response = self._api_request('/me/player/play', 'PUT')
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Play failed: {response.status_code}")

    def set_volume(self, volume):
        """Set volume (0-100)"""
        response = self._api_request(f'/me/player/volume?volume_percent={volume}', 'PUT')
        if response.status_code not in [200, 202, 204]:
            raise Exception(f"Set volume failed: {response.status_code}")
