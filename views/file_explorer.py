# website_builder/views/file_explorer.py
import os
import shutil
import logging
from PyQt6.QtWidgets import ( QTreeView, QMenu, QInputDialog, QMessageBox,
                              QLineEdit, QApplication, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem )
from PyQt6.QtCore import QDir, QModelIndex, Qt, QFileSystemWatcher, pyqtSignal, QTimer, pyqtSlot, QItemSelectionModel, QEvent
from PyQt6.QtGui import QAction, QIcon, QFileSystemModel, QKeySequence, QKeyEvent
from .project_file_proxy_model import ProjectFileProxyModel

logger = logging.getLogger(__name__)

class FileExplorerDelegate(QStyledItemDelegate):
    """Custom delegate to adjust the MINIMUM SIZE of the inline rename editor."""
    def createEditor(self, parent, option: QStyleOptionViewItem, index: QModelIndex):
        """Create a QLineEdit with adjusted minimum size."""
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            # --- Keep Sizing Logic ---
            tree_view = parent.parent()
            if isinstance(tree_view, QTreeView):
                column_width = tree_view.columnWidth(index.column())
                editor.setMinimumWidth(max(column_width, 200))
            else:
                editor.setMinimumWidth(200)
            editor.setMinimumHeight(24)
            # --- REMOVE STYLESHEET CALL ---
            # editor.setStyleSheet("""...""") # REMOVED

        logger.debug(f"Created editor for index {index.row()}: minSizeHint={editor.minimumSizeHint()}")
        return editor

    def updateEditorGeometry(self, editor, option: QStyleOptionViewItem, index: QModelIndex):
        """Ensure editor geometry respects minimums."""
        rect = option.rect
        # Use maximum of item rect size or editor's minimum size hint/explicit minimum
        width = max(rect.width(), editor.minimumWidth())
        height = max(rect.height(), editor.minimumHeight())
        editor.setGeometry(rect.x(), rect.y(), width, height)
        # logger.debug(f"Editor geometry for index {index.row()}: {editor.geometry()}") # Optional debug

