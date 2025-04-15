# website_builder/views/web_preview.py
import os
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, QTimer, QFileSystemWatcher, QFileInfo

logger = logging.getLogger(__name__)

class WebPreview(QWidget):
    """
    A widget using QWebEngineView to display a live preview of an HTML file.
    Includes basic live reload functionality for the project's root directory.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.webview = QWebEngineView()
        self.layout.addWidget(self.webview)

        # --- Configure WebEngine Settings ---
        settings = self.webview.settings()
        # Enable essential features for local development
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True) # Crucial for local CSS/JS/images
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True) # Allow fetching remote resources if needed
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False) # Generally disable plugins unless needed (Flash, etc.)
        # Enable DevTools via environment variable (set *before* QApplication init)
        # Example: os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "8080"
        # Then access http://localhost:8080 in a Chromium browser.
        # Note: This is global, affects all QWebEngineView instances.
        # settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True) # Optional
        # settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True) # Optional, use with caution

        self.current_file = None # Path to the currently loaded HTML file
        self.project_root = None # Root directory of the current project

        # --- File Watcher for Live Reload (Watches project root only) ---
        self.project_watcher = QFileSystemWatcher(self)
        self.project_watcher.directoryChanged.connect(self._schedule_reload)
        self.project_watcher.fileChanged.connect(self._schedule_reload) # Watch for direct file changes too
        self.watched_path = None # Store the single path being watched

        # Debounce timer for reloads to avoid excessive reloads on multiple quick changes
        self.reload_timer = QTimer(self)
        self.reload_timer.setInterval(500) # 500ms delay before reloading
        self.reload_timer.setSingleShot(True)
        self.reload_timer.timeout.connect(self.perform_reload)

        # Set initial placeholder content
        self.webview.setHtml("<p>Open an HTML file or project folder to start the preview.</p>",
                              QUrl("about:blank")) # Provide a base URL


    def set_project_root(self, root_path: str):
        """Sets the project root directory and starts watching it."""
        root_path = os.path.normpath(root_path)
        logger.info(f"Setting project root to: {root_path}")
        if not os.path.isdir(root_path):
             logger.warning(f"Invalid project root directory: {root_path}")
             # Optionally clear preview or show error?
             return

        # Stop watching old path if different
        if self.watched_path and self.watched_path != root_path:
             self.project_watcher.removePath(self.watched_path)
             logger.debug(f"Stopped watching old path: {self.watched_path}")
             self.watched_path = None

        self.project_root = root_path

        # Start watching the new root directory if not already watched
        if self.watched_path != root_path:
             if self.project_watcher.addPath(root_path):
                 self.watched_path = root_path
                 logger.debug(f"Started watching new path: {self.watched_path}")
             else:
                 logger.error(f"Failed to add path to watcher: {root_path}")

        # Attempt to automatically load index.html if it exists
        index_html_path = os.path.join(root_path, "index.html")
        if os.path.exists(index_html_path):
             self.load_file(index_html_path)
        elif self.current_file and not self.current_file.startswith(root_path):
            # If a file was loaded previously from outside the new root, clear preview
             self.clear_preview("Project folder changed.")
        elif not self.current_file:
            # If no file is loaded, show a message indicating the project context
            self.webview.setHtml(f"<p>Project folder set to '{os.path.basename(root_path)}'.<br>"
                                  f"Load an HTML file or create/select index.html.</p>",
                                  QUrl.fromLocalFile(QFileInfo(self.project_root).absoluteFilePath()))


    def load_file(self, file_path: str):
        """Loads and displays the specified HTML file."""
        file_path = os.path.normpath(file_path)
        if not file_path:
            self.clear_preview("No file specified.")
            return

        if not os.path.exists(file_path):
            logger.error(f"Attempted to load non-existent file: {file_path}")
            self.clear_preview(f"File not found: {os.path.basename(file_path)}")
            return

        # Ensure it's an HTML file (basic check)
        if not file_path.lower().endswith((".html", ".htm")):
             logger.warning(f"Attempted to load non-HTML file in preview: {file_path}")
             # Don't clear preview, just log it, or show a non-HTML message?
             # self.webview.setHtml(f"<p>Cannot preview non-HTML file: {os.path.basename(file_path)}</p>")
             return

        self.current_file = file_path
        # Ensure the project root is set correctly, infer if necessary
        if not self.project_root or not file_path.startswith(self.project_root):
             containing_dir = os.path.dirname(file_path)
             logger.warning(f"Loaded file '{os.path.basename(file_path)}' is outside current project root '{self.project_root}'. Setting root to '{containing_dir}'.")
             self.set_project_root(containing_dir) # Treat containing dir as root if no project set or file is outside

        # Use file:/// URL for local files, crucial for relative paths (CSS, JS, images)
        url = QUrl.fromLocalFile(file_path)
        logger.info(f"Loading URL in preview: {url.toString()}")
        self.webview.load(url)


    def clear_preview(self, message="No file loaded."):
         """Clears the preview and resets the current file."""
         logger.info(f"Clearing preview: {message}")
         self.current_file = None
         # Stop webview loading if any
         self.webview.stop()
         # Provide a base URL even for the cleared message
         base_url = QUrl("about:blank")
         if self.project_root:
             base_url = QUrl.fromLocalFile(QFileInfo(self.project_root).absoluteFilePath())
         self.webview.setHtml(f"<p>{message}</p>", base_url)


    def _schedule_reload(self, path: str):
        """Schedules a reload using a debounced timer."""
        # This gets triggered for file or directory changes within the watched root
        logger.debug(f"Watcher detected change in '{path}'. Scheduling reload.")
        # Check if the change is relevant (e.g., ignore changes to non-web files?)
        # Simple approach: reload if *any* change happens in the watched root.
        # More complex: check file extension, check if it's linked from current HTML etc.
        if self.current_file:
             # Debounce the reload requests - restart timer on each trigger
             self.reload_timer.start()


    def perform_reload(self):
        """Reloads the currently loaded file in the webview."""
        if self.current_file:
            logger.info(f"Performing reload for: {self.current_file}")
            self.webview.reload() # Reload the current page in the webview
        else:
             logger.debug("Reload triggered but no current file loaded.")


    def update_preview_content(self, html_content: str):
        """
        Displays HTML content directly (e.g., from unsaved editor buffer).
        This bypasses file loading and watching. Relative paths need base URL.
        """
        logger.debug("Updating preview with direct HTML content.")
        self.current_file = None # Indicate it's not displaying a specific saved file
        # Stop the reload timer if it was running
        self.reload_timer.stop()

        # Provide a base URL based on the project root for relative paths
        base_url = QUrl("about:blank")
        if self.project_root:
             # Use the directory containing the (conceptual) file as base
             base_url = QUrl.fromLocalFile(QFileInfo(self.project_root).absoluteFilePath())
             logger.debug(f"Setting base URL for direct content: {base_url.toString()}")

        self.webview.setHtml(html_content, base_url)