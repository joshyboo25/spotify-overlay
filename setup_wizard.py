"""
setup_wizard.py - Spotify Setup Wizard v2.0
-------------------------------------------
User-friendly setup with automatic validation and detailed guidance.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                              QPushButton, QMessageBox, QHBoxLayout, 
                              QProgressBar, QTextEdit, QTabWidget, QWidget)
from PySide6.QtCore import Qt, QThread, Signal
import webbrowser
import os
import requests
import sys
import base64


class SetupWorker(QThread):
    """Background worker for credential validation"""
    validation_complete = Signal(bool, str)
    
    def __init__(self, client_id, client_secret):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
    
    def run(self):
        try:
            # Test the credentials with a simple API call
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers = {'Authorization': f'Basic {encoded}'}
            
            response = requests.post(
                'https://accounts.spotify.com/api/token',
                headers=headers,
                data={'grant_type': 'client_credentials'}
            )
            
            if response.status_code == 200:
                self.validation_complete.emit(True, "✅ Credentials are valid!")
            else:
                self.validation_complete.emit(False, f"❌ Invalid credentials (Error {response.status_code})")
                
        except Exception as e:
            self.validation_complete.emit(False, f"❌ Validation failed: {str(e)}")


class EnhancedSetupWizard(QDialog):
    """Enhanced setup wizard with validation and better UX"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Overlay Setup")
        self.setFixedSize(700, 600)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the enhanced setup wizard UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("🎵 Spotify Overlay Setup")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1DB954; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Tab widget for organized setup
        tab_widget = QTabWidget()
        
        # Setup Tab
        setup_tab = self.create_setup_tab()
        tab_widget.addTab(setup_tab, "🔧 Setup")
        
        # Instructions Tab
        instructions_tab = self.create_instructions_tab()
        tab_widget.addTab(instructions_tab, "📖 Detailed Guide")
        
        # Troubleshooting Tab
        troubleshooting_tab = self.create_troubleshooting_tab()
        tab_widget.addTab(troubleshooting_tab, "🔍 Troubleshooting")
        
        layout.addWidget(tab_widget)
        
        # Status area
        self.status_label = QLabel("Ready to set up...")
        self.status_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        test_button = QPushButton("🧪 Test Credentials")
        test_button.clicked.connect(self.test_credentials)
        button_layout.addWidget(test_button)
        
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        self.save_button = QPushButton("💾 Save & Launch")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #1ed760; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.save_button.clicked.connect(self.save_and_launch)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
    
    def create_setup_tab(self):
        """Create the main setup tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Quick start section
        quick_start = QLabel("""
        <h3>🚀 Quick Start (2 minutes)</h3>
        <ol>
        <li>Click "Open Spotify Developer Dashboard" below</li>
        <li>Click "Create App" and fill in the form</li>
        <li>Copy your Client ID and Client Secret</li>
        <li>Paste them in the fields below</li>
        <li>Click "Test Credentials" to verify</li>
        <li>Click "Save & Launch" to start using the overlay!</li>
        </ol>
        """)
        quick_start.setWordWrap(True)
        layout.addWidget(quick_start)
        
        # Open Dashboard button
        dash_button = QPushButton("🎵 Open Spotify Developer Dashboard")
        dash_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #1ed760; }
        """)
        dash_button.clicked.connect(self.open_developer_dashboard)
        layout.addWidget(dash_button)
        
        # Credential fields
        cred_layout = QVBoxLayout()
        cred_layout.setSpacing(8)
        
        # Client ID
        cred_layout.addWidget(QLabel("<b>Client ID:</b>"))
        self.client_id_field = QLineEdit()
        self.client_id_field.setPlaceholderText("Paste your Client ID here (starts with numbers and letters)")
        self.client_id_field.textChanged.connect(self.validate_fields)
        cred_layout.addWidget(self.client_id_field)
        
        # Client Secret
        cred_layout.addWidget(QLabel("<b>Client Secret:</b>"))
        self.client_secret_field = QLineEdit()
        self.client_secret_field.setPlaceholderText("Paste your Client Secret here (long string of letters and numbers)")
        self.client_secret_field.setEchoMode(QLineEdit.Password)
        self.client_secret_field.textChanged.connect(self.validate_fields)
        cred_layout.addWidget(self.client_secret_field)
        
        # Redirect URI (read-only)
        cred_layout.addWidget(QLabel("<b>Redirect URI (copy this to your app):</b>"))
        self.redirect_uri_field = QLineEdit("http://localhost:8888/callback")
        self.redirect_uri_field.setReadOnly(True)
        self.redirect_uri_field.setStyleSheet("background: #e9e9e9;")
        cred_layout.addWidget(self.redirect_uri_field)
        
        layout.addLayout(cred_layout)
        layout.addStretch()
        
        return widget
    
    def create_instructions_tab(self):
        """Create detailed instructions tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setHtml("""
        <h2>Detailed Setup Instructions</h2>
        
        <h3>Step 1: Create Spotify Developer App</h3>
        <ol>
        <li>Visit <a href="https://developer.spotify.com/dashboard/">Spotify Developer Dashboard</a></li>
        <li>Log in with your Spotify account (use the same account you want to control)</li>
        <li>Click "Create App"</li>
        <li>Fill in the form:
          <ul>
          <li><b>App Name:</b> "Spotify Overlay" or any name you prefer</li>
          <li><b>App Description:</b> "Overlay for controlling Spotify during streams"</li>
          <li><b>Redirect URI:</b> <code>http://localhost:8888/callback</code></li>
          </ul>
        </li>
        <li>Agree to the terms and click "Create"</li>
        </ol>
        
        <h3>Step 2: Get Your Credentials</h3>
        <ol>
        <li>On your app's page, find "Client ID" and click "Show Client Secret"</li>
        <li>Copy the Client ID (looks like: <code>a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6</code>)</li>
        <li>Copy the Client Secret (long string of letters/numbers)</li>
        <li>Paste them in the setup tab</li>
        </ol>
        
        <h3>Step 3: Test and Launch</h3>
        <ol>
        <li>Click "Test Credentials" to verify they work</li>
        <li>If successful, click "Save & Launch"</li>
        <li>The app will open Spotify for authorization - click "Agree"</li>
        <li>You're all set! The overlay will appear on your screen</li>
        </ol>
        
        <h3>💡 Pro Tips</h3>
        <ul>
        <li>Keep your browser open during setup</li>
        <li>Make sure Spotify is installed on your computer</li>
        <li>The overlay works best when Spotify is active</li>
        <li>You can reposition the overlay by dragging it</li>
        </ul>
        """)
        
        layout.addWidget(instructions)
        return widget
    
    def create_troubleshooting_tab(self):
        """Create troubleshooting tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        troubleshooting = QTextEdit()
        troubleshooting.setReadOnly(True)
        troubleshooting.setHtml("""
        <h2>Common Issues & Solutions</h2>
        
        <h3>🔑 Credential Issues</h3>
        <p><b>Problem:</b> "Invalid credentials" error</p>
        <ul>
        <li>Make sure you copied the entire Client ID and Client Secret</li>
        <li>Check for extra spaces before/after the text</li>
        <li>Ensure the Redirect URI matches exactly: <code>http://localhost:8888/callback</code></li>
        <li>Try creating a new app in the Spotify Developer Dashboard</li>
        </ul>
        
        <h3>🌐 Connection Issues</h3>
        <p><b>Problem:</b> "Cannot connect to Spotify"</p>
        <ul>
        <li>Check your internet connection</li>
        <li>Make sure Spotify's servers aren't down</li>
        <li>Try disabling your firewall temporarily</li>
        <li>Ensure port 8888 is available (the app will try others if needed)</li>
        </ul>
        
        <h3>🔐 Authorization Issues</h3>
        <p><b>Problem:</b> Browser doesn't open or authorization fails</p>
        <ul>
        <li>Make sure you're logged into Spotify in your browser</li>
        <li>Check that pop-ups aren't blocked for the Spotify site</li>
        <li>Try using a different browser if issues persist</li>
        <li>Ensure you click "Agree" on the authorization page</li>
        </ul>
        
        <h3>📱 Overlay Not Working</h3>
        <p><b>Problem:</b> Overlay appears but doesn't control Spotify</p>
        <ul>
        <li>Make sure Spotify is running on your computer</li>
        <li>Try playing music in Spotify first</li>
        <li>Check that the overlay has focus (click on it once)</li>
        <li>Restart both Spotify and the Overlay app</li>
        </ul>
        
        <h3>🆘 Still Having Issues?</h3>
        <p>If you continue to have problems:</p>
        <ol>
        <li>Take a screenshot of any error messages</li>
        <li>Check the application logs in the same folder</li>
        <li>Visit the GitHub page for more help</li>
        <li>Contact support with your issue details</li>
        </ol>
        """)
        
        layout.addWidget(troubleshooting)
        return widget
    
    def open_developer_dashboard(self):
        """Open Spotify developer dashboard in browser"""
        webbrowser.open("https://developer.spotify.com/dashboard")
        self.status_label.setText("✅ Opened Spotify Developer Dashboard - follow the instructions there")
    
    def validate_fields(self):
        """Enable save button only if fields are filled"""
        has_id = bool(self.client_id_field.text().strip())
        has_secret = bool(self.client_secret_field.text().strip())
        self.save_button.setEnabled(has_id and has_secret)
    
    def test_credentials(self):
        """Test the entered credentials"""
        client_id = self.client_id_field.text().strip()
        client_secret = self.client_secret_field.text().strip()
        
        if not client_id or not client_secret:
            QMessageBox.warning(self, "Missing Information", 
                              "Please enter both Client ID and Client Secret")
            return
        
        self.progress_bar.setVisible(True)
        self.status_label.setText("Testing credentials...")
        
        # Start validation in background thread
        self.worker = SetupWorker(client_id, client_secret)
        self.worker.validation_complete.connect(self.on_validation_complete)
        self.worker.start()
    
    def on_validation_complete(self, success, message):
        """Handle validation result"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        
        if success:
            QMessageBox.information(self, "Success", 
                                  "Your credentials are valid!\n\nClick 'Save & Launch' to start using the overlay.")
        else:
            QMessageBox.warning(self, "Validation Failed", 
                              f"Credential test failed:\n{message}\n\nCheck the troubleshooting tab for help.")
    
    def save_and_launch(self):
        """Save credentials and close wizard"""
        client_id = self.client_id_field.text().strip()
        client_secret = self.client_secret_field.text().strip()
        
        try:
            # Save to .env file
            with open('.env', 'w') as f:
                f.write(f"SPOTIFY_CLIENT_ID={client_id}\n")
                f.write(f"SPOTIFY_CLIENT_SECRET={client_secret}\n")
                f.write("SPOTIFY_REDIRECT_URI=http://localhost:8888/callback\n")
            
            # Create a basic README for the user
            with open('QUICK_START.txt', 'w') as f:
                f.write("""
Spotify Overlay - Quick Start Guide
===================================

Your setup is complete! Here's how to use the overlay:

1. The overlay will appear on your screen automatically
2. Hover over it to see controls
3. Drag to reposition anywhere on screen
4. Keyboard shortcuts:
   - Ctrl+Shift+Space: Play/Pause
   - Ctrl+Shift+N: Next Track
   - Ctrl+Shift+B: Previous Track
   - Ctrl+Shift+Q: Show Queue
   - Ctrl+Shift+L: Show Playlists

Need Help?
- Check QUICK_START.txt (this file)
- Visit the GitHub page
- Contact support if issues persist

Enjoy your Spotify Overlay!
                """)
            
            QMessageBox.information(self, "Setup Complete", 
                                  "Credentials saved successfully!\n\nThe application will now launch.")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"Failed to save credentials:\n{str(e)}")
