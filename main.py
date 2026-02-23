"""
main.py - Spotify Overlay Main Entry Point
-----------------------------------------
Production-ready main application with proper error handling.
"""

import sys
import os
import traceback

# Add current directory to Python path for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = sys._MEIPASS
else:
    # Running as script
    application_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, application_path)

try:
    from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
    from PySide6.QtCore import QSharedMemory, Qt
except ImportError as e:
    print(f"PySide6 import error: {e}")
    input("Press Enter to exit...")
    sys.exit(1)

def resource_path(relative_path):
    """Get absolute path for resources (works for dev and PyInstaller)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = sys._MEIPASS
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)

def load_environment_variables():
    """Load environment variables from .env file"""
    env_vars = {}
    env_path = resource_path(".env")
    
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip().strip('"\'')
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")
    
    # Add system environment variables
    env_vars.update(os.environ)
    return env_vars

def main():
    """Main application entry point"""
    
    # Enable high DPI support for modern displays
    if hasattr(QApplication, 'setHighDpiScaleFactorRoundingPolicy'):
        # Use the correct enum value instead of boolean
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Spotify Overlay")
    app.setApplicationVersion("2.0")
    
    # Show welcome message first
    reply = QMessageBox.question(
        None, "Welcome to Spotify Overlay",
        "Welcome to Spotify Overlay!\n\n"
        "This app creates a transparent overlay to control Spotify while you game or stream.\n\n"
        "Do you want to run the setup wizard now?",
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.No:
        return 0
    
    # Prevent multiple instances
    try:
        app_lock = QSharedMemory("SpotifyOverlay_v2_InstanceLock")
        if not app_lock.create(1):
            QMessageBox.information(None, "Already Running", 
                                  "Spotify Overlay is already running.\nCheck your system tray or taskbar.")
            return 0
    except Exception as e:
        print(f"Shared memory lock not available: {e}")
        # Continue without lock if not available
    
    try:
        # Try to import the modules dynamically
        try:
            from spotify_api import SpotifyAPI
            from ui_main import MainWindow
            from setup_wizard import EnhancedSetupWizard
        except ImportError as e:
            QMessageBox.critical(None, "Import Error", 
                               f"Failed to load application modules:\n{str(e)}\n\n"
                               "Please ensure all files are in the same directory.")
            return 1
        
        # Load environment
        env_vars = load_environment_variables()
        client_id = env_vars.get("SPOTIFY_CLIENT_ID")
        client_secret = env_vars.get("SPOTIFY_CLIENT_SECRET") 
        redirect_uri = env_vars.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
        
        # Check if setup is needed
        if not client_id or not client_secret:
            # Run enhanced setup wizard
            wizard = EnhancedSetupWizard()
            if wizard.exec() != QDialog.Accepted:
                return 0
            
            # Reload environment after setup
            env_vars = load_environment_variables()
            client_id = env_vars.get("SPOTIFY_CLIENT_ID")
            client_secret = env_vars.get("SPOTIFY_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                QMessageBox.warning(None, "Setup Incomplete", 
                                  "Setup was not completed. Please run the application again to set up Spotify integration.")
                return 0
        
        # Initialize Spotify API
        try:
            spotify = SpotifyAPI(client_id, client_secret, redirect_uri)
        except Exception as e:
            QMessageBox.critical(None, "API Error", 
                               f"Failed to initialize Spotify API:\n{str(e)}")
            return 1
        
        # Check if we need authentication
        if not spotify.access_token:
            try:
                QMessageBox.information(None, "Authentication Required",
                                      "The application will now open your browser for Spotify authentication.\n\n"
                                      "Please grant the required permissions to continue.")
                spotify.authorize()
            except Exception as e:
                QMessageBox.critical(None, "Authentication Failed",
                                   f"Spotify authentication failed:\n{str(e)}\n\n"
                                   "Please check your internet connection and try again.")
                return 1
        
        # Create and show main window
        window = MainWindow(spotify)
        window.show()
        
        # Show welcome message on first run
        if not os.path.exists('spotify_tokens.json'):
            QMessageBox.information(window, "Welcome to Spotify Overlay",
                                  "The overlay is now active!\n\n"
                                  "Tips:\n"
                                  "• Drag the overlay to reposition it\n" 
                                  "• Hover to show controls\n"
                                  "• Use keyboard shortcuts for quick control\n"
                                  "• The overlay stays on top of other windows\n\n"
                                  "Keyboard Shortcuts:\n"
                                  "Ctrl+Shift+Space - Play/Pause\n"
                                  "Ctrl+Shift+N - Next Track\n" 
                                  "Ctrl+Shift+B - Previous Track\n"
                                  "Ctrl+Shift+Q - Show Queue\n"
                                  "Ctrl+Shift+L - Show Playlists")
        
        # Start application loop
        return app.exec()
        
    except Exception as e:
        # Handle unexpected errors gracefully
        error_details = traceback.format_exc()
        
        QMessageBox.critical(None, "Application Error",
                           f"The application encountered an unexpected error:\n\n{str(e)}\n\n"
                           "Please restart the application. If the problem persists, "
                           "check that all required files are in the same directory.")
        return 1
    
    finally:
        # Clean up shared memory lock
        try:
            if 'app_lock' in locals() and app_lock.isAttached():
                app_lock.detach()
        except:
            pass

if __name__ == "__main__":
    sys.exit(main())