class FileExplorer(QTreeView):
    # --- Signals ---
    file_selected = pyqtSignal(str)
    folder_changed = pyqtSignal(str)
    item_renamed = pyqtSignal(str, str)
    item_deleted = pyqtSignal(str)
    guided_page_creation_requested = pyqtSignal(str)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        try:
            app_instance = QApplication.instance()
            if app_instance:
                self.setFont(app_instance.font())
        except Exception as e:
            logger.error(f"Error setting FileExplorer font: {e}")

        # Model setup
        self.source_model = QFileSystemModel()
        self.source_model.setReadOnly(False)
        logger.debug("QFileSystemModel read-only state: %s", self.source_model.isReadOnly())
        self.proxy_model = ProjectFileProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self.setModel(self.proxy_model)

        self.project_mode = "free"
        self.current_root_path = ""

        # Model Filters/Options
        self.source_model.setFilter(
            QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.Hidden
        )
        self.source_model.setOption(QFileSystemModel.Option.DontWatchForChanges, True)

        # View settings
        for i in range(1, self.proxy_model.columnCount()):
            self.hideColumn(i)
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.AnyKeyPressed
        )

        # Set custom delegate
        self.setItemDelegate(FileExplorerDelegate(self))
        logger.debug("Set custom FileExplorerDelegate")

        # Connect signals
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.doubleClicked.connect(self.item_double_clicked)
        self.source_model.dataChanged.connect(self._handle_data_changed)

        # File Watcher
        self.root_watcher = QFileSystemWatcher(self)
        self.root_watcher.directoryChanged.connect(self._refresh_current_directory)

        # Delete Action
        self.delete_action = QAction("Delete", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.addAction(self.delete_action)
        self.delete_action.triggered.connect(self.delete_selected_items)
        self.selectionModel().selectionChanged.connect(self._update_delete_action_state)
        self._update_delete_action_state()

    def mouseReleaseEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.clearSelection()
        super().mouseReleaseEvent(event)

    def set_project_mode(self, mode: str):
        """Sets the project mode ('free' or 'guided') and updates proxy filter."""
        logger.info(f"Setting project mode to: {mode}")
        self.project_mode = mode
        # --- Tell the PROXY model the mode changed ---
        self.proxy_model.set_project_mode(mode)
        # --- No manual refresh needed, invalidateFilter() handles it ---

    # --- Removed _update_file_filters method as name filtering moved to proxy ---
    # def _update_file_filters(self): ...

    def set_root_path(self, path: str):
        """Sets the root path for the file explorer view."""
        path = os.path.normpath(path)
        if not QDir(path).exists():
            logger.error(f"Attempted to set invalid root path: {path}")
            QMessageBox.warning(
                self, "Invalid Path", f"The selected folder path does not exist:\n{path}"
            )
            return

        logger.info(f"Setting root path to: {path}")
        if self.current_root_path and self.current_root_path in self.root_watcher.directories():
            self.root_watcher.removePath(self.current_root_path)
            logger.debug(f"Stopped watching old root: {self.current_root_path}")

        self.current_root_path = path
        # --- Set root path on the SOURCE model ---
        self.source_model.setRootPath(path)
        # --- Get the index from the SOURCE model and map it for the view ---
        source_root_index = self.source_model.index(path)
        proxy_root_index = self.proxy_model.mapFromSource(source_root_index)
        self.setRootIndex(proxy_root_index)

        if path not in self.root_watcher.directories():
            self.root_watcher.addPath(path)
            logger.debug(f"Started watching new root: {path}")

        self.folder_changed.emit(path)
        # No need to call filter update here, proxy handles it based on its mode

    def _refresh_current_directory(self, path: str):
        """Refreshes the view for the current root directory."""
        # This might still be needed if the watcher approach is kept,
        # but it operates on the source model. The proxy will update automatically.
        if path == self.current_root_path:
            logger.debug(f"Root directory changed: {path}. Refreshing source model.")
            # Refreshing the source model should be sufficient
            self.source_model.setRootPath("") # Temporarily unset source
            self.source_model.setRootPath(self.current_root_path) # Reset source
            # The view connected to the proxy should update.
            # You might not need setRootIndex again here unless the root index itself becomes invalid.
            # Re-evaluate if this refresh method causes issues with the proxy.
        else:
             logger.debug(f"Ignoring directory change for non-root path: {path}")

    def item_double_clicked(self, index: QModelIndex):
        """Handles double-click: opens files, expands/collapses folders."""
        # --- index is from the PROXY model ---
        if not index.isValid():
            return

        # --- Map proxy index to source index to get file info ---
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid():
             logger.warning("Double click on invalid source index after mapping.")
             return

        file_path = self.source_model.filePath(source_index)
        if self.source_model.isDir(source_index):
            # Expand/collapse on double click (use proxy index for view state)
            if self.isExpanded(index):
                self.collapse(index)
            else:
                self.expand(index)
        else: # It's a file
            logger.debug(f"File double-clicked: {file_path}")
            self.file_selected.emit(file_path)

    def _update_delete_action_state(self):
        """Enables/disables the delete action based on selection."""
        selected_indexes = self.selectionModel().selectedIndexes()
        has_selection = bool(selected_indexes)
        can_delete = has_selection

        # Prevent deleting the root item itself
        if has_selection:
            # Check if any selected index maps to the root path in the source model
            root_source_index = self.source_model.index(self.current_root_path)
            for index in selected_indexes:
                source_index = self.proxy_model.mapToSource(index)
                if source_index == root_source_index:
                    can_delete = False
                    break
                # Optional: Add check for settings.json in guided mode here if needed?
                # filePath = self.source_model.filePath(source_index)
                # if self.project_mode == "guided" and os.path.basename(filePath).lower() == "settings.json":
                #    can_delete = False; break

        self.delete_action.setEnabled(can_delete)

    @pyqtSlot()
    def delete_selected_items(self):
        """Deletes all currently selected valid items after confirmation."""
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        paths_to_delete = set()  # Use a set to store unique paths
        source_root_index = self.source_model.index(self.current_root_path)
        forbidden_items = []  # Items that cannot be deleted

        for index in selected_indexes:
            if index.column() == 0:  # Process only one index per row
                source_index = self.proxy_model.mapToSource(index)
                if source_index.isValid():
                    # Check if it's the root item
                    if source_index == source_root_index:
                        QMessageBox.warning(self, "Cannot Delete Root", "The project root folder cannot be deleted.")
                        return

                    file_path = self.source_model.filePath(source_index)
                    base_name = os.path.basename(file_path)

                    # Check for protected items (e.g., settings.json in guided mode)
                    if self.project_mode == "guided" and base_name.lower() == "settings.json":
                        forbidden_items.append(base_name)
                        continue  # Skip this item

                    paths_to_delete.add(file_path)  # Add valid path to the set

        if forbidden_items:
            QMessageBox.warning(self, "Deletion Restricted",
                                f"The following items cannot be deleted in Guided Mode:\n - {', '.join(forbidden_items)}")
            return

        if not paths_to_delete:
            logger.info("No valid items selected for deletion.")
            return  # Nothing valid to delete

        # --- Confirmation Dialog ---
        count = len(paths_to_delete)
        item_text = f"{count} item" if count == 1 else f"{count} items"
        reply = QMessageBox.question(
            self,
            f"Confirm Delete",  # Dialog Title
            f"Are you sure you want to permanently delete the selected {item_text}?\n"
            f"(Folders and their contents will be deleted recursively)",  # Dialog Text
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,  # Buttons to show
            # --- CHANGE DEFAULT BUTTON HERE ---
            QMessageBox.StandardButton.Yes  # Default button is now Yes
            # --- END CHANGE ---
        )

        if reply != QMessageBox.StandardButton.Yes:
            logger.info(f"Deletion of {count} items cancelled by user.")
            return

        # --- Perform Deletion ---
        errors = []
        logger.info(f"Attempting to delete items: {paths_to_delete}")
        for path in paths_to_delete:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    logger.info(f"Folder deleted: {path}")
                elif os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"File deleted: {path}")
                else:
                    logger.warning(f"Item no longer exists or is not file/dir: {path}")
                    continue

                self.item_deleted.emit(path)

            except OSError as e:
                logger.error(f"OSError deleting item {path}: {e}", exc_info=True)
                errors.append(f"{os.path.basename(path)}: {e.strerror}")
            except Exception as e:
                logger.error(f"Unexpected error deleting item {path}: {e}", exc_info=True)
                errors.append(f"{os.path.basename(path)}: Unexpected error")

        if errors:
            error_list_str = '\n - '.join(errors)
            QMessageBox.critical(self, "Deletion Errors",
                                 f"Failed to delete the following items:\n - {error_list_str}")  # Use pre-formatted string

    def show_context_menu(self, position):
        """Displays the context menu based on selection and project mode."""
        logger.debug(f"Showing context menu at position: {position}")
        index = self.indexAt(position)  # Proxy index from the view
        selected_path = ""
        parent_dir = self.current_root_path  # Default parent is the root
        is_selection = index.isValid()
        is_dir = False
        source_index = QModelIndex()  # Default invalid source index

        if is_selection:
            # Map proxy index to source index to get real file info
            source_index = self.proxy_model.mapToSource(index)
            if source_index.isValid():
                selected_path = self.source_model.filePath(source_index)
                is_dir = self.source_model.isDir(source_index)
                parent_dir = selected_path if is_dir else os.path.dirname(selected_path)
                logger.debug(f"Valid selection: path={selected_path}, is_dir={is_dir}")
            else:
                logger.warning("Invalid source index after mapping proxy index")
                is_selection = False
                parent_dir = self.current_root_path
        else:
            logger.debug("No selection, using root path as parent")
            parent_dir = self.current_root_path

        menu = QMenu(self)
        current_mode = self.project_mode
        can_create = QDir(parent_dir).exists()

        # Creation Actions
        if current_mode == "guided":
            action_new_page = QAction(QIcon(self.theme_manager.get_icon("new_page")), "New Page...", self)
            action_new_page.triggered.connect(self._handle_context_new_page)
            action_new_page.setEnabled(can_create and (not is_selection or selected_path == self.current_root_path))
            menu.addAction(action_new_page)
        else:
            action_new_file = QAction(QIcon(self.theme_manager.get_icon("new_file")), "New File...", self)
            action_new_file.triggered.connect(lambda: self.create_item(parent_dir, is_file=True))
            action_new_file.setEnabled(can_create)
            menu.addAction(action_new_file)

            action_new_folder = QAction(QIcon(self.theme_manager.get_icon("new_folder_context")), "New Folder...", self)
            action_new_folder.triggered.connect(lambda: self.create_item(parent_dir, is_file=False))
            action_new_folder.setEnabled(can_create)
            menu.addAction(action_new_folder)

        # Modification Actions
        if is_selection:
            menu.addSeparator()

            # Rename Action
            action_rename = QAction(QIcon(self.theme_manager.get_icon("rename")), "Rename", self)
            action_rename.triggered.connect(
                lambda checked=False: self.rename_item(index)
            )
            action_rename.setEnabled(selected_path != self.current_root_path)
            logger.debug(f"Adding rename action, enabled={action_rename.isEnabled()}, path={selected_path}")
            menu.addAction(action_rename)

            # Delete Action
            menu.addAction(self.delete_action)

        logger.debug("Executing context menu")
        menu.exec(self.viewport().mapToGlobal(position))

    # --- NEW: Handler for context menu 'New Page' action ---
    def _handle_context_new_page(self):
        """Prompts for page name and EMITS a signal for the controller."""
        page_name_raw, ok = QInputDialog.getText(
            self, "Create New Guided Page", "Enter page name:", QLineEdit.EchoMode.Normal
        )
        if ok and page_name_raw:
            logger.info(f"Context menu requesting guided page: {page_name_raw}")
            # --- EMIT SIGNAL instead of calling controller ---
            self.guided_page_creation_requested.emit(page_name_raw.strip())
            # --------------------------------------------------
            # (FileExplorer no longer needs to emit file_selected here)
        else:
            logger.debug("User cancelled context menu new page creation.")

        # --- NEW SLOT: Handle model directory updates ---
        def _on_directory_loaded(self, path):
            """Checks if a pending item edit can be triggered."""
            # Check if the loaded directory is the parent of the item we just created
            if self._pending_edit_path and os.path.normpath(path) == os.path.normpath(
                    os.path.dirname(self._pending_edit_path)):
                logger.debug(f"Directory '{path}' loaded, attempting to find and edit '{self._pending_edit_path}'")
                source_index = self.source_model.index(self._pending_edit_path)
                if source_index.isValid():
                    proxy_index = self.proxy_model.mapFromSource(source_index)
                    if proxy_index.isValid():
                        logger.info(f"Triggering inline edit for: {self._pending_edit_path}")
                        # Clear the pending path BEFORE starting edit, to prevent re-triggering
                        self._pending_edit_path = None
                        # Scroll to ensure item is visible before editing
                        self.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)
                        # Start editing the item's name
                        self.edit(proxy_index)
                    else:
                        logger.warning(f"Could not map source index to proxy for editing: {self._pending_edit_path}")
                        self._pending_edit_path = None  # Clear anyway
                else:
                    logger.warning(
                        f"Could not find source index for editing after directory load: {self._pending_edit_path}")
                    # Don't clear pending path yet, maybe model needs more time? Or it failed.
                    # Consider adding a small timer fallback here if needed, but try without first.
            # else:
            #     logger.debug(f"Directory loaded '{path}', but not relevant for pending edit ('{self._pending_edit_path}').")

    def create_item(self, parent_dir: str, is_file: bool):
        """
        Creates a new file or folder with a default name in Free Mode
        and immediately starts inline renaming.
        """
        if self.project_mode != "free":
            logger.warning("create_item called but not in free mode. Ignoring.")
            return  # Should only be called in free mode context

        item_type = "file" if is_file else "folder"
        base_name = "Untitled File" if is_file else "New Folder"
        suffix = ".txt" if is_file else ""

        # Find unique default name
        counter = 0
        if not os.path.isdir(parent_dir):
            logger.error(f"Cannot create item: Parent directory '{parent_dir}' does not exist.")
            QMessageBox.warning(self, "Error", f"Cannot create item in '{parent_dir}'. Directory not found.")
            return

        new_name = f"{base_name}{suffix}"
        new_path = os.path.join(parent_dir, new_name)

        while os.path.exists(new_path):
            counter += 1
            new_name = f"{base_name} ({counter}){suffix}"
            new_path = os.path.join(parent_dir, new_name)
            if counter > 999:
                logger.error(f"Could not find a unique name for {base_name} in {parent_dir} after 999 attempts.")
                QMessageBox.warning(self, "Error", f"Could not find a unique name for '{base_name}'.")
                return

        logger.info(f"Attempting to create {item_type} with default name: {new_path}")

        try:
            # Create the item
            if is_file:
                with open(new_path, "w", encoding='utf-8') as f:
                    pass
                logger.info(f"Empty file created: {new_path}")
            else:
                os.makedirs(new_path)
                logger.info(f"Folder created: {new_path}")

            # Find the new item’s index
            source_index = self.source_model.index(new_path)
            if not source_index.isValid():
                logger.error(f"Failed to find source index for new item: {new_path}")
                QMessageBox.warning(self, "Error", f"Could not select new item '{new_name}' for renaming.")
                return

            proxy_index = self.proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                logger.error(f"Failed to map source index to proxy for new item: {new_path}")
                QMessageBox.warning(self, "Error", f"Could not select new item '{new_name}' for renaming.")
                return

            # Ensure the parent directory is expanded
            source_parent_index = self.source_model.index(parent_dir)
            if source_parent_index.isValid():
                proxy_parent_index = self.proxy_model.mapFromSource(source_parent_index)
                if proxy_parent_index.isValid():
                    self.expand(proxy_parent_index)
                    logger.debug(f"Expanded parent directory: {parent_dir}")

            # Select and start editing
            logger.debug(f"Selecting and editing new item: {new_path}")
            self.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)
            self.setCurrentIndex(proxy_index)
            self.selectionModel().select(proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

            # Set focus
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            QApplication.processEvents()

            # Log state
            logger.debug(f"View state for new item: hasFocus={self.hasFocus()}, "
                         f"isVisible={self.isVisible()}, selected={self.currentIndex() == proxy_index}")

            # Trigger editing
            logger.info(f"Starting rename for new item: {new_path}")
            success = self.edit(proxy_index)
            logger.debug(f"edit() returned: {success}")

            if not success:
                logger.warning("Direct edit() failed, trying F2 simulation")
                key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
                QApplication.postEvent(self, key_event)
                logger.debug("Posted F2 key event")

        except OSError as e:
            logger.error(f"OSError creating {item_type} at {new_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error Creating Item", f"Failed to create {item_type}:\n{e}")
        except Exception as e:
            logger.error(f"Unexpected error creating {item_type} at {new_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error Creating Item", f"An unexpected error occurred:\n{e}")

    def rename_item(self, proxy_index: QModelIndex):
        """Initiates inline renaming for the selected file or folder in the tree view."""
        logger.debug(
            f"rename_item called with proxy_index: row={proxy_index.row()}, column={proxy_index.column()}, valid={proxy_index.isValid()}")

        try:
            if not proxy_index.isValid():
                logger.warning("Inline rename cancelled: Invalid proxy index")
                QMessageBox.warning(self, "Cannot Rename", "No valid item selected.")
                return

            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                logger.error("Cannot rename: Invalid source index after mapping")
                QMessageBox.critical(self, "Rename Error", "Could not locate the item to rename.")
                return

            old_path = self.source_model.filePath(source_index)
            old_path = os.path.normpath(old_path)
            logger.debug(f"Item to rename: path={old_path}")

            if old_path == self.current_root_path:
                logger.warning("Inline rename cancelled: Attempted to rename root path")
                QMessageBox.warning(self, "Cannot Rename", "Cannot rename the project root folder.")
                return

            # Check proxy model flags
            proxy_flags = self.proxy_model.flags(proxy_index)
            logger.debug(f"Proxy model flags for {old_path}: {proxy_flags}")
            if not (proxy_flags & Qt.ItemFlag.ItemIsEditable):
                logger.warning(f"Item is not editable: {old_path}, proxy_flags={proxy_flags}")
                QMessageBox.warning(self, "Cannot Rename", "This item cannot be renamed.")
                return

            # Check filesystem permissions
            is_writable = os.access(old_path, os.W_OK)
            logger.debug(f"Filesystem writable: {is_writable} for {old_path}")
            if not is_writable:
                logger.warning(f"Cannot rename: {old_path} is read-only on filesystem")
                QMessageBox.warning(self, "Cannot Rename", f"The item '{os.path.basename(old_path)}' is read-only.")
                return

            # Prepare view
            logger.debug(f"Preparing view for editing: {old_path}")
            self.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)
            self.setCurrentIndex(proxy_index)
            self.selectionModel().select(proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

            # Set focus
            logger.debug("Setting focus on QTreeView")
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            QApplication.processEvents()

            # Log state
            logger.debug(f"View state: hasFocus={self.hasFocus()}, isVisible={self.isVisible()}, "
                         f"selected={self.currentIndex() == proxy_index}, "
                         f"focusWidget={QApplication.focusWidget()}")

            # Try direct edit
            logger.info(f"Attempting edit() for: {old_path}")
            success = self.edit(proxy_index)
            logger.debug(f"edit() returned: {success}")

            if not success:
                logger.warning("Direct edit() failed, trying F2 simulation")
                # Fallback: Simulate F2 key press
                key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
                QApplication.postEvent(self, key_event)
                logger.debug("Posted F2 key event")
                return

            logger.info("Inline editing started successfully")

        except Exception as e:
            logger.error(f"Unexpected error in rename_item: {e}", exc_info=True)
            QMessageBox.critical(self, "Rename Error", f"An unexpected error occurred: {e}")

    def _handle_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list):
        """Handles data changes in the source model, e.g., renames."""
        if not top_left.isValid() or top_left != bottom_right:
            return  # We only care about single-item changes

        if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.EditRole in roles:
            # This indicates a possible rename (name changed)
            new_path = self.source_model.filePath(top_left)
            new_path = os.path.normpath(new_path)

            # To get the old path, we rely on the fact that the index's parent and row
            # can help us deduce the old name. However, QFileSystemModel doesn't store
            # the old path directly, so we may need to track it if critical.
            # For simplicity, assume the rename just happened and emit the signal.
            logger.debug(f"Data changed for path: {new_path}")

            # Since we don't have the old path easily, we can emit the new path and let
            # downstream components handle it. If old_path is critical, you'd need to
            # track pending renames (e.g., in a dict mapping indexes to old paths).
            # For now, emit with new_path as both arguments if old_path isn't tracked.
            self.item_renamed.emit(new_path, new_path)

            # Optional: If you need the old path, you might need to:
            # 1. Store the old path when edit() is called (e.g., in a temp variable).
            # 2. Match it here when dataChanged fires.
            # Example approach (if needed):
            """
            if hasattr(self, '_pending_rename_path') and self._pending_rename_path:
                old_path = self._pending_rename_path
                self._pending_rename_path = None
                if old_path != new_path:
                    logger.info(f"Emitting item_renamed: '{old_path}' -> '{new_path}'")
                    self.item_renamed.emit(old_path, new_path)
            """

    def delete_item(self, path_to_delete: str):
        """Deletes the selected file or folder (with confirmation)."""
        path_to_delete = os.path.normpath(path_to_delete)
        if (not path_to_delete or not os.path.exists(path_to_delete)
             or path_to_delete == self.current_root_path): # Prevent deleting root
             logger.warning("Delete cancelled: Invalid, non-existent, or root path selected.")
             return

        is_dir = os.path.isdir(path_to_delete)
        item_type = "folder" if is_dir else "file"
        item_name = os.path.basename(path_to_delete)

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            f"Confirm Delete",
            f"Are you sure you want to permanently delete the {item_type} '{item_name}'?\n"
            f"{'(and all its contents)' if is_dir else ''}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel, # Default to Cancel
        )

        if reply != QMessageBox.StandardButton.Yes:
            logger.info(f"Delete cancelled by user for: {path_to_delete}")
            return

        logger.info(f"Attempting to delete {item_type}: {path_to_delete}")
        try:
            if is_dir:
                shutil.rmtree(path_to_delete) # Use shutil for robust directory removal
                logger.info(f"Folder deleted: {path_to_delete}")
            else:
                os.remove(path_to_delete)
                logger.info(f"File deleted: {path_to_delete}")

            # Emit signal so editor tabs can be closed
            self.item_deleted.emit(path_to_delete)

            # Refresh view
            # self._refresh_current_directory(self.current_root_path)

        except OSError as e:
            logger.error(f"OSError deleting {item_type} {path_to_delete}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to delete {item_type}:\n{e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting {item_type} {path_to_delete}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred:\n{e}")