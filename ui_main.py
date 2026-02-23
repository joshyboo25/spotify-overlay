"""
ui_main.py - Spotify Viewer UI v1.2 (Production Ready)
-----------------------------------------------------
Fully functional transparent overlay for Spotify control.
"""

import sys
import os
import logging
import requests
from typing import Optional

# Core UI Components
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSlider, QListWidget, QListWidgetItem, QGraphicsDropShadowEffect
)

# Drawing & Input
from PySide6.QtGui import (
    QPainter, QLinearGradient, QColor, QPixmap, QKeySequence, 
    QPen, QShortcut, QCursor, QPainterPath
)

# Logic & Concurrency
from PySide6.QtCore import (
    Qt, QTimer, QPoint, Signal, QRectF, QObject, QRunnable, 
    QThreadPool, QRect
)

# ---------------------------------------------------------------------
# SYSTEM LOGGING
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SpotifyOverlay")

# ---------------------------------------------------------------------
# THEME: GAMING TRANSPARENCY (20% OPACITY)
# ---------------------------------------------------------------------
class Theme:
    """Visual theme constants"""
    ALPHA_BASE = 51  # 20% opacity
    ALPHA_HOVER = 120
    
    # Colors
    BG_NORMAL = QColor(10, 10, 10, ALPHA_BASE)  
    BG_HOVER = QColor(25, 25, 25, ALPHA_HOVER)
    ACCENT = QColor(0, 120, 215, 200)
    BORDER_FLUENT = QColor(255, 255, 255, 35)
    SHADOW_COLOR = QColor(0, 0, 0, 150)
    
    # Typography
    TEXT_PRIMARY = QColor(255, 255, 255, 250)
    TEXT_SECONDARY = QColor(200, 200, 200, 160)
    
    # Layout constants
    RADIUS_DEFAULT = 12
    SHADOW_BLUR = 25

# ---------------------------------------------------------------------
# ASYNC PIPELINE INFRASTRUCTURE
# ---------------------------------------------------------------------
class PipelineSignals(QObject):
    """Communication bridge for background threads"""
    playback_ready = Signal(object)
    art_ready = Signal(QPixmap)
    error_signal = Signal(str)

# ---------------------------------------------------------------------
# BACKGROUND WORKERS
# ---------------------------------------------------------------------
class ApiWorker(QRunnable):
    """Background thread for Spotify API commands"""
    def __init__(self, signals: PipelineSignals, api_func, *args, **kwargs):
        super().__init__()
        self.signals = signals
        self.api_func = api_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.api_func(*self.args, **self.kwargs)
            if self.signals:
                self.signals.playback_ready.emit(result)
        except Exception as e:
            if self.signals:
                self.signals.error_signal.emit(str(e))

class ArtLoader(QRunnable):
    """Background thread for album art loading"""
    def __init__(self, signals: PipelineSignals, url: str, size: int):
        super().__init__()
        self.signals = signals
        self.url = url
        self.size = size

    def run(self):
        try:
            if not self.url: 
                return
            res = requests.get(self.url, timeout=3)
            if res.status_code == 200:
                px = QPixmap()
                px.loadFromData(res.content)
                if not px.isNull():
                    scaled = px.scaled(self.size, self.size, 
                                     Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    if self.signals:
                        self.signals.art_ready.emit(scaled)
        except Exception as e:
            logger.error(f"Art loading failed: {str(e)}")

# ---------------------------------------------------------------------
# MIXIN: VISUAL ENGINE
# ---------------------------------------------------------------------
class GlassVisualMixin:
    """Windows 11 acrylic glass effect"""
    def paint_glass_effect(self, widget: QWidget, painter: QPainter, active: bool):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = widget.rect()
        
        # Geometry Path
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), Theme.RADIUS_DEFAULT, Theme.RADIUS_DEFAULT)
        
        # Base Layer (20% Opacity)
        bg = Theme.BG_HOVER if active else Theme.BG_NORMAL
        painter.fillPath(path, bg)
        
        # Shine Gradient
        shine = QLinearGradient(0, 0, 0, rect.height())
        shine.setColorAt(0, QColor(255, 255, 255, 20))
        shine.setColorAt(0.5, QColor(255, 255, 255, 2))
        shine.setColorAt(1, QColor(255, 255, 255, 8))
        painter.fillPath(path, shine)
        
        # Stroke Border
        border = QPen(Theme.BORDER_FLUENT)
        border.setWidth(1)
        painter.setPen(border)
        painter.drawPath(path)

