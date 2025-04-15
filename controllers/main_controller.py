# website_builder/controllers/main_controllers.py
import json
import os
import re
import shutil
import logging
from bs4 import BeautifulSoup
from PyQt6.QtCore import QObject, pyqtSlot, QUrl
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QLineEdit,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QPushButton,
)

logger = logging.getLogger(__name__)

class MainController(QObject):
    def __init__(self, main_window, theme_manager, welcome_screen):
        super().__init__()
        self.window = main_window
        self.theme_manager = theme_manager
        self.welcome_screen = welcome_screen
        self.current_project_path = None
        self.projects_dir = self._get_root_projects_directory()
        self.current_project_mode = "free"
        self._signals_connected = False
        self._connect_signals()

    def _get_root_projects_directory(self) -> str:
        """Gets or creates the 'Projects' directory in the application's root directory."""
        # Get the absolute path to the directory containing main.py (assuming it's the root)
        app_root = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        projects_dir = os.path.join(app_root, "Projects")

        if not os.path.exists(projects_dir):
            try:
                os.makedirs(projects_dir)
                print(f"MainController: Created Projects directory in root: {projects_dir}")
            except OSError as e:
                print(f"MainController: Error creating Projects directory in root: {e}")
                # Fallback to a default directory (e.g., user's home) if creation fails
                projects_dir = os.path.expanduser("~")
        return projects_dir

    def _connect_signals(self):
        """Connects signals from the UI to controller methods."""
        if self._signals_connected: return
        logger.debug("Connecting controller signals...")

        if self.welcome_screen:
            try: # Add try/except for robustness during debugging
                self.welcome_screen.create_project_requested.connect(
                    self.create_new_project_dialog
                )
                self.welcome_screen.open_project_requested.connect(
                    self.open_folder_dialog
                )
                logger.debug("Connected WelcomeScreen signals.")
            except Exception as e:
                 logger.error(f"Error connecting WelcomeScreen signals: {e}", exc_info=True)


        # --- File Menu Actions ---
        try:
            # File Menu Actions
            if hasattr(self.window, 'action_new_page'):  # Check if action exists
                self.window.action_new_page.triggered.connect(self.create_new_page)  # Guided Mode
            if hasattr(self.window, 'action_new_file'):  # Check if action exists
                self.window.action_new_file.triggered.connect(self.handle_new_file_action)  # Free Mode <-- ADD
            if hasattr(self.window, 'action_new_folder'):  # Check if action exists
                self.window.action_new_folder.triggered.connect(self.handle_new_folder_action)  # Free Mode <-- ADD

            if hasattr(self.window, 'action_save'):
                self.window.action_save.triggered.connect(self.save_current_file)
            if hasattr(self.window, 'action_save_all'):
                self.window.action_save_all.triggered.connect(self.save_all_files)  # Connect if action exists
            if hasattr(self.window, 'action_exit'):
                self.window.action_exit.triggered.connect(self.window.close)  # Connect if action exists

            logger.debug("Connected File menu signals.")
        except AttributeError as e:
             logger.warning(f"AttributeError connecting File menu signals: {e}. Some actions might be missing.")
        except Exception as e:
             logger.error(f"Error connecting File menu signals: {e}", exc_info=True)


        # --- Edit Menu Actions ---
        try:
            self.window.action_undo.triggered.connect(self.undo)
            self.window.action_redo.triggered.connect(self.redo)
            # Add cut/copy/paste connections if implemented
            logger.debug("Connected Edit menu signals.")
        except AttributeError as e:
             logger.warning(f"AttributeError connecting Edit menu signals: {e}.")
        except Exception as e:
             logger.error(f"Error connecting Edit menu signals: {e}", exc_info=True)


        # --- View Menu Actions ---
        try:
            self.window.action_toggle_theme.triggered.connect(self.toggle_theme)
            # Connections for toggle docks are in MainWindow itself
            logger.debug("Connected View menu signals.")
        except AttributeError as e:
             logger.warning(f"AttributeError connecting View menu signals: {e}.")
        except Exception as e:
             logger.error(f"Error connecting View menu signals: {e}", exc_info=True)


        # --- Project Menu Actions ---
        try:
            self.window.action_export_project.triggered.connect(self.export_project)
            self.window.action_run_in_browser.triggered.connect(self.run_in_browser)
            logger.debug("Connected Project menu signals.")
        except AttributeError as e:
             logger.warning(f"AttributeError connecting Project menu signals: {e}.")
        except Exception as e:
             logger.error(f"Error connecting Project menu signals: {e}", exc_info=True)


        # --- Widget Signals ---
        try:
            # --- Connect to the NEW FileExplorer signal ---
            self.window.file_explorer.guided_page_creation_requested.connect(self.handle_guided_page_request)
            # --- Keep other FileExplorer signal connections ---
            self.window.file_explorer.file_selected.connect(self.handle_file_selected)
            self.window.file_explorer.folder_changed.connect(self.handle_folder_changed)

            # ... (connect CodeEditorTabWidget signals) ...
            self.window.code_editor_widget.content_changed.connect(self.handle_content_change)
            self.window.code_editor_widget.tab_closed_signal.connect(self.handle_tab_closed)

            logger.debug("Connected Widget signals.")
        except AttributeError as e:
             logger.warning(f"AttributeError connecting Widget signals: {e}. Some widgets might be missing.")
        except Exception as e:
             logger.error(f"Error connecting Widget signals: {e}", exc_info=True)


        # --- Set flag to prevent re-connection ---
        self._signals_connected = True
        logger.info("Controller signals connected successfully.")
        # -----------------------------------------

    def _resolve_resource_path(self, resource_link, html_file_path):
        """Resolves a CSS/JS link relative to the HTML file and project root."""
        if not resource_link or not html_file_path or not self.current_project_path:
            logger.warning(
                f"Cannot resolve path, missing info: link='{resource_link}', html='{html_file_path}', project='{self.current_project_path}'")
            return None
        # Basic cleaning: remove potential query strings or fragments
        resource_link = resource_link.split('?')[0].split('#')[0].strip()
        if not resource_link:
            logger.warning(f"Empty resource link after cleaning in {html_file_path}")
            return None

        abs_path = None
        try:
            # Check if absolute path relative to project root
            if resource_link.startswith('/'):
                # Ensure we don't join // if resource_link is just "/"
                path_segment = resource_link[1:] if len(resource_link) > 1 else ""
                abs_path = os.path.abspath(os.path.join(self.current_project_path, path_segment))
            # Check if absolute file URI (less common for local dev, handle basic case)
            elif resource_link.startswith('file:///'):
                local_path = QUrl(resource_link).toLocalFile()
                # Check if path is within project (security/sanity check)
                if os.path.abspath(local_path).startswith(os.path.abspath(self.current_project_path)):
                    abs_path = os.path.abspath(local_path)
                else:
                    logger.warning(f"File URI '{resource_link}' points outside project root.")
                    abs_path = None  # Disallow external file URIs for now
            # Check for Windows absolute path (e.g., C:/...) - less likely in href
            elif re.match(r'^[a-zA-Z]:[\\/]', resource_link):
                logger.warning(f"Absolute system path '{resource_link}' found in HTML link, potentially non-portable.")
                abs_path = os.path.abspath(resource_link)  # Resolve it but be aware
                # Could add check if it's within project root here too
            # Assume relative path to HTML file
            else:
                html_dir = os.path.dirname(html_file_path)
                abs_path = os.path.abspath(os.path.join(html_dir, resource_link))

            # Optional: Final check if resolved path is within project boundaries
            if abs_path and not os.path.abspath(abs_path).startswith(os.path.abspath(self.current_project_path)):
                logger.warning(
                    f"Resolved path '{abs_path}' is outside project root '{self.current_project_path}'. Treating as invalid.")
                return None

        except Exception as e:
            logger.error(f"Error resolving path for link '{resource_link}' relative to '{html_file_path}': {e}")
            return None

        return abs_path

    # --- NEW: Validation logic ---
    def validate_design_view_access(self):
        """
        Checks if the current HTML file in the editor has valid CSS/JS links
        required for the Design View in Free Form mode.

        Returns:
            tuple[bool, list | str]: (isValid, details)
             - isValid: True if access should be granted, False otherwise.
             - details: Empty list [] if valid, or a list of missing file paths (str),
                        or a string code ('no_references', 'not_html', 'error') otherwise.
        """
        if self.current_project_mode != "free":
            logger.debug("Allowing Design View access (not free mode).")
            return True, []  # Allow in guided mode (links are implicit)

        try:
            file_path, content = self.window.code_editor_widget.get_current_editor_content()

            if not file_path or not content:
                logger.warning("Cannot validate design view: No active file/content.")
                # Show message? Or just disallow? Let's disallow silently for now.
                return False, "no_file"

            if not file_path.lower().endswith((".html", ".htm")):
                logger.debug("Design view check: Not an HTML file.")
                QMessageBox.information(self.window, "Design View Unavailable",
                                        "Design View is only available for HTML files.")
                return False, "not_html"

            if not self.current_project_path:
                logger.error("Cannot validate design view access: Project path not set.")
                QMessageBox.critical(self.window, "Error", "Cannot validate file paths: Project root not identified.")
                return False, "error"

            logger.debug(f"Validating Design View for: {file_path}")

            # Parse HTML
            try:
                # Use 'lxml' if installed for speed, fallback to 'html.parser'
                soup = BeautifulSoup(content, 'lxml')
            except ImportError:
                logger.warning("lxml parser not found, using html.parser.")
                soup = BeautifulSoup(content, 'html.parser')
            except Exception as e:
                logger.error(f"HTML parsing failed for {file_path}: {e}", exc_info=True)
                QMessageBox.critical(self.window, "HTML Parsing Error",
                                     f"Could not parse the HTML file to check links:\n{e}")
                return False, "error"

            # Find links
            css_links = [link.get('href') for link in soup.find_all('link', rel='stylesheet') if link.get('href')]
            js_links = [script.get('src') for script in soup.find_all('script', src=True) if
                        script.get('src')]  # Check src exists

            logger.debug(f"Found CSS links: {css_links}")
            logger.debug(f"Found JS links: {js_links}")

            # Condition 1: No references
            if not css_links and not js_links:
                logger.warning("Design View check failed: No CSS or JS references found.")
                QMessageBox.warning(self.window, "Design View Unavailable",
                                    "This HTML file does not reference any CSS or JavaScript files using standard tags "
                                    "(<link rel='stylesheet'> or <script src='...'>).\n\n"
                                    "Please add references to enable Design View in Free Form mode.")
                return False, "no_references"

            # Condition 2: Check if referenced files exist
            missing_files = []
            all_links = [("CSS", href) for href in css_links] + [("JS", src) for src in js_links]

            for file_type, link in all_links:
                resolved_path = self._resolve_resource_path(link, file_path)
                if resolved_path is None:
                    # Resolution failed (bad path format, outside project, etc.)
                    missing_files.append(f"{link} ({file_type} path invalid or could not be resolved)")
                elif not os.path.exists(resolved_path):
                    logger.warning(
                        f"Missing {file_type} file: '{resolved_path}' (referenced as '{link}' in {file_path})")
                    # Show path relative to project root for clarity
                    relative_missing = os.path.relpath(resolved_path, self.current_project_path)
                    missing_files.append(f"{relative_missing} ({file_type}, from '{link}')")

            if missing_files:
                logger.warning(f"Design View check failed: Missing files - {missing_files}")
                missing_str = "\n - ".join(missing_files)
                QMessageBox.warning(self.window, "Missing Files Referenced",
                                    "Cannot open Design View because the following referenced files were not found "
                                    "or could not be resolved within the project:\n\n - "
                                    f"{missing_str}\n\nPlease check the href/src paths in your HTML or create the missing files.")
                return False, missing_files  # Return the list of missing relative paths

            # Condition 3: All referenced files exist
            logger.debug("Design View check passed.")
            return True, []

        except Exception as e:
            logger.error(f"Unexpected error during Design View validation: {e}", exc_info=True)
            QMessageBox.critical(self.window, "Validation Error",
                                 f"An unexpected error occurred while checking file links:\n{e}")
            return False, "error"

    def create_new_project_dialog(self):
        """Opens a dialog to select the project creation mode."""

        dialog = QDialog(self.window)
        dialog.setWindowTitle("Select Project Mode")
        layout = QVBoxLayout()

        mode_label = QLabel("Select Project Mode:")
        layout.addWidget(mode_label)

        mode_group = QButtonGroup()
        free_mode_radio = QRadioButton("Free Mode (Full Control)")
        guided_mode_radio = QRadioButton("Guided Mode (Page-Based)")
        mode_group.addButton(free_mode_radio)
        mode_group.addButton(guided_mode_radio)
        free_mode_radio.setChecked(True)  # Default to Free Mode

        layout.addWidget(free_mode_radio)
        layout.addWidget(guided_mode_radio)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        def on_ok_clicked():
            mode = "free" if free_mode_radio.isChecked() else "guided"
            dialog.accept()  # Close the dialog and set result to Accepted
            self.create_new_project(mode)  # Create the project

        ok_button.clicked.connect(on_ok_clicked)
        cancel_button.clicked.connect(dialog.reject)  # Close the dialog and set result to Rejected

        if dialog.exec() == QDialog.DialogCode.Accepted:
            print("MainController: User selected a project mode and clicked OK.")
        else:
            print("MainController: User cancelled project creation.")

    @pyqtSlot(str)
    def create_new_project(self, mode: str):
        """Guides user to create a new project folder and initializes it based on mode."""
        # ... (keep logic for getting parent_dir and project_name_raw) ...
        self.current_project_mode = mode
        print(f"MainController: Creating project in {mode} mode.")
        parent_dir = QFileDialog.getExistingDirectory(
            self.window, "Select Parent Directory for New Project", self.projects_dir,
        )
        if not parent_dir: return
        project_name_raw, ok = QInputDialog.getText(self.window, "Create New Project", "Enter project name:",
                                                    QLineEdit.EchoMode.Normal)

        if ok and project_name_raw:
            project_name_raw = project_name_raw.strip()
            # ... (keep validation checks for project_name_raw) ...
            if not project_name_raw or "/" in project_name_raw or "\\" in project_name_raw:
                QMessageBox.warning(self.window, "Invalid Name", "Please enter a valid project name (no slashes).")
                return

            new_project_path = os.path.join(parent_dir, project_name_raw)  # This is the root project folder

            if os.path.exists(new_project_path):
                QMessageBox.warning(self.window, "Error",
                                    f"A directory named '{project_name_raw}' already exists here.")
                return

            try:
                # Create the main project root directory
                os.makedirs(new_project_path)
                print(f"MainController: Created new project directory: {new_project_path}")

                # --- Sanitize project name for filenames ---
                # (Used for file names inside the subfolder in guided mode, or root files in free mode)
                sanitized_name = project_name_raw.lower().replace(" ", "_").replace("-", "_")
                sanitized_name = re.sub(r'[^\w_]+', '', sanitized_name)
                if not sanitized_name: sanitized_name = "project"
                print(f"MainController: Sanitized base name for files: {sanitized_name}")

                # --- Create Basic Project Files Based on Mode ---
                initial_file_to_open = None
                try:
                    if mode == "free":
                        # Free Mode: Files created directly in project root (no change here)
                        html_path = os.path.join(new_project_path, "index.html")
                        css_path = os.path.join(new_project_path, "style.css")
                        js_path = os.path.join(new_project_path, "script.js")
                        # ... (with open blocks for free mode remain the same) ...
                        with open(html_path, "w", encoding="utf-8") as f_html:
                            f_html.write(f"""...""")  # Shortened for brevity
                        with open(css_path, "w", encoding="utf-8") as f_css:
                            f_css.write(f"""...""")
                        with open(js_path, "w", encoding="utf-8") as f_js:
                            f_js.write(f"""...""")
                        initial_file_to_open = html_path
                        print(f"MainController: Created Free Mode files in {new_project_path}")

                    elif mode == "guided":
                        # --- Guided Mode: Create subfolder and files INSIDE it ---

                        # 1. Determine subfolder name (use raw name, cleaned slightly for safety)
                        subfolder_name = project_name_raw.strip().replace('/', '_').replace('\\', '_')
                        if not subfolder_name: subfolder_name = "home"  # Fallback if name is invalid
                        subfolder_path = os.path.join(new_project_path, subfolder_name)

                        # 2. Create the subfolder
                        os.makedirs(subfolder_path,
                                    exist_ok=True)  # exist_ok=True handles case if somehow created already
                        logger.info(f"Ensured subfolder exists: {subfolder_path}")

                        # 3. Define file paths INSIDE the subfolder using the fully sanitized name
                        html_filename = f"{sanitized_name}.html"
                        css_filename = f"{sanitized_name}.css"
                        js_filename = f"{sanitized_name}.js"
                        html_path = os.path.join(subfolder_path, html_filename)
                        css_path = os.path.join(subfolder_path, css_filename)
                        js_path = os.path.join(subfolder_path, js_filename)

                        # 4. Create files inside the subfolder
                        with open(html_path, "w", encoding="utf-8") as f_html:
                            f_html.write(f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{project_name_raw}</title>
        <link rel="stylesheet" href="{css_filename}">
    </head>
    <body>
        <h1>Welcome to {project_name_raw}!</h1>
        <p>This is the starting page for your '{project_name_raw}' project.</p>
        <script src="{js_filename}"></script>
    </body>
    </html>""")
                        with open(css_path, "w", encoding="utf-8") as f_css:
                            f_css.write(f"""/* Styles for {project_name_raw} ({html_filename}) */
    body {{
        font-family: sans-serif;
    }}""")
                        with open(js_path, "w", encoding="utf-8") as f_js:
                            f_js.write(
                                f"// JavaScript for {project_name_raw} ({html_filename})\n\nconsole.log('{project_name_raw} script loaded!');\n")

                        initial_file_to_open = html_path  # Path is now inside subfolder
                        print(f"MainController: Created Guided Mode initial files in {subfolder_path}")

                except Exception as file_err:
                    # ... (keep existing file error handling) ...
                    print(f"MainController: Warning: Could not create default project files: {file_err}")
                    QMessageBox.warning(self.window, "File Creation Warning",
                                        f"Could not create all default project files:\n{file_err}")

                # --- Create settings.json (common to both modes) ---
                self._create_project_settings(new_project_path, mode)

                # --- Show UI and Load Context ---
                self.window.show_main_ui()
                self._update_project_context(new_project_path)
                self.window.file_explorer.set_project_mode(self.current_project_mode)

                # --- Open the initial HTML file created ---
                if initial_file_to_open and os.path.exists(initial_file_to_open):
                    self.window.code_editor_widget.open_file(initial_file_to_open)
                    self.window.web_preview.load_file(initial_file_to_open)
                else:
                    print(f"MainController: Initial file '{initial_file_to_open}' not found or not created.")

            # ... (keep except OSError and other exception handling) ...
            except OSError as e:
                QMessageBox.critical(self.window, "Error", f"Failed to create project directory:\n{e}")
                print(f"MainController: Error creating project directory: {e}")
            except Exception as e:
                QMessageBox.critical(self.window, "Error",
                                     f"An unexpected error occurred during project creation:\n{e}")
                print(f"MainController: Unexpected error creating project: {e}")

    def _create_project_settings(self, project_path: str, mode: str):
        """Creates the settings.json file to store project settings."""
        settings = {"mode": mode}
        settings_path = os.path.join(project_path, "settings.json")
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            print(f"MainController: Created settings.json in: {project_path}")
        except Exception as e:
            print(f"MainController: Error creating settings.json: {e}")
            QMessageBox.warning(self.window, "Settings Warning", f"Could not create settings.json:\n{e}")

    @pyqtSlot()
    def handle_new_file_action(self):
        """Handles File -> New File action."""
        logger.debug("handle_new_file_action called")
        if self.current_project_mode != "free":
            logger.warning("New File action triggered, but not in free mode.")
            return  # Or show message
        if self.current_project_path:
            # Use the file explorer's existing method to create the item
            # Assumes create_item handles prompting for name itself
            self.window.file_explorer.create_item(self.current_project_path, is_file=True)
        else:
            QMessageBox.information(self.window, "No Project Open", "Please open a project folder first.")

    @pyqtSlot()
    def handle_new_folder_action(self):
        """Handles File -> New Folder action."""
        logger.debug("handle_new_folder_action called")
        if self.current_project_mode != "free":
            logger.warning("New Folder action triggered, but not in free mode.")
            return  # Or show message
        if self.current_project_path:
            # Use the file explorer's existing method to create the item
            self.window.file_explorer.create_item(self.current_project_path, is_file=False)
        else:
            QMessageBox.information(self.window, "No Project Open", "Please open a project folder first.")

    @pyqtSlot()
    def create_new_file_in_explorer(self):
        """Handles the creation of a new file in the file explorer."""
        if self.current_project_path:
            self.window.file_explorer.create_item(self.current_project_path, is_file=True)
        else:
            QMessageBox.information(self.window, "No Folder Open",
                                    "Please open a project folder first to create a new file.")

    def _create_guided_page_structure(self, project_path, page_name_raw):
        """
        Creates a folder for the page and generates HTML, CSS, JS files inside.

        Args:
            project_path (str): The root path of the guided project.
            page_name_raw (str): The raw name entered by the user for the page.

        Returns:
            str | None: The absolute path to the created HTML file, or None on failure.
        """
        if not page_name_raw:
            logger.warning("Guided page creation attempt with empty name.")
            return None

        # Sanitize for folder name (allow spaces, keep case, replace slashes)
        folder_name = page_name_raw.strip().replace('/', '_').replace('\\', '_')
        if not folder_name:  # Check again after potential stripping
            logger.warning("Guided page name resulted in empty folder name.")
            QMessageBox.warning(self.window, "Invalid Name", "Please enter a valid page name.")
            return None
        folder_path = os.path.join(project_path, folder_name)

        # Sanitize for file base name (lowercase, underscores, alphanumeric only)
        sanitized_file_base = re.sub(r'[^\w_]+', '', folder_name.lower().replace(" ", "_").replace("-", "_"))
        if not sanitized_file_base:
            sanitized_file_base = "page"  # Fallback if sanitization removes everything
        html_filename = f"{sanitized_file_base}.html"
        css_filename = f"{sanitized_file_base}.css"
        js_filename = f"{sanitized_file_base}.js"

        html_path = os.path.join(folder_path, html_filename)
        css_path = os.path.join(folder_path, css_filename)
        js_path = os.path.join(folder_path, js_filename)

        logger.info(f"Attempting to create guided page structure in: {folder_path}")

        # Check if folder already exists
        if os.path.exists(folder_path):
            # Check if it's actually a directory, not a file with the same name
            if not os.path.isdir(folder_path):
                QMessageBox.warning(self.window, "Naming Conflict",
                                    f"A file named '{folder_name}' already exists. Please choose a different page name.")
                logger.warning(f"Page creation conflict: File exists with name '{folder_name}'.")
                return None

            # Folder exists, check if conflicting files are inside
            if os.path.exists(html_path) or os.path.exists(css_path) or os.path.exists(js_path):
                QMessageBox.warning(self.window, "Page Exists",
                                    f"A folder named '{folder_name}' already exists and contains conflicting page files (HTML, CSS, or JS).")
                logger.warning(f"Page creation conflict: Folder '{folder_name}' exists with conflicting files.")
                return None
            else:
                logger.info(f"Folder '{folder_name}' exists, but no conflicting files found inside. Proceeding.")
                # Folder exists but is empty or contains unrelated files - OK to proceed creating files inside

        try:
            # Create folder if it doesn't exist
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                logger.info(f"Created directory: {folder_path}")

            # Create HTML file with basic structure, linking relative CSS/JS
            with open(html_path, 'w', encoding='utf-8') as f_html:
                f_html.write(f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_name_raw}</title>
        <link rel="stylesheet" href="{css_filename}">
    </head>
    <body>
        <h1>{page_name_raw}</h1>
        <p>Content for the {page_name_raw} page goes here.</p>
        <script src="{js_filename}"></script>
    </body>
    </html>""")

            # Create CSS file
            with open(css_path, 'w', encoding='utf-8') as f_css:
                f_css.write(
                    f"/* Styles for {page_name_raw} ({html_filename}) */\n\nbody {{\n    font-family: sans-serif;\n}}\n")

            # Create JS file
            with open(js_path, 'w', encoding='utf-8') as f_js:
                f_js.write(
                    f"// JavaScript for {page_name_raw} ({html_filename})\n\nconsole.log('{folder_name} page script loaded.');\n")

            logger.info(f"Successfully created page files for '{page_name_raw}' in {folder_path}.")
            return html_path  # Return path to the HTML file

        except OSError as e:
            logger.error(f"OSError creating page structure for '{page_name_raw}' in {folder_path}: {e}",
                         exc_info=True)
            QMessageBox.critical(self.window, "Error Creating Page",
                                 f"Could not create page directory or files:\n{e}")
            # Optional: Clean up partially created folder/files?
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating page structure for '{page_name_raw}': {e}", exc_info=True)
            QMessageBox.critical(self.window, "Error Creating Page", f"An unexpected error occurred:\n{e}")
            return None

    @pyqtSlot()
    def create_new_page(self):
        logger.debug(f"create_new_page called. Mode: {self.current_project_mode}")
        if self.current_project_mode != "guided":
            QMessageBox.warning(self.window, "Action Not Available",
                                "'New Page' action is only available in Guided Mode projects.")
            return
        if not self.current_project_path:
            QMessageBox.warning(self.window, "No Project", "Cannot create page: No project is currently open.")
            return
        page_name_raw, ok = QInputDialog.getText(self.window, "Create New Guided Page", "Enter page name:",
                                                 QLineEdit.EchoMode.Normal)
        if ok and page_name_raw:
            created_html_path = self._create_guided_page_structure(self.current_project_path, page_name_raw)
            if created_html_path:
                logger.info(f"New page '{page_name_raw}' created via menu. Opening {created_html_path}")
                self.window.code_editor_widget.open_file(created_html_path)
                self.window.web_preview.load_file(created_html_path)
            else:
                logger.error(f"Failed to create page structure for '{page_name_raw}'.")
        else:
            logger.debug("User cancelled new page creation via menu.")
    pass

    @pyqtSlot(str)
    def handle_guided_page_request(self, page_name_raw):
        """Handles request from FileExplorer context menu to create a guided page."""
        logger.info(f"handle_guided_page_request received for: {page_name_raw}")
        if self.current_project_mode != "guided":
            logger.warning("Guided page request ignored: Not in guided mode.")
            # Should not happen if context menu action is only enabled in guided mode
            return
        if not self.current_project_path:
            logger.error("Cannot handle guided page request: No project path.")
            QMessageBox.warning(self.window, "No Project", "Cannot create page: No project is currently open.")
            return

        created_html_path = self._create_guided_page_structure(self.current_project_path, page_name_raw)

        if created_html_path:
            logger.info(f"New page '{page_name_raw}' created via context menu. Opening {created_html_path}")
            # Open the newly created HTML file
            self.window.code_editor_widget.open_file(created_html_path)
            self.window.web_preview.load_file(created_html_path)
        else:
            logger.error(f"Failed to create page structure for '{page_name_raw}' via context menu.")
            # User already shown error message by _create_guided_page_structure

    @pyqtSlot()
    def open_file_dialog(self):
        """Opens a file using a file dialog."""
        start_dir = self.current_project_path or self.projects_dir or os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open File",
            start_dir,
            "Web Files (*.html *.htm *.css *.js);;HTML Files (*.html *.htm);;CSS Files (*.css);;JavaScript Files (*.js);;All Files (*)"
        )
        if file_path:
            self.window.code_editor_widget.open_file(file_path)
            # Also load in preview if HTML
            if file_path.lower().endswith((".html", ".htm")):
                self.window.web_preview.load_file(file_path)

    @pyqtSlot()
    def open_folder_dialog(self):
        """Opens an existing project folder."""

        # Use self.projects_dir as the initial directory
        folder_path = QFileDialog.getExistingDirectory(
            self.window,
            "Open Project Folder",
            self.projects_dir
        )
        if folder_path:
            # --- Read project settings ---
            settings_path = os.path.join(folder_path, "settings.json")
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                    self.current_project_mode = settings.get("mode", "free")  # Get mode or default to "free"
                    print(f"MainController: Opened project in {self.current_project_mode} mode.")
                except Exception as e:
                    print(f"MainController: Error reading settings.json: {e}")
                    self.current_project_mode = "free"  # Default to "free" if error
            else:
                print("MainController: settings.json not found, assuming free mode.")
                self.current_project_mode = "free"  # Default if file missing

            self.window.show_main_ui()
            self._update_project_context(folder_path)
            self.window.file_explorer.set_project_mode(self.current_project_mode)  # Inform FileExplorer

    def _update_project_context(self, folder_path):
        """Updates file explorer, preview, and window title for the given path."""

        if folder_path and os.path.isdir(folder_path):
            self.current_project_path = folder_path
            self.window.file_explorer.set_root_path(folder_path) # This will also trigger filter update in explorer
            self.window.web_preview.set_project_root(folder_path) # This might auto-load index/default file
            project_folder_name = os.path.basename(folder_path)
            self.window.setWindowTitle(f"{project_folder_name} - Flexta")
            print(f"MainController: Project context updated to: {folder_path}")
            # Maybe close tabs from previous project? Optional.
            # self.window.code_editor_widget.close_all_tabs()
        else:
            print(f"MainController: Error updating project context: Invalid path '{folder_path}'")
            self.current_project_path = None
            # Optionally clear file explorer, preview, title here
            self.window.setWindowTitle("Flexta")

    @pyqtSlot(str)
    def handle_file_selected(self, file_path):
        """Handles the signal when a file is selected in the file explorer."""

        print(f"MainController: handle_file_selected called with file_path: {file_path}")
        print(f"MainController: Current project path: {self.current_project_path}")
        print(f"MainController: Checking if file exists: {os.path.exists(file_path)}")

        self.window.code_editor_widget.open_file(file_path)
        # Load in preview if it's an HTML file
        if file_path.lower().endswith((".html", ".htm")):
            self.window.web_preview.load_file(file_path)

    @pyqtSlot(str, str)
    def handle_content_change(self, file_path, content):
        """Handles the signal when the content of a file changes in the code editor."""

        print(f"MainController: Content changed in {file_path}")
        # TODO: Implement synchronization logic between code editor, visual designer, and preview

    @pyqtSlot(str)
    def handle_folder_changed(self, folder_path):
        """Handles the signal when the file explorer's root folder changes."""
        print(f"MainController: handle_folder_changed called with folder_path: {folder_path}")
        # Update project path when file explorer root changes
        self.current_project_path = folder_path
        self.window.web_preview.set_project_root(folder_path)
        self.window.setWindowTitle(f"{os.path.basename(folder_path)} - PyQt Website Builder")

    @pyqtSlot(str)
    def handle_tab_closed(self, file_path):
        """Handles the signal when a tab is closed in the code editor."""

        print(f"MainController: Tab closed for {file_path}")
        # TODO: Implement any necessary cleanup or state updates when a tab is closed

    @pyqtSlot()
    def save_current_file(self):
        """Saves the currently active file in the code editor."""

        print("MainController: save_current_file requested.")
        self.window.code_editor_widget.save_current_file()

    @pyqtSlot()
    def save_file_as(self):
        """Handles the "Save As" functionality."""

        print("MainController: save_file_as requested.")
        # TODO: Implement Save As logic
        QMessageBox.information(self.window, "Not Implemented", "Save As functionality is not yet implemented.")

    @pyqtSlot()
    def save_all_files(self):
        """Saves all open files in the code editor."""

        print("MainController: save_all_files requested.")
        self.window.code_editor_widget.save_all_files()

    @pyqtSlot()
    def undo(self):
        """Handles the "Undo" action."""

        print("MainController: undo requested.")
        # TODO: Implement Undo logic (likely in the code editor or visual designer)

    @pyqtSlot()
    def redo(self):
        """Handles the "Redo" action."""

        print("MainController: redo requested.")
        # TODO: Implement Redo logic (likely in the code editor or visual designer)

    @pyqtSlot()
    def toggle_theme(self):
        """Toggles between light and dark themes."""

        print("MainController: toggle_theme requested.")
        self.theme_manager.toggle_theme()

    @pyqtSlot()
    def export_project(self):
        """Exports the current project to a deployable folder."""

        print("MainController: export_project requested.")
        if not self.current_project_path:
            QMessageBox.warning(self.window, "No Project", "Please open or create a project folder first.")
            return

        target_dir = QFileDialog.getExistingDirectory(self.window, "Select Export Destination Folder", os.path.expanduser("~"))

        if target_dir:
            source_dir = self.current_project_path
            destination = os.path.join(target_dir, os.path.basename(source_dir) + "_export")
            try:
                shutil.copytree(source_dir, destination, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', '.vscode'))
                QMessageBox.information(self.window, "Export Successful", f"Project exported successfully to:\n{destination}")
                print(f"MainController: Project exported from {source_dir} to {destination}")
            except Exception as e:
                QMessageBox.critical(self.window, "Export Failed", f"Could not export project:\n{e}")
                print(f"MainController: Error exporting project: {e}")

    @pyqtSlot()
    def run_in_browser(self):
        """Opens the main HTML file of the project in the default web browser."""

        print("MainController: run_in_browser requested.")
        # Find the currently previewed HTML file or index.html
        file_to_open = self.window.web_preview.current_file
        if not file_to_open and self.current_project_path:
            index_path = os.path.join(self.current_project_path, "index.html")
            if os.path.exists(index_path):
                file_to_open = index_path

        if file_to_open and os.path.exists(file_to_open):
            try:
                import webbrowser
                # Convert path to file:/// URL
                url = QUrl.fromLocalFile(file_to_open).toString()
                webbrowser.open(url)
                print(f"MainController: Opening {url} in default browser.")
            except Exception as e:
                QMessageBox.critical(self.window, "Error", f"Could not open file in browser:\n{e}")
                print(f"MainController: Error opening in browser: {e}")
        else:
            QMessageBox.warning(self.window, "No File", "No HTML file is currently active in the preview or found as index.html in the project root.")