# website_builder/utils/theme_manager.py
import os
import logging
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtWidgets import QApplication, QStyleFactory

logger = logging.getLogger(__name__)

class ThemeManager:
    """Manages application themes (light/dark) using QSS and QPalette."""
    THEME_SETTING_KEY = "Appearance/Theme"
    DEFAULT_THEME = "light"
    ICON_BASE_DIR = "resources/icons" # Relative path to icons directory

    def __init__(self, app: QApplication, settings: QSettings):
        self.app = app
        self.settings = settings
        self.base_icon_path = self._find_resource_dir(self.ICON_BASE_DIR)
        self.themes_qss = self._load_themes_qss() # Load QSS from files

    def _find_resource_dir(self, relative_path: str) -> str:
        """Finds the absolute path to a resource directory."""
        # Assumes this script is in utils/, resources are ../resources/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resource_dir = os.path.join(base_dir, relative_path)
        if not os.path.isdir(resource_dir):
             logger.warning(f"Resource directory not found at expected location: {resource_dir}")
             # Fallback or error handling? For now, return the path anyway.
        return resource_dir

    def _load_themes_qss(self) -> dict:
        """Loads QSS theme files."""
        themes = {"light": "", "dark": ""}
        styles_dir = self._find_resource_dir("resources/styles")

        for theme_name in themes:
            qss_file_path = os.path.join(styles_dir, f"{theme_name}.qss")
            if os.path.exists(qss_file_path):
                try:
                    with open(qss_file_path, "r", encoding="utf-8") as f_qss:
                        themes[theme_name] = f_qss.read()
                    logger.info(f"Loaded QSS theme file: {qss_file_path}")
                except Exception as e:
                    logger.error(f"Error reading QSS file {qss_file_path}: {e}")
            else:
                logger.warning(f"QSS theme file not found: {qss_file_path}. Theme '{theme_name}' might rely solely on palette.")
                # Keep empty string - indicates no QSS for this theme

        return themes

    def apply_theme(self, theme_name: str):
        """Applies the specified theme (QSS and Palette)."""
        if theme_name not in self.themes_qss:
            logger.warning(f"Theme '{theme_name}' not found. Using default '{self.DEFAULT_THEME}'.")
            theme_name = self.DEFAULT_THEME

        qss = self.themes_qss.get(theme_name, "")

        # Always set Fusion style for consistency, especially with QSS
        self.app.setStyle(QStyleFactory.create("Fusion"))

        if theme_name == "dark":
             self.app.setPalette(self._create_dark_palette())
        else: # Light theme (or default)
             # Reset to default palette for light theme before applying QSS
             self.app.setPalette(QApplication.style().standardPalette())

        # Apply the QSS stylesheet
        self.app.setStyleSheet(qss)
        logger.info(f"Applied theme: {theme_name}")

        # Save the selected theme preference
        self.settings.setValue(self.THEME_SETTING_KEY, theme_name)
        logger.debug(f"Saved theme preference: {theme_name}")


    def _create_dark_palette(self) -> QPalette:
            """Creates a standard dark QPalette."""
            dark_palette = QPalette()
            # Define base colors
            WINDOW_BG = QColor(53, 53, 53)
            WINDOW_TEXT = QColor(220, 220, 220) # Slightly off-white
            BASE = QColor(42, 42, 42)
            ALTERNATE_BASE = QColor(66, 66, 66)
            TOOLTIP_BASE = QColor(53, 53, 53)
            TOOLTIP_TEXT = QColor(220, 220, 220)
            TEXT = QColor(220, 220, 220)
            BUTTON = QColor(66, 66, 66) # Button background slightly lighter
            BUTTON_TEXT = QColor(220, 220, 220)
            BRIGHT_TEXT = QColor(255, 80, 80) # Brighter red for emphasis
            LINK = QColor(42, 130, 218)
            HIGHLIGHT = QColor(42, 130, 218) # Highlight color (e.g., selection)
            HIGHLIGHTED_TEXT = QColor(240, 240, 240) # Text on highlight

            # Set colors for active state
            dark_palette.setColor(QPalette.ColorRole.Window, WINDOW_BG)
            dark_palette.setColor(QPalette.ColorRole.WindowText, WINDOW_TEXT)
            dark_palette.setColor(QPalette.ColorRole.Base, BASE)
            dark_palette.setColor(QPalette.ColorRole.AlternateBase, ALTERNATE_BASE)
            dark_palette.setColor(QPalette.ColorRole.ToolTipBase, TOOLTIP_BASE)
            dark_palette.setColor(QPalette.ColorRole.ToolTipText, TOOLTIP_TEXT)
            dark_palette.setColor(QPalette.ColorRole.Text, TEXT)
            dark_palette.setColor(QPalette.ColorRole.Button, BUTTON)
            dark_palette.setColor(QPalette.ColorRole.ButtonText, BUTTON_TEXT)
            dark_palette.setColor(QPalette.ColorRole.BrightText, BRIGHT_TEXT)
            dark_palette.setColor(QPalette.ColorRole.Link, LINK)
            dark_palette.setColor(QPalette.ColorRole.Highlight, HIGHLIGHT)
            dark_palette.setColor(QPalette.ColorRole.HighlightedText, HIGHLIGHTED_TEXT)

            # Set colors for disabled state
            DISABLED_TEXT = QColor(127, 127, 127)
            DISABLED_BUTTON_TEXT = QColor(127, 127, 127)
            DISABLED_WINDOW_TEXT = QColor(127, 127, 127)

            dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, DISABLED_TEXT)
            dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, DISABLED_BUTTON_TEXT)
            dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, DISABLED_WINDOW_TEXT)
            dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, BUTTON) # Use button color for disabled highlight
            dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, DISABLED_TEXT)

            return dark_palette


    def toggle_theme(self):
        """Switches between light and dark themes."""
        current_theme = self.get_current_theme()
        new_theme = "dark" if current_theme == "light" else "light"
        logger.info(f"Toggling theme from {current_theme} to {new_theme}")
        self.apply_theme(new_theme)


    def get_current_theme(self) -> str:
        """Gets the currently configured theme name."""
        return self.settings.value(self.THEME_SETTING_KEY, self.DEFAULT_THEME)


    def get_icon(self, icon_name: str) -> str:
        """
        Gets the absolute path to an icon file, preferring the themed version
        but falling back to the 'light' version or a default name if not found.
        Returns an empty string if no suitable icon is found.
        """
        current_theme = self.get_current_theme()
        # Try theme-specific path first
        themed_icon_path = os.path.join(self.base_icon_path, current_theme, f"{icon_name}.png") # Assuming PNG

        if os.path.exists(themed_icon_path):
            return themed_icon_path

        # Fallback 1: Try light theme version
        light_icon_path = os.path.join(self.base_icon_path, "light", f"{icon_name}.png")
        if os.path.exists(light_icon_path):
             logger.debug(f"Icon '{icon_name}' not found for theme '{current_theme}', using 'light' fallback.")
             return light_icon_path

        # Fallback 2: Try a generic name (e.g., 'default_icon.png') - requires adding such an icon
        # generic_icon_path = os.path.join(self.base_icon_path, "default_icon.png")
        # if os.path.exists(generic_icon_path):
        #    logger.warning(f"Icon '{icon_name}' not found for theme '{current_theme}' or 'light'. Using generic default.")
        #    return generic_icon_path

        # Final fallback: Icon not found
        logger.warning(f"Icon '{icon_name}' not found for theme '{current_theme}' or in fallbacks.")
        return "" # Return empty string; QIcon("") is valid and shows nothing.