# ---------------------------------------------------------------------
# CUSTOM UI COMPONENTS
# ---------------------------------------------------------------------
class FluentButton(QPushButton):
    """Custom transparent button"""
    def __init__(self, text="", parent=None, is_accent=False):
        super().__init__(text, parent)
        self.setFixedSize(36, 36)
        self.is_accent = is_accent
        self.over = False
        self.refresh_ui()

    def refresh_ui(self):
        alpha = 40 if not self.over else 100
        color = Theme.ACCENT if self.is_accent else QColor(255, 255, 255, alpha)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});
                border-radius: 18px;
                color: white;
                font-weight: bold;
                font-size: 15px;
                border: none;
            }}
            QPushButton:pressed {{ background-color: rgba(0, 120, 215, 140); }}
        """)

    def enterEvent(self, event):
        self.over = True
        self.refresh_ui()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.over = False
        self.refresh_ui()
        super().leaveEvent(event)

class FluentSlider(QSlider):
    """Custom transparent slider"""
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.is_dragging = False
        self.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; }
            QSlider::handle:horizontal { background: white; border: 2px solid #0078d7; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #0078d7; border-radius: 2px; }
        """)

    def mousePressEvent(self, ev):
        self.is_dragging = True
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self.is_dragging = False
        super().mouseReleaseEvent(ev)

# ---------------------------------------------------------------------
# FLOATING WINDOWS
# ---------------------------------------------------------------------
class FloatingBase(QWidget, GlassVisualMixin):
    """Base class for sub-windows"""
    def __init__(self, title: str, parent_ref):
        super().__init__()
        self.main_ref = parent_ref
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(350, 480)
        self.drag_pos = None

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: white; font-size: 15px;")
        
        self.close_btn = FluentButton("×", self)
        self.close_btn.clicked.connect(self.hide)
        
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.close_btn)
        layout.addLayout(header)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.paint_glass_effect(self, painter, self.underMouse())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)

class QueueWindow(FloatingBase):
    """Queue display window"""
    def __init__(self, api, parent):
        super().__init__("Next Up", parent)
        self.spotify = api
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background: transparent; border: none; color: #ddd; font-size: 12px;")
        self.layout().addWidget(self.list_widget)

    def refresh(self):
        def on_data(data):
            self.list_widget.clear()
            if data and data.get('queue'):
                for track in data['queue'][:10]:
                    artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
                    self.list_widget.addItem(f"{track['name']}\n{artists}")
        
        def fetch_queue():
            try:
                data = self.spotify.get_queue()
                on_data(data)
            except Exception as e:
                logger.error(f"Queue refresh failed: {str(e)}")
        
        QThreadPool.globalInstance().start(fetch_queue)

class PlaylistWindow(FloatingBase):
    """Playlist browser window"""
    def __init__(self, api, parent):
        super().__init__("Your Playlists", parent)
        self.spotify = api
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background: transparent; border: none; color: #ddd; font-size: 12px;")
        self.list_widget.itemDoubleClicked.connect(self.play_playlist)
        self.layout().addWidget(self.list_widget)

    def refresh(self):
        def on_data(data):
            self.list_widget.clear()
            if data and data.get('items'):
                for playlist in data['items']:
                    item = QListWidgetItem(playlist['name'])
                    item.setData(Qt.UserRole, playlist['id'])
                    self.list_widget.addItem(item)
        
        def fetch_playlists():
            try:
                data = self.spotify.get_playlists()
                on_data(data)
            except Exception as e:
                logger.error(f"Playlists refresh failed: {str(e)}")
        
        QThreadPool.globalInstance().start(fetch_playlists)

    def play_playlist(self, item):
        playlist_id = item.data(Qt.UserRole)
        def play():
            try:
                self.spotify.play_playlist(playlist_id)
            except Exception as e:
                logger.error(f"Play playlist failed: {str(e)}")
        
        QThreadPool.globalInstance().start(play)
        self.hide()

