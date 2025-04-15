# website_builder/main.py
import hashlib
import os
import sys

# --- Import QFont and QFontDatabase ---
from PyQt6.QtGui import QFont, QFontDatabase
# --- Keep other imports ---
from PyQt6.QtCore import QCoreApplication, QSettings
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from utils.theme_manager import ThemeManager

# Set application metadata
QCoreApplication.setOrganizationName("MyCompany") # Or your name/org
QCoreApplication.setApplicationName("Flexta") # <-- RENAME HERE

# --- Helper function to load font and get family name ---
def load_font(font_filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(base_dir, "resources", "fonts", font_filename)
    loaded_family = None
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                loaded_family = font_families[0]
                print(f"Successfully loaded font: '{loaded_family}' from {font_filename}")
            else:
                print(f"Warning: Font loaded from {font_filename} but no family names found.")
        else:
            print(f"Error: Failed to load font from {font_filename}. Check file.")
    else:
        print(f"Warning: Font file not found at {font_path}")
    return loaded_family
# --- End Helper Function ---

def main():
    # ... (optional remote debugging env var) ...

    app = QApplication(sys.argv)

    # --- Load Custom Fonts ---
    # Load the main UI font (Bold)
    default_font_family = load_font("SF-Pro-Display-Bold.otf")
    # Load the font specifically for the menubar
    menubar_font_family = load_font("SF-Pro-Text-Semibold.otf")
    # --- End Font Loading ---


    # --- Set Default Application Font (using the Bold Display font) ---
    default_font = QFont()
    default_point_size = 10

    if default_font_family:
        # Prioritize the loaded custom Display font
        default_font.setFamily(default_font_family)
        default_font.setPointSize(default_point_size)
        default_font.setWeight(QFont.Weight.Bold) # Use Bold weight
        print(f"Setting default font: {default_font_family} Bold")
    else:
        # Fallback to platform-specific fonts if custom font failed
        print("Default custom font not loaded, using platform fallback.")
        # ... (keep existing fallback logic for San Francisco/Segoe UI/Cantarell) ...
        if sys.platform == "darwin":
            default_font.setFamily("San Francisco")
            default_font.setPointSize(default_point_size)
            print("Attempting to set font: San Francisco (fallback)")
        elif sys.platform == "win32":
            default_font.setFamily("Segoe UI")
            default_font.setPointSize(default_point_size)
            print("Setting font: Segoe UI (fallback)")
        else:
            default_font.setFamily("Cantarell")
            default_font.setPointSize(default_point_size + 1)
            print(f"Setting font: {default_font.family()} (fallback)")


    # Apply the chosen default font to the application
    app.setFont(default_font)
    # --- End Font Setting ---

    # --- Initialize ThemeManager, Settings, MainWindow etc. ---
    # ... (rest of main function remains the same) ...
    settings = QSettings()
    theme_manager = ThemeManager(app, settings)
    try:
        theme_manager.apply_theme(theme_manager.get_current_theme())
    except Exception as e:
        print(f"Error applying initial theme: {e}")

    window = MainWindow(theme_manager)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    # --- Keep existing plugin path logic ---
    # ... (plugin path logic remains the same) ...
    plugin_paths = [
        os.path.join(
            os.path.dirname(sys.executable),
            "Lib",
            "site-packages",
            "PyQt6",
            "Qt6",
            "plugins",
        ),
        os.path.join(
            os.path.dirname(sys.executable), "Library", "plugins"
        ),
    ]
    os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(filter(os.path.isdir, plugin_paths))

    main()