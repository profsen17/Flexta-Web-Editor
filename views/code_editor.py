# website_builder/views/code_editor.py
import os
import logging # Use logging instead of prints for internal info
from typing import Optional, Tuple

from PyQt6.QtCore import QFileSystemWatcher, QRegularExpression, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# --- Enhanced Syntax Highlighter ---
class EnhancedHtmlCssJsHighlighter(QSyntaxHighlighter):
    """Basic syntax highlighter for HTML, CSS, and JavaScript."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        # Define comment expressions for multi-line handling
        self.commentStartExpression = QRegularExpression("/\\*")
        self.commentEndExpression = QRegularExpression("\\*/")
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor(128, 128, 128)) # Gray
        self.multiLineCommentFormat.setFontItalic(True)

        # --- Common Formats ---
        def create_format(color: QColor, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        # --- HTML ---
        htmlKeywordFormat = create_format(QColor(0, 0, 128), bold=True) # Dark Blue
        htmlKeywords = [
            "html", "head", "body", "title", "div", "span", "p", "a", "img", "ul", "ol", "li",
            "table", "tr", "td", "th", "form", "input", "button", "textarea", "select",
            "option", "meta", "link", "style", "script", "header", "footer", "nav",
            "article", "section", "aside", "main", "figure", "figcaption"
        ]
        # Match opening and closing tags
        for word in htmlKeywords:
            try:
                # Opening tag start (<tag) or self-closing (<tag />)
                pattern_open = QRegularExpression(f"<\\s*{word}(\\b|(?=\\s|/?>))", QRegularExpression.PatternOption.CaseInsensitiveOption)
                self.highlightingRules.append((pattern_open, htmlKeywordFormat))
                # Closing tag (</tag>)
                pattern_close = QRegularExpression(f"</\\s*{word}\\s*>", QRegularExpression.PatternOption.CaseInsensitiveOption)
                self.highlightingRules.append((pattern_close, htmlKeywordFormat))
            except Exception as e:
                logger.error(f"Error creating HTML regex for '{word}': {e}")

        htmlAttributeFormat = create_format(QColor(128, 0, 0)) # Dark Red
        self.highlightingRules.append((QRegularExpression("\\b[a-zA-Z\\-:]+(?=\\s*=)"), htmlAttributeFormat))

        htmlTagBracketFormat = create_format(QColor(128, 128, 128), bold=False) # Gray brackets
        self.highlightingRules.append((QRegularExpression("[<>/]"), htmlTagBracketFormat)) # Highlight <, >, /

        # --- CSS (Simplified - doesn't handle nested structures perfectly) ---
        cssSelectorFormat = create_format(QColor(128, 0, 128)) # Purple
        # Matches common selectors (element, class, id, attributes) at line start or after }
        self.highlightingRules.append((QRegularExpression("(^\\s*|}\\s*)([\\w\\.#\\-\\*\\[\\]=:\"]+)(?=\\s*\\{)"), cssSelectorFormat))

        cssPropertyFormat = create_format(QColor(0, 128, 0)) # Dark Green
        self.highlightingRules.append((QRegularExpression("\\b([a-z\\-]+)(?=\\s*:)"), cssPropertyFormat))

        cssValueFormat = create_format(QColor(0, 0, 200)) # Blue values
        # Matches content between : and ; or }
        self.highlightingRules.append((QRegularExpression(":\\s*([^;\\}]+)(?=[;\\}])"), cssValueFormat))

        # --- JavaScript (Basic Keywords and Built-ins) ---
        jsKeywordFormat = create_format(QColor(170, 120, 100), bold=True) # Darker red
        jsKeywords = [
            "function", "var", "let", "const", "if", "else", "for", "while", "return", "class",
            "import", "export", "from", "new", "this", "super", "try", "catch", "finally",
            "throw", "async", "await", "switch", "case", "default", "break", "continue",
            "do", "delete", "in", "instanceof", "typeof", "void", "yield"
        ]
        for word in jsKeywords:
            try:
                pattern = QRegularExpression(f"\\b{word}\\b")
                self.highlightingRules.append((pattern, jsKeywordFormat))
            except Exception as e:
                logger.error(f"Error creating JS keyword regex for '{word}': {e}")

        jsBuiltinFormat = create_format(QColor(100, 100, 200)) # Lighter blue/purple
        jsBuiltins = [
            "document", "window", "console", "alert", "prompt", "confirm", "parseInt",
            "parseFloat", "String", "Number", "Boolean", "Object", "Array", "Date",
            "Math", "JSON", "RegExp", "Error", "setTimeout", "setInterval",
            "clearTimeout", "clearInterval", "isNaN", "isFinite", "encodeURI",
            "decodeURI", "encodeURIComponent", "decodeURIComponent", "Promise", "Map", "Set",
            "Symbol", "Proxy", "Reflect", "fetch"
        ]
        for word in jsBuiltins:
            try:
                pattern = QRegularExpression(f"\\b{word}\\b")
                self.highlightingRules.append((pattern, jsBuiltinFormat))
            except Exception as e:
                logger.error(f"Error creating JS builtin regex for '{word}': {e}")

        # --- Common ---
        commentFormat = create_format(QColor(128, 128, 128), italic=True) # Gray
        self.highlightingRules.append((QRegularExpression("//[^\n]*"), commentFormat))
        # Removed multi-line comment regex here, handled by block state logic below

        stringFormat = create_format(QColor(0, 150, 0)) # Green strings
        self.highlightingRules.append((QRegularExpression("\".*?\""), stringFormat))
        self.highlightingRules.append((QRegularExpression("'.*?'"), stringFormat))
        self.highlightingRules.append((QRegularExpression("`.*?`"), stringFormat)) # Template literals

        numberFormat = create_format(QColor(200, 100, 0)) # Orange numbers
        self.highlightingRules.append((QRegularExpression("\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b"), numberFormat))

    def highlightBlock(self, text):
        # Apply single-line rules first
        for pattern, format_rule in self.highlightingRules:
            try:
                match_iterator = pattern.globalMatch(text)
                while match_iterator.hasNext():
                    match = match_iterator.next()
                    start = match.capturedStart()
                    length = match.capturedLength()
                    # Check if inside a multi-line comment before applying format
                    if not self.is_inside_multiline_comment(start):
                        self.setFormat(start, length, format_rule)
            except Exception as e:
                 logger.error(f"Error in highlighter match processing: {e} with pattern {pattern.pattern()}")

        # Handle multi-line comments using block state
        self.setCurrentBlockState(0) # Default state: not in comment

        startIndex = 0
        # If previous block ended inside a comment, start searching from beginning
        if self.previousBlockState() == 1:
            startIndex = 0
        else: # Otherwise, find the first /* in this block
            match = self.commentStartExpression.match(text)
            startIndex = match.capturedStart() if match.hasMatch() else -1

        while startIndex >= 0:
            # Find the end of the comment */
            endMatch = self.commentEndExpression.match(text, startIndex + 2) # Start searching after /*
            endIndex = endMatch.capturedStart()
            commentLength = 0

            if endIndex == -1: # Comment doesn't end in this block
                self.setCurrentBlockState(1) # Mark block state as inside comment
                commentLength = len(text) - startIndex
            else: # Comment ends in this block
                commentLength = endIndex - startIndex + endMatch.capturedLength()

            # Apply the comment format
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)

            # Find the next /* starting after the current comment ends
            match = self.commentStartExpression.match(text, startIndex + commentLength)
            startIndex = match.capturedStart() if match.hasMatch() else -1

    def is_inside_multiline_comment(self, position: int) -> bool:
        """Helper to check if a position is within a formatted multi-line comment."""
        # This requires checking the format at the position, which is tricky
        # as formats are applied sequentially. The block state method is more robust.
        # For simplicity, this helper might not be perfectly accurate if other rules
        # overwrite the comment format partially. Rely primarily on the block state logic.
        # A simple check (might be inaccurate):
        # current_format = self.format(position)
        # return current_format == self.multiLineCommentFormat
        return self.currentBlockState() == 1 # Rely on block state


# --- Code Editor Widget ---
class CodeEditorTabWidget(QWidget):
    content_changed = pyqtSignal(str, str)  # file_path, content
    tab_closed_signal = pyqtSignal(str)  # file_path (emitted AFTER tab is removed)
    modification_changed = pyqtSignal(str, bool) # file_path, modified_status

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.layout.addWidget(self.tab_widget)

        self.open_files = {}  # Dictionary: file_path -> QPlainTextEdit widget
        self.file_watchers = {}  # Dictionary: file_path -> QFileSystemWatcher

    def open_file(self, file_path: str):
        """Opens a file in a new tab or switches to it if already open."""
        # Normalize path separators for consistent keys
        file_path = os.path.normpath(file_path)
        logger.info(f"Request to open file: {file_path}")

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"The file does not exist:\n{file_path}")
            logger.warning(f"Attempted to open non-existent file: {file_path}")
            return

        if file_path in self.open_files:
            editor_widget = self.open_files[file_path]
            tab_index = self.tab_widget.indexOf(editor_widget.parentWidget())
            logger.debug(f"File already open, switching to tab index: {tab_index}")
            if tab_index != -1:
                self.tab_widget.setCurrentIndex(tab_index)
            return

        try:
            # Try reading with UTF-8, fallback to latin-1
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for {file_path}, trying latin-1.")
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            logger.info(f"Successfully read file: {file_path}")

            editor = QPlainTextEdit()
            editor.setFont(QFont("Courier New", 11)) # Consider making font configurable
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap) # Optional: QPlainTextEdit.LineWrapMode.WidgetWidth

            # Block signals during initial setup
            editor.blockSignals(True)
            editor.setPlainText(content)
            editor.document().setModified(False) # Reset modified state after loading
            editor.blockSignals(False)

            # Apply highlighter based on file extension
            # TODO: Make highlighter selection more robust (e.g., based on mime types or config)
            if file_path.lower().endswith((".html", ".htm", ".css", ".js")):
                try:
                    highlighter = EnhancedHtmlCssJsHighlighter(editor.document())
                    logger.debug(f"Applied syntax highlighter for: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to apply highlighter for {file_path}: {e}")


            editor.setProperty("file_path", file_path)
            # Connect modificationChanged signal to handle '*' in tab text
            editor.modificationChanged.connect(
                lambda modified, fp=file_path: self._on_modification_changed(fp, modified)
            )
            # Connect textChanged to potentially trigger external updates (like preview)
            editor.textChanged.connect(lambda fp=file_path: self._on_text_changed(fp))


            # Place editor inside a container widget for the tab
            editor_container = QWidget()
            container_layout = QVBoxLayout(editor_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(editor)

            tab_index = self.tab_widget.addTab(editor_container, os.path.basename(file_path))
            self.tab_widget.setTabToolTip(tab_index, file_path) # Show full path in tooltip
            self.tab_widget.setCurrentIndex(tab_index)
            logger.info(f"Added tab at index {tab_index} for: {file_path}")

            self.open_files[file_path] = editor
            self._watch_file(file_path)

            # Initial saved status is false (not modified since opening)
            self.set_tab_saved_status(file_path, True) # True means 'not modified *'

        except Exception as e:
            logger.error(f"Error opening file {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error Opening File",
                f"Could not open file: {file_path}\n\n{e}"
            )

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Reads file content, trying UTF-8 then Latin-1."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except Exception as e_fallback:
                logger.error(f"Encoding fallback failed for {file_path}: {e_fallback}")
                return None
        except Exception as e:
            logger.error(f"Error reading file content for {file_path}: {e}")
            return None

    def _watch_file(self, file_path):
        """Starts watching a file for external changes."""
        if file_path not in self.file_watchers:
            watcher = QFileSystemWatcher([file_path], self)
            watcher.fileChanged.connect(self.handle_external_change)
            self.file_watchers[file_path] = watcher
            logger.debug(f"Started watching file: {file_path}")

    def _unwatch_file(self, file_path):
        """Stops watching a file."""
        watcher = self.file_watchers.pop(file_path, None)
        if watcher:
            watcher.removePath(file_path)
            watcher.fileChanged.disconnect(self.handle_external_change)
            watcher.deleteLater() # Schedule watcher for deletion
            logger.debug(f"Stopped watching file: {file_path}")

    def handle_external_change(self, file_path: str):
        """Handles notification that a file was changed outside the editor."""
        file_path = os.path.normpath(file_path)
        logger.info(f"External change detected for: {file_path}")

        if file_path not in self.open_files:
            logger.warning(f"Received external change for non-open file: {file_path}, unwatching.")
            self._unwatch_file(file_path) # Clean up watcher if file was closed unexpectedly
            return

        editor = self.open_files.get(file_path)
        if not editor:
            return # Should not happen if file_path is in open_files

        # Read disk content *carefully*, handle potential read errors
        disk_content = self._read_file_content(file_path)
        if disk_content is None:
             logger.error(f"Could not read disk content for {file_path} after external change.")
             # Optionally inform user?
             return

        # Compare with editor content
        editor_content = editor.toPlainText()

        # If content matches, maybe the save operation triggered the watcher. Ignore.
        # Be careful with line endings or minor whitespace diffs if needed.
        if disk_content == editor_content:
            logger.debug(f"Ignoring external change; content matches editor: {file_path}")
            # Ensure the modified status is correct (it should be 'saved' if content matches)
            if editor.document().isModified():
                editor.document().setModified(False)
            return

        # If editor has unsaved changes, ask user what to do.
        if editor.document().isModified():
             reply = QMessageBox.question(
                 self,
                 "File Conflict",
                 f"The file '{os.path.basename(file_path)}' has been modified both in the editor and externally.\n"
                 f"Do you want to overwrite your changes with the external version?",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, # Yes = Reload, No = Keep editor changes
                 QMessageBox.StandardButton.No,
             )
             should_reload = (reply == QMessageBox.StandardButton.Yes)
        else: # Editor has no unsaved changes, safer to just ask about reloading
             reply = QMessageBox.question(
                 self,
                 "File Changed Externally",
                 f"The file '{os.path.basename(file_path)}' has been modified outside the editor.\n"
                 f"Do you want to reload it?",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                 QMessageBox.StandardButton.Yes, # Default to reloading if no unsaved changes
             )
             should_reload = (reply == QMessageBox.StandardButton.Yes)


        if should_reload:
            try:
                logger.info(f"Reloading externally changed file: {file_path}")
                editor.blockSignals(True)
                # Preserve cursor roughly
                cursor_pos = editor.textCursor().position()
                editor.setPlainText(disk_content)
                editor.document().setModified(False) # Reloaded content is now 'saved' state
                # Restore cursor
                cursor = editor.textCursor()
                cursor.setPosition(min(cursor_pos, len(disk_content)))
                editor.setTextCursor(cursor)
                editor.blockSignals(False)
                # Emit modification changed *after* signals unblocked
                self.modification_changed.emit(file_path, False)
            except Exception as e:
                 logger.error(f"Error reloading file {file_path}: {e}", exc_info=True)
                 QMessageBox.warning(
                     self,
                     "Error Reloading File",
                     f"Could not reload file: {file_path}\n\n{e}",
                 )
        else:
             # User chose not to reload, mark the editor content as modified
             # since it now differs from the disk.
             logger.info(f"User chose not to reload: {file_path}. Marking as modified.")
             editor.document().setModified(True)
             # Emit modification changed
             self.modification_changed.emit(file_path, True)


    def _on_text_changed(self, file_path: str):
        """Slot connected to editor's textChanged signal."""
        if file_path in self.open_files:
            editor = self.open_files[file_path]
            # This signal fires frequently. Only emit our content_changed signal
            # if needed for live updates (e.g., preview).
            # The modification status is handled by modificationChanged.
            # logger.debug(f"textChanged triggered for: {file_path}")
            self.content_changed.emit(file_path, editor.toPlainText())


    def _on_modification_changed(self, file_path: str, modified: bool):
        """Slot connected to editor's modificationChanged signal."""
        # Update the tab text with '*'
        self.set_tab_saved_status(file_path, not modified)
        # Emit our own signal
        self.modification_changed.emit(file_path, modified)
        logger.debug(f"Modification status changed for {file_path}: {'Modified' if modified else 'Saved'}")


    def set_tab_saved_status(self, file_path: str, saved: bool):
        """Updates the tab text to include/exclude the '*' modified indicator."""
        if file_path in self.open_files:
            editor = self.open_files[file_path]
            tab_index = self.tab_widget.indexOf(editor.parentWidget())
            if tab_index != -1:
                base_name = os.path.basename(file_path)
                tab_text = base_name if saved else base_name + "*"
                self.tab_widget.setTabText(tab_index, tab_text)


    def get_current_editor_content(self) -> Tuple[Optional[str], Optional[str]]:
        """Returns the file path and content of the currently active editor tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index == -1:
            return None, None # No tab open

        editor_container = self.tab_widget.widget(current_index)
        if editor_container:
            # Find the QPlainTextEdit within the container
            editor = editor_container.findChild(QPlainTextEdit)
            if editor:
                file_path = editor.property("file_path")
                content = editor.toPlainText()
                return file_path, content
        return None, None


    def save_current_file(self) -> bool:
        """Saves the content of the currently active tab to its file."""
        file_path, content = self.get_current_editor_content()
        if file_path and content is not None:
             return self.save_file(file_path, content)
        logger.warning("save_current_file called but no active editor found.")
        return False


    def save_file(self, file_path: str, content: str) -> bool:
        """Saves the given content to the specified file path."""
        if not file_path:
             logger.error("save_file called with empty file path.")
             return False

        logger.info(f"Attempting to save file: {file_path}")
        # Temporarily stop watching file to prevent self-triggering change event
        watcher = self.file_watchers.get(file_path)
        if watcher:
             logger.debug(f"Temporarily blocking signals for watcher: {file_path}")
             watcher.blockSignals(True)
             # It might be safer to remove/re-add path if blocking isn't reliable across OS/Qt versions
             # watcher.removePath(file_path)

        success = False
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Successfully saved file: {file_path}")

            # Mark the corresponding editor as unmodified *after* successful save
            if file_path in self.open_files:
                editor = self.open_files[file_path]
                editor.document().setModified(False)
                # The modificationChanged signal will update the tab text

            success = True

        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error Saving File", f"Could not save file: {file_path}\n\n{e}"
            )
            success = False
        finally:
            # Re-enable watching
            if watcher:
                 # if watcher.files() == []: # If path was removed
                 #     watcher.addPath(file_path)
                 watcher.blockSignals(False)
                 logger.debug(f"Unblocked signals for watcher: {file_path}")

        return success

    def save_all_files(self) -> bool:
        """Saves all open files that have unsaved changes."""
        saved_count = 0
        error_count = 0
        all_successful = True
        logger.info("Attempting to save all modified files.")

        for file_path, editor in list(self.open_files.items()): # Iterate over copy in case of issues
             if editor.document().isModified():
                 logger.debug(f"Found modified file to save: {file_path}")
                 content = editor.toPlainText()
                 if self.save_file(file_path, content):
                     saved_count += 1
                 else:
                     error_count += 1
                     all_successful = False # Mark overall success as false if any save fails

        logger.info(f"Save All complete: {saved_count} files saved, {error_count} errors.")
        if error_count > 0:
             QMessageBox.warning(self, "Save All Issues", f"Could not save {error_count} files. Please check permissions or logs.")
        return all_successful

    def close_tab(self, index: int):
        """Handles the request to close a tab, prompting for unsaved changes."""
        editor_container = self.tab_widget.widget(index)
        if not editor_container:
             logger.error(f"Attempted to close tab at invalid index: {index}")
             return

        editor = editor_container.findChild(QPlainTextEdit)
        if not editor:
             logger.error(f"Could not find editor widget in tab index: {index}")
             self.tab_widget.removeTab(index) # Remove tab anyway if structure is broken
             return

        file_path = editor.property("file_path")
        base_name = os.path.basename(file_path) if file_path else "Untitled"

        proceed_with_close = True
        if editor.document().isModified():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Do you want to save the changes to '{base_name}' before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save, # Default to Save
            )

            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file(file_path, editor.toPlainText()):
                    # Save failed, do not close the tab
                    proceed_with_close = False
            elif reply == QMessageBox.StandardButton.Cancel:
                proceed_with_close = False
            # If Discard, proceed_with_close remains True

        if proceed_with_close:
            logger.info(f"Closing tab for file: {file_path}")
            # Remove tab from widget
            self.tab_widget.removeTab(index)

            # Clean up resources
            self._unwatch_file(file_path)
            editor_widget = self.open_files.pop(file_path, None)

            if editor_widget:
                 # Disconnect signals manually? Might not be necessary if parent is deleted.
                 # try: editor_widget.modificationChanged.disconnect()
                 # except TypeError: pass
                 # try: editor_widget.textChanged.disconnect()
                 # except TypeError: pass
                 editor_widget.deleteLater() # Schedule editor for deletion
                 editor_container.deleteLater() # Schedule container for deletion

            self.tab_closed_signal.emit(file_path) # Notify controller


    def close_all_tabs(self):
        """Closes all open tabs, prompting for saves as needed."""
        logger.info("Closing all tabs.")
        # Iterate backwards as removing tabs changes indices
        while self.tab_widget.count() > 0:
             # close_tab handles prompts and actual removal.
             # If user cancels closing one tab, this loop will stop there.
             self.close_tab(self.tab_widget.count() - 1)
             # Add a check in case close_tab was cancelled
             if self.tab_widget.widget(self.tab_widget.count() -1):
                 # Tab wasn't closed (user cancelled), stop trying
                 logger.warning("Tab closing cancelled by user.")
                 break


    def update_content(self, file_path: str, new_content: str):
        """Programmatically updates the content of an open editor without marking it modified."""
        file_path = os.path.normpath(file_path)
        if file_path in self.open_files:
             editor = self.open_files[file_path]
             logger.debug(f"Programmatically updating content for: {file_path}")
             editor.blockSignals(True)
             current_cursor_pos = editor.textCursor().position()
             editor.setPlainText(new_content)
             # Restore cursor if possible
             cursor = editor.textCursor()
             cursor.setPosition(min(current_cursor_pos, len(new_content)))
             editor.setTextCursor(cursor)
             editor.document().setModified(False) # Assume programmatic update is 'saved' state
             editor.blockSignals(False)
             # Manually trigger modification change signal to update tab '*'
             self.modification_changed.emit(file_path, False)

    def has_unsaved_changes(self) -> bool:
        """Checks if any open tab has unsaved modifications."""
        for editor in self.open_files.values():
            if editor.document().isModified():
                return True
        return False