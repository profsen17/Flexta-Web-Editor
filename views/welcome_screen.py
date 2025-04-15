# website_builder/views/welcome_screen.py

import sys
import logging
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QHBoxLayout,
    QSpacerItem,
)

logger = logging.getLogger(__name__)

class WelcomeScreen(QWidget):
    """Initial screen shown on startup, offering project creation/opening and theme toggle."""
    create_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal()

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setObjectName("WelcomeScreen")
        self._init_ui()
        logger.debug("WelcomeScreen initialized.")

    def _init_ui(self):
        # --- Main Layout (Vertical) ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 30, 50, 60)

        # --- Top Right Layout (for Theme Button) ---
        top_right_layout = QHBoxLayout()
        top_right_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.theme_toggle_button = QPushButton("Toggle Light/Dark Theme")
        self.theme_toggle_button.setObjectName("ThemeToggleButton")
        self.theme_toggle_button.setToolTip("Switch between light and dark mode")
        self.theme_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.theme_toggle_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.theme_toggle_button.clicked.connect(self._toggle_theme)
        top_right_layout.addWidget(self.theme_toggle_button)
        main_layout.addLayout(top_right_layout)

        # --- Spacer ---
        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Title ---
        title_label = QLabel("Flexta")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("WelcomeTitle")
        main_layout.addWidget(title_label)
        main_layout.addSpacing(50)

        # --- Create New Project Button ---
        self.create_button = QPushButton(" Create New Project")
        self.create_button.setIconSize(QSize(24, 24))
        self.create_button.setMinimumHeight(50)
        self.create_button.setObjectName("CreateButton")
        self.create_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.create_button.setMaximumWidth(350)
        self.create_button.clicked.connect(self.create_project_requested)
        main_layout.addWidget(self.create_button, 0, Qt.AlignmentFlag.AlignCenter)

        # --- Reduce Spacing Between Buttons ---
        main_layout.addSpacing(10) # <-- REDUCED SPACING HERE (from 15)

        # --- Open Project Button ---
        self.open_button = QPushButton(" Open Existing Project")
        self.open_button.setIconSize(QSize(24, 24))
        self.open_button.setMinimumHeight(50)
        self.open_button.setObjectName("OpenButton")
        self.open_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.open_button.setMaximumWidth(350)
        self.open_button.clicked.connect(self.open_project_requested)
        main_layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignCenter)

        # --- Spacer at Bottom ---
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        # --- Adjust stretch factors as needed ---
        main_layout.setStretchFactor(top_right_layout, 0)
        main_layout.setStretchFactor(title_label, 0)
        main_layout.setStretchFactor(self.create_button, 0)
        main_layout.setStretchFactor(self.open_button, 0)
        main_layout.setStretch(1, 1) # Spacer before title
        main_layout.setStretch(7, 1) # Spacer after buttons (index adjusted)

        self.update_icons()
        self.update_styles()

    def _toggle_theme(self):
        """Toggles the theme and updates the welcome screen UI."""
        self.theme_manager.toggle_theme()
        self.update_styles()
        self.update_icons()

    def update_styles(self):
        """Applies styles based on the current theme."""
        theme = self.theme_manager.get_current_theme()
        logger.debug(f"Updating WelcomeScreen styles for theme: {theme}")

        base_style = """
            WelcomeScreen {
                background-color: #ECECEC;
            }

            WelcomeScreen QLabel#WelcomeTitle {
                font-size: 30pt;
                font-weight: bold;
                color: #333333;
                padding-bottom: 10px;
                background: transparent;
            }

            /* Style for BOTH main action buttons - Light */
            WelcomeScreen QPushButton#CreateButton,
            WelcomeScreen QPushButton#OpenButton { /* Combined selector */
                font-size: 11pt;
                font-weight: 600; /* Semibold */
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                text-align: left;
                padding-left: 20px; /* Space for icon */
                /* Common color style */
                background-color: #E5E5E5; /* Light gray */
                color: #333333; /* Dark text */
            }
            /* Hover state for BOTH main action buttons - Light */
            WelcomeScreen QPushButton#CreateButton:hover,
            WelcomeScreen QPushButton#OpenButton:hover { /* Combined selector */
                background-color: #DCDCDC;
            }
            /* Pressed state for BOTH main action buttons - Light */
            WelcomeScreen QPushButton#CreateButton:pressed,
            WelcomeScreen QPushButton#OpenButton:pressed { /* Combined selector */
                background-color: #C8C8C8;
            }

            /* Theme Toggle Button Style (QPushButton) */
            WelcomeScreen QPushButton#ThemeToggleButton {
                font-size: 10pt;   /* Keep size from before */
                font-weight: 500;
                color: #555555;
                background-color: rgba(0, 0, 0, 0.05);
                border: 1px solid rgba(0, 0, 0, 0.1);
                padding: 8px 15px; /* Keep size from before */
                border-radius: 8px;
            }
            WelcomeScreen QPushButton#ThemeToggleButton:hover {
                background-color: rgba(0, 0, 0, 0.08);
                border-color: rgba(0, 0, 0, 0.15);
            }
            WelcomeScreen QPushButton#ThemeToggleButton:pressed {
                background-color: rgba(0, 0, 0, 0.12);
            }
        """

        dark_style_overrides = """
            WelcomeScreen {
                background-color: #2D2D2D;
            }
            WelcomeScreen QLabel#WelcomeTitle {
                color: #FFFFFF; /* White title */
            }

            /* Style for BOTH main action buttons - Dark */
            WelcomeScreen QPushButton#CreateButton,
            WelcomeScreen QPushButton#OpenButton { /* Combined selector */
                 background-color: #555555; /* Darker gray */
                 color: #E0E0E0; /* Light text */
            }
            /* Hover state for BOTH main action buttons - Dark */
            WelcomeScreen QPushButton#CreateButton:hover,
            WelcomeScreen QPushButton#OpenButton:hover { /* Combined selector */
                 background-color: #606060;
            }
            /* Pressed state for BOTH main action buttons - Dark */
            WelcomeScreen QPushButton#CreateButton:pressed,
            WelcomeScreen QPushButton#OpenButton:pressed { /* Combined selector */
                 background-color: #4A4A4A;
            }


            /* Theme Toggle Button Style (QPushButton) - Dark */
            WelcomeScreen QPushButton#ThemeToggleButton {
                color: #AAAAAA;
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                /* Inherit padding/font/radius */
                font-size: 10pt;
                padding: 8px 15px;
                border-radius: 8px;
            }
            WelcomeScreen QPushButton#ThemeToggleButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border-color: rgba(255, 255, 255, 0.2);
            }
            WelcomeScreen QPushButton#ThemeToggleButton:pressed {
                background-color: rgba(255, 255, 255, 0.16);
            }
        """

        if theme == "dark":
            self.setStyleSheet(base_style + dark_style_overrides)
        else: # Light theme
            self.setStyleSheet(base_style)


    def update_icons(self):
        """Updates icons for Create/Open buttons."""
        logger.debug("Updating WelcomeScreen icons.")
        create_icon_name = "new_project"
        open_icon_name = "open_project"

        icon_size = QSize(24, 24)
        self.create_button.setIconSize(icon_size)
        self.open_button.setIconSize(icon_size)

        self.create_button.setIcon(QIcon(self.theme_manager.get_icon(create_icon_name)))
        self.open_button.setIcon(QIcon(self.theme_manager.get_icon(open_icon_name)))