# ---------------------------------------------------------------------
# MAIN APPLICATION WINDOW
# ---------------------------------------------------------------------
class MainWindow(QMainWindow, GlassVisualMixin):
    """Main transparent overlay window"""
    WIDTH = 320
    HEIGHT_MIN = 100
    HEIGHT_MAX = 280

    def __init__(self, spotify_client):
        super().__init__()
        self.spotify = spotify_client
        self.is_expanded = False
        self.drag_pos = None
        self.last_track_id = ""
        
        # Async communication
        self.signals = PipelineSignals()
        self.signals.playback_ready.connect(self.on_playback_data)
        self.signals.art_ready.connect(self.on_art_ready)
        self.signals.error_signal.connect(self.on_error)
        
        # Child windows
        self.queue_window = None
        self.playlist_window = None
        
        self.setup_ui()
        self.setup_timers()
        self.setup_shortcuts()
        
        # Initial sync
        self.refresh_playback()

    def setup_ui(self):
        """Initialize the user interface"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(self.WIDTH, self.HEIGHT_MIN)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        # Header section
        header_layout = QHBoxLayout()
        
        # Album art
        self.art_label = QLabel()
        self.art_label.setFixedSize(60, 60)
        self.art_label.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 8px;")
        header_layout.addWidget(self.art_label)
        
        # Text info
        text_layout = QVBoxLayout()
        self.title_label = QLabel("Syncing...")
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {Theme.TEXT_PRIMARY.name()};")
        self.artist_label = QLabel("Connecting to Spotify")
        self.artist_label.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_SECONDARY.name()};")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.artist_label)
        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        
        # Close button
        self.close_button = FluentButton("×", self)
        self.close_button.clicked.connect(self.close)
        header_layout.addWidget(self.close_button)
        
        layout.addLayout(header_layout)
        
        # Controls section (hidden by default)
        self.controls_widget = QWidget()
        self.controls_widget.hide()
        controls_layout = QVBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(0, 5, 0, 0)
        controls_layout.setSpacing(15)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        playback_layout.addStretch()
        self.prev_button = FluentButton("⏮", self)
        self.play_button = FluentButton("▶", self, is_accent=True)
        self.next_button = FluentButton("⏭", self)
        playback_layout.addWidget(self.prev_button)
        playback_layout.addWidget(self.play_button)
        playback_layout.addWidget(self.next_button)
        playback_layout.addStretch()
        controls_layout.addLayout(playback_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("🔊"))
        self.volume_slider = FluentSlider(self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addLayout(volume_layout)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        self.queue_button = FluentButton("📋", self)
        self.playlist_button = FluentButton("🎵", self)
        self.queue_button.clicked.connect(self.toggle_queue)
        self.playlist_button.clicked.connect(self.toggle_playlists)
        nav_layout.addWidget(self.queue_button)
        nav_layout.addWidget(self.playlist_button)
        nav_layout.addStretch()
        controls_layout.addLayout(nav_layout)
        
        layout.addWidget(self.controls_widget)
        
        # Connect buttons
        self.prev_button.clicked.connect(lambda: self.api_call(self.spotify.previous_track))
        self.play_button.clicked.connect(self.toggle_playback)
        self.next_button.clicked.connect(lambda: self.api_call(self.spotify.next_track))
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(Theme.SHADOW_BLUR)
        shadow.setColor(Theme.SHADOW_COLOR)
        shadow.setOffset(0, 8)
        central.setGraphicsEffect(shadow)

    def setup_timers(self):
        """Initialize timers for auto-refresh and hover detection"""
        # Playback refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_playback)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds
        
        # Hover detection timer
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.check_hover_state)
        self.hover_timer.start(100)  # Check every 100ms

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        shortcuts = {
            "Ctrl+Shift+Space": self.toggle_playback,
            "Ctrl+Shift+N": lambda: self.api_call(self.spotify.next_track),
            "Ctrl+Shift+B": lambda: self.api_call(self.spotify.previous_track),
            "Ctrl+Shift+Q": self.toggle_queue,
            "Ctrl+Shift+L": self.toggle_playlists
        }
        
        for key_sequence, callback in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.activated.connect(callback)

    def refresh_playback(self):
        """Refresh current playback state"""
        worker = ApiWorker(self.signals, self.spotify.get_current_playback)
        QThreadPool.globalInstance().start(worker)

    def on_playback_data(self, data):
        """Handle playback data received from API"""
        if not data or not data.get('item'):
            self.title_label.setText("No Active Playback")
            self.artist_label.setText("Play something in Spotify")
            self.play_button.setText("▶")
            return

        track = data['item']
        title = track.get('name', 'Unknown Title')
        artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
        
        # Truncate long text
        display_title = title[:28] + "..." if len(title) > 30 else title
        display_artists = artists[:28] + "..." if len(artists) > 30 else artists
        
        self.title_label.setText(display_title)
        self.artist_label.setText(display_artists)
        self.play_button.setText("⏸" if data.get('is_playing', False) else "▶")
        
        # Load album art if track changed
        if track.get('id') != self.last_track_id:
            self.last_track_id = track.get('id', '')
            images = track.get('album', {}).get('images', [])
            if images:
                art_loader = ArtLoader(self.signals, images[0]['url'], 60)
                QThreadPool.globalInstance().start(art_loader)

    def on_art_ready(self, pixmap):
        """Handle album art ready"""
        self.art_label.setPixmap(pixmap)

    def on_error(self, error_msg):
        """Handle API errors"""
        logger.error(f"API Error: {error_msg}")

    def api_call(self, func, *args):
        """Make API call with error handling"""
        worker = ApiWorker(None, func, *args)
        QThreadPool.globalInstance().start(worker)
        # Refresh playback after a short delay
        QTimer.singleShot(400, self.refresh_playback)

    def toggle_playback(self):
        """Toggle play/pause state"""
        def determine_action(data):
            if data and data.get('is_playing'):
                self.api_call(self.spotify.pause)
            else:
                self.api_call(self.spotify.play)
        
        # Get current state first, then toggle
        worker = ApiWorker(PipelineSignals(), self.spotify.get_current_playback)
        worker.signals.playback_ready.connect(determine_action)
        QThreadPool.globalInstance().start(worker)

    def on_volume_changed(self, volume):
        """Handle volume slider change"""
        self.api_call(self.spotify.set_volume, volume)

    def check_hover_state(self):
        """Check if mouse is hovering over the interface"""
        cursor_pos = QCursor.pos()
        over_main = self.geometry().contains(cursor_pos)
        
        # Check if over child windows
        over_child = False
        for window in [self.queue_window, self.playlist_window]:
            if window and window.isVisible() and window.geometry().contains(cursor_pos):
                over_child = True
                break
        
        # Expand if hovering over any part of the interface or dragging slider
        if over_main or over_child or self.volume_slider.is_dragging:
            self.expand_interface()
        else:
            self.collapse_interface()

    def expand_interface(self):
        """Show expanded controls"""
        if not self.is_expanded:
            self.is_expanded = True
            self.controls_widget.show()
            self.setFixedSize(self.WIDTH, self.HEIGHT_MAX)
            self.reposition_child_windows()

    def collapse_interface(self):
        """Hide expanded controls"""
        if self.is_expanded:
            self.is_expanded = False
            self.controls_widget.hide()
            self.setFixedSize(self.WIDTH, self.HEIGHT_MIN)

    def reposition_child_windows(self):
        """Reposition child windows relative to main window"""
        if self.queue_window and self.queue_window.isVisible():
            self.queue_window.move(self.x() + self.width() + 10, self.y())
        if self.playlist_window and self.playlist_window.isVisible():
            self.playlist_window.move(self.x() - self.playlist_window.width() - 10, self.y())

    def toggle_queue(self):
        """Toggle queue window visibility"""
        if not self.queue_window:
            self.queue_window = QueueWindow(self.spotify, self)
        
        if self.queue_window.isVisible():
            self.queue_window.hide()
        else:
            self.queue_window.refresh()
            self.reposition_child_windows()
            self.queue_window.show()

    def toggle_playlists(self):
        """Toggle playlists window visibility"""
        if not self.playlist_window:
            self.playlist_window = PlaylistWindow(self.spotify, self)
        
        if self.playlist_window.isVisible():
            self.playlist_window.hide()
        else:
            self.playlist_window.refresh()
            self.reposition_child_windows()
            self.playlist_window.show()

    def paintEvent(self, event):
        """Custom paint event for glass effect"""
        painter = QPainter(self)
        self.paint_glass_effect(self, painter, self.underMouse())

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
            self.reposition_child_windows()

    def closeEvent(self, event):
        """Clean up on close"""
        self.refresh_timer.stop()
        self.hover_timer.stop()
        if self.queue_window:
            self.queue_window.close()
        if self.playlist_window:
            self.playlist_window.close()
        QApplication.quit()
        event.accept()
