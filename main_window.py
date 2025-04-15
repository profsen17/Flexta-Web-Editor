# website_builder/main_window.py
import logging
import os
from PyQt6.QtCore import QTimer
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from controllers.main_controller import MainController
from views.code_editor import CodeEditorTabWidget
from views.components_panel import ComponentsPanel
from views.file_explorer import FileExplorer
from views.properties_panel import PropertiesPanel
from views.visual_designer import VisualDesigner
from views.web_preview import WebPreview
from views.welcome_screen import WelcomeScreen

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    open_file_requested = pyqtSignal(str)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("Flexta")
        self.resize(1400, 900)

        # --- Store references ---
        self.main_ui_widgets = []
        self.toolbars = []
        self.docks = []

        # --- Create UI Elements ---
        self._create_actions()
        self._create_menus()
        self.menuBar().hide()
        self._create_toolbars()
        self._create_status_bar()
        self._create_main_splitter_and_children()
        self._create_dock_widgets()

        # --- Create Welcome Screen ---
        self.welcome_screen = WelcomeScreen(self.theme_manager, self)
        self.setCentralWidget(self.welcome_screen)

        # --- Hide Main UI ---
        self._hide_main_ui_elements()

        # --- Initialize Controller AFTER UI elements exist ---
        # This order should now be correct again
        self.controller = MainController(
            self, self.theme_manager, self.welcome_screen
        )
        # Controller's __init__ calls _connect_signals, which now connects to
        # the FileExplorer's new signal.

        # --- Update Icons ---
        self.update_icons()

    def _create_actions(self):
        """Creates all QAction objects for menus and toolbars."""

        # Action list for easy enabling/disabling
        self.project_dependent_actions = []  # Actions disabled until project open

        # --- Mode-Specific File Actions ---
        # Guided Mode Action
        self.action_new_page = QAction(
            QIcon(self.theme_manager.get_icon("new_page")), "&New Page", self
        )
        self.action_new_page.setStatusTip("Create a new guided page folder and files")
        self.project_dependent_actions.append(self.action_new_page)

        # Free Mode Actions
        self.action_new_file = QAction(
            QIcon(self.theme_manager.get_icon("new_file")), "New &File...", self  # Added new_file icon
        )
        self.action_new_file.setStatusTip("Create a new empty file")
        self.project_dependent_actions.append(self.action_new_file)

        self.action_new_folder = QAction(
            QIcon(self.theme_manager.get_icon("new_folder")), "New Fol&der...", self  # Added new_folder icon
        )
        self.action_new_folder.setStatusTip("Create a new folder")
        self.project_dependent_actions.append(self.action_new_folder)
        # ---------------------------------

        # --- Common File Actions ---
        self.action_save = QAction(
            QIcon(self.theme_manager.get_icon("save")), "&Save", self
        )
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.setStatusTip("Save the current file")
        self.project_dependent_actions.append(self.action_save)

        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.setStatusTip("Save the current file with a new name")
        self.project_dependent_actions.append(self.action_save_as)
        # TODO: Implement Save As functionality in the controller.
        self.action_save_as.setEnabled(False) # Disable until implemented

        self.action_save_all = QAction(
            QIcon(self.theme_manager.get_icon("save_all")), "Save A&ll", self
        )
        self.action_save_all.setShortcut("Ctrl+Shift+S")
        self.action_save_all.setStatusTip("Save all open modified files")
        self.project_dependent_actions.append(self.action_save_all)

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_exit.setStatusTip("Exit the application")

        # --- Edit Actions ---
        self.action_undo = QAction(
            QIcon(self.theme_manager.get_icon("undo")), "&Undo", self
        )
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.setStatusTip("Undo the last action")
        self.project_dependent_actions.append(self.action_undo)

        self.action_redo = QAction(
            QIcon(self.theme_manager.get_icon("redo")), "&Redo", self
        )
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.setStatusTip("Redo the last undone action")
        self.project_dependent_actions.append(self.action_redo)

        self.action_cut = QAction(
            QIcon(self.theme_manager.get_icon("cut")), "Cu&t", self
        )
        self.action_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self.action_cut.setStatusTip("Cut the selected text")
        self.project_dependent_actions.append(self.action_cut)

        self.action_copy = QAction(
            QIcon(self.theme_manager.get_icon("copy")), "&Copy", self
        )
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.action_copy.setStatusTip("Copy the selected text")
        self.project_dependent_actions.append(self.action_copy)

        self.action_paste = QAction(
            QIcon(self.theme_manager.get_icon("paste")), "&Paste", self
        )
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.action_paste.setStatusTip("Paste text from the clipboard")
        self.project_dependent_actions.append(self.action_paste)
        # TODO: Connect Edit actions (Undo/Redo/Cut/Copy/Paste) to the focused editor.

        # --- View Actions ---
        self.action_toggle_theme = QAction(
            QIcon(self.theme_manager.get_icon("toggle_theme")),
            "&Toggle Light/Dark Theme",
            self,
        )
        self.action_toggle_theme.setStatusTip("Switch between light and dark modes")

        # Actions for toggling docks
        self.action_toggle_file_explorer = QAction(
            "File Explorer", self, checkable=True
        )
        self.action_toggle_components = QAction("Components", self, checkable=True)
        self.action_toggle_properties = QAction("Properties", self, checkable=True)

        # --- Project Actions ---
        self.action_export_project = QAction(
            QIcon(self.theme_manager.get_icon("export")), "&Export Project...", self
        )
        self.action_export_project.setStatusTip(
            "Export the entire project folder for deployment"
        )
        self.project_dependent_actions.append(self.action_export_project)

        self.action_run_in_browser = QAction(
            QIcon(self.theme_manager.get_icon("run")), "&Run in Browser", self
        )
        self.action_run_in_browser.setShortcut("F5")
        self.action_run_in_browser.setStatusTip(
            "Open the current HTML file in the default web browser"
        )
        self.project_dependent_actions.append(self.action_run_in_browser)

        # --- Disable project-dependent actions initially ---
        for action in self.project_dependent_actions:
            action.setEnabled(False)  # Keep this disabling logic
            action.setVisible(False)  # Also hide them initially

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        # Add all potentially relevant actions
        file_menu.addAction(self.action_new_page)   # For Guided
        file_menu.addAction(self.action_new_file)   # For Free
        file_menu.addAction(self.action_new_folder) # For Free
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addAction(self.action_save_all)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_cut)
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.action_toggle_theme)
        view_menu.addSeparator()
        view_menu.addMenu("Toggle Panels") # Group panel toggles
        view_menu.addAction(self.action_toggle_file_explorer)
        view_menu.addAction(self.action_toggle_components)
        view_menu.addAction(self.action_toggle_properties)

        project_menu = menu_bar.addMenu("&Project")
        project_menu.addAction(self.action_run_in_browser)
        project_menu.addAction(self.action_export_project)

    def _create_toolbars(self):
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolbar")
        file_toolbar.setIconSize(QSize(20, 20))
        file_toolbar.addAction(self.action_new_page)   # For Guided
        file_toolbar.addAction(self.action_new_file)   # For Free
        file_toolbar.addAction(self.action_new_folder) # For Free
        file_toolbar.addAction(self.action_save)
        file_toolbar.addAction(self.action_save_all)
        self.toolbars.append(file_toolbar)

        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolbar")
        edit_toolbar.setIconSize(QSize(20, 20))
        edit_toolbar.addAction(self.action_undo)
        edit_toolbar.addAction(self.action_redo)
        # Add Cut/Copy/Paste to toolbar? Optional.
        # edit_toolbar.addAction(self.action_cut)
        # edit_toolbar.addAction(self.action_copy)
        # edit_toolbar.addAction(self.action_paste)
        self.toolbars.append(edit_toolbar)

        project_toolbar = self.addToolBar("Project")
        project_toolbar.setObjectName("ProjectToolbar")
        project_toolbar.setIconSize(QSize(20, 20))
        project_toolbar.addAction(self.action_run_in_browser)
        project_toolbar.addAction(self.action_export_project)
        self.toolbars.append(project_toolbar)

        view_toolbar = self.addToolBar("View")
        view_toolbar.setObjectName("ViewToolbar")
        view_toolbar.setIconSize(QSize(20, 20))
        view_toolbar.addAction(self.action_toggle_theme)
        self.toolbars.append(view_toolbar)

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready", 3000)

    def _create_main_splitter_and_children(self):
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_ui_widgets.append(self.main_splitter)

        # Left Side: Editor / Visual Designer Tabs
        self.edit_design_tabs = QTabWidget()
        self.edit_design_tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.code_editor_widget = CodeEditorTabWidget(self)
        self.visual_designer = VisualDesigner(self) # Placeholder

        self.edit_design_tabs.addTab(
            self.code_editor_widget, QIcon(self.theme_manager.get_icon("code")), "Code"
        )
        self.edit_design_tabs.addTab(
            self.visual_designer, QIcon(self.theme_manager.get_icon("design")), "Design"
        )
        # TODO: Disable 'Design' tab initially? Or implement basic functionality.

        # Right Side: Web Preview
        self.web_preview = WebPreview(self)

        self.main_splitter.addWidget(self.edit_design_tabs)
        self.main_splitter.addWidget(self.web_preview)
        self.main_splitter.setSizes([750, 450]) # Adjusted initial sizes
        self.main_splitter.setStretchFactor(0, 2) # Code/Design takes more space
        self.main_splitter.setStretchFactor(1, 1) # Preview takes less

    def _create_dock_widgets(self):
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks # Keep this if you want to allow manual tabbing by dragging
        )

        # File Explorer Dock
        # File Explorer Dock
        self.file_explorer_dock = QDockWidget("File Explorer", self)
        self.file_explorer_dock.setObjectName("FileExplorerDock")
        # --- REVERT: Instantiate FileExplorer WITHOUT controller ---
        self.file_explorer = FileExplorer(self.theme_manager, self)
        # --------------------------------------------------------
        self.file_explorer_dock.setWidget(self.file_explorer)
        # ... (add dock widget, connect toggles) ...
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.file_explorer_dock)
        self.docks.append(self.file_explorer_dock)
        self.action_toggle_file_explorer.setChecked(True)
        self.action_toggle_file_explorer.toggled.connect(self.file_explorer_dock.setVisible)
        self.file_explorer_dock.visibilityChanged.connect(self.action_toggle_file_explorer.setChecked)


        # Components Dock
        self.components_dock = QDockWidget("Components", self)
        self.components_dock.setObjectName("ComponentsDock")
        self.components_panel = ComponentsPanel(self) # Placeholder
        self.components_dock.setWidget(self.components_panel)
        # Add Components Dock also to the left area (it will stack initially)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.components_dock)
        self.docks.append(self.components_dock)
        self.action_toggle_components.setChecked(True)
        self.action_toggle_components.toggled.connect(self.components_dock.setVisible)
        self.components_dock.visibilityChanged.connect(self.action_toggle_components.setChecked)

        # --- Change: Remove Tabify and Explicitly Split Vertically ---
        # Remove these lines:
        # self.tabifyDockWidget(self.file_explorer_dock, self.components_dock)
        # self.file_explorer_dock.raise_()

        # Add this line to stack Components below File Explorer:
        self.splitDockWidget(self.file_explorer_dock, self.components_dock, Qt.Orientation.Vertical)
        # --- End Change ---


        # Properties Dock (remains on the right)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_panel = PropertiesPanel(self) # Placeholder
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.docks.append(self.properties_dock)
        self.action_toggle_properties.setChecked(True)
        self.action_toggle_properties.toggled.connect(self.properties_dock.setVisible)
        self.properties_dock.visibilityChanged.connect(self.action_toggle_properties.setChecked)

    def handle_edit_design_tab_changed(self, index):
        """Checks validity before allowing switch to Design tab (index 1)."""
        design_tab_index = 1  # Assuming "Design" is the second tab (index 1)

        # Only perform check if switching TO the Design tab
        if index == design_tab_index:
            logger.debug(f"Attempting to switch to Design tab (index {index})")
            # Check validity via controller
            is_valid, detail_or_missing = self.controller.validate_design_view_access()

            if not is_valid:
                logger.warning(f"Design View access denied: {detail_or_missing}")
                # Validation failed, prevent the switch by scheduling a switch back to Code tab (index 0)
                # Using QTimer.singleShot ensures this happens after the current signal processing is done.
                code_tab_index = 0
                QTimer.singleShot(0, lambda: self.edit_design_tabs.setCurrentIndex(code_tab_index))
                # Optional: Bring the code editor tab visually to the front immediately
                # current_widget = self.edit_design_tabs.widget(code_tab_index)
                # if current_widget: current_widget.raise_()

            else:
                # Access granted, load content into visual designer (conceptual)
                current_path, current_content = self.code_editor_widget.get_current_editor_content()
                if current_path and current_content:
                    logger.info(f"Accessing Design View for: {current_path}")
                    # --- TODO: Replace with actual VisualDesigner loading ---
                    # self.visual_designer.load_html(current_content, current_path)
                    # For now, maybe update the placeholder label:
                    if hasattr(self.visual_designer, 'placeholder_label'):
                        self.visual_designer.placeholder_label.setText(
                            f"Design View for:\n{os.path.basename(current_path)}\n(Implementation Pending)")
                        self.visual_designer.placeholder_label.show()  # Ensure visible
                    # ---------------------------------------------------------
                else:
                    logger.warning("Could not get current content for Visual Designer after validation.")
                    # Optionally show an error or disable design view again?
                    QTimer.singleShot(0, lambda: self.edit_design_tabs.setCurrentIndex(0))

    def _hide_main_ui_elements(self):
        """Hides the main editor UI elements."""
        # Note: We already hide menuBar in __init__
        if hasattr(self, "main_splitter"):
            self.main_splitter.hide()
        for dock in self.docks:
            dock.hide()
        for toolbar in self.toolbars:
            toolbar.hide()

    def show_main_ui(self):
        """Shows the main editor UI and hides the welcome screen."""
        mode = self.controller.current_project_mode # Get current mode
        if mode:
             self.file_explorer.set_project_mode(mode)
        else:
             mode = "free" # Default assumption if mode is somehow None
             self.file_explorer.set_project_mode(mode)

        if self.welcome_screen:
            self.welcome_screen.hide()

        self.setCentralWidget(self.main_splitter)
        self.main_splitter.show()
        for dock in self.docks: dock.show()
        for toolbar in self.toolbars: toolbar.show()
        self.menuBar().show()

        # --- Update Action Visibility and Enable States ---
        # Disable/Hide all project-dependent first
        for action in self.project_dependent_actions:
             action.setEnabled(False)
             action.setVisible(False)

        # Enable/Show common ones
        common_actions = [
            self.action_save, self.action_save_as, self.action_save_all,
            self.action_undo, self.action_redo, self.action_cut, self.action_copy,
            self.action_paste, self.action_export_project, self.action_run_in_browser
        ]
        for action in common_actions:
            if action != self.action_save_as: # Keep Save As disabled if not implemented
                 action.setEnabled(True)
            action.setVisible(True)

        # Enable/Show mode-specific ones
        if mode == "guided":
            self.action_new_page.setEnabled(True)
            self.action_new_page.setVisible(True)
            # Ensure free mode actions are hidden (redundant but safe)
            self.action_new_file.setVisible(False)
            self.action_new_folder.setVisible(False)
        elif mode == "free":
            self.action_new_file.setEnabled(True)
            self.action_new_file.setVisible(True)
            self.action_new_folder.setEnabled(True)
            self.action_new_folder.setVisible(True)
             # Ensure guided mode action is hidden (redundant but safe)
            self.action_new_page.setVisible(False)
        # --- End Action Update ---

        self.status_bar.showMessage("Project loaded.", 3000)
        self.file_explorer.setFocus()


    def update_icons(self):
        """Refreshes icons on actions and welcome screen after theme change."""
        self.action_new_page.setIcon(QIcon(self.theme_manager.get_icon("new_page")))
        self.action_save.setIcon(QIcon(self.theme_manager.get_icon("save")))
        self.action_save_all.setIcon(QIcon(self.theme_manager.get_icon("save_all")))
        self.action_undo.setIcon(QIcon(self.theme_manager.get_icon("undo")))
        self.action_redo.setIcon(QIcon(self.theme_manager.get_icon("redo")))
        self.action_cut.setIcon(QIcon(self.theme_manager.get_icon("cut")))
        self.action_copy.setIcon(QIcon(self.theme_manager.get_icon("copy")))
        self.action_paste.setIcon(QIcon(self.theme_manager.get_icon("paste")))
        self.action_toggle_theme.setIcon(
            QIcon(self.theme_manager.get_icon("toggle_theme"))
        )
        self.action_export_project.setIcon(QIcon(self.theme_manager.get_icon("export")))
        self.action_run_in_browser.setIcon(QIcon(self.theme_manager.get_icon("run")))

        # Update tab icons
        if hasattr(self, 'edit_design_tabs'): # Check if initialized
            self.edit_design_tabs.currentChanged.connect(self.handle_edit_design_tab_changed)
            self.edit_design_tabs.setTabIcon(0, QIcon(self.theme_manager.get_icon("code")))
            self.edit_design_tabs.setTabIcon(1, QIcon(self.theme_manager.get_icon("design")))

        # Update Welcome Screen if it still exists and is visible
        if hasattr(self, "welcome_screen") and self.welcome_screen and self.welcome_screen.isVisible():
            self.welcome_screen.update_icons()
            self.welcome_screen.update_styles() # Styles might depend on icons/theme state

    def closeEvent(self, event):
        """Handles window close event, checking for unsaved changes."""
        # Check only if the main UI (splitter) is visible, implying a project is open
        if hasattr(self, 'main_splitter') and self.main_splitter.isVisible():
            if self.code_editor_widget.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    "You have unsaved changes. Do you want to save before exiting?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save # Default to Save
                )
                if reply == QMessageBox.StandardButton.Save:
                    # Attempt to save all files; if successful, accept the event
                    # If saving fails (e.g., permission error), save_all_files should show a message,
                    # and we might want to reconsider closing. For now, assume save works or user sees error.
                    self.code_editor_widget.save_all_files()
                    event.accept()
                elif reply == QMessageBox.StandardButton.Discard:
                    event.accept()
                else: # Cancel
                    event.ignore()
            else:
                # No unsaved changes, safe to close
                event.accept()
        else:
            # Welcome screen is visible, safe to close
            event.accept()