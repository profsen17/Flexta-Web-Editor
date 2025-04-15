# website_builder/views/project_file_proxy_model.py
import os
from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex, Qt
from PyQt6.QtGui import QFileSystemModel

class ProjectFileProxyModel(QSortFilterProxyModel):
    """
    A proxy model to filter files in the FileExplorer based on project mode.
    Specifically hides settings.json in guided mode.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_mode = "free"  # Default mode

    def set_project_mode(self, mode: str):
        """Sets the current project mode to control filtering."""
        if mode != self._project_mode:
            self._project_mode = mode
            self.invalidateFilter()  # Crucial: Tells the view to re-query the filter

    def project_mode(self) -> str:
        return self._project_mode

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """
        Determines whether a row from the source model should be shown.
        """
        source_model = self.sourceModel()
        if not isinstance(source_model, QFileSystemModel):
            # If source model isn't set or is wrong type, accept by default
            return super().filterAcceptsRow(source_row, source_parent)

        # Get the index for the row in the source model
        source_index = source_model.index(source_row, 0, source_parent)

        if not source_index.isValid():
            return False  # Should not happen but good practice

        # Check if in guided mode and if it's the settings.json file
        if self._project_mode == "guided":
            file_info = source_model.fileInfo(source_index)
            if not file_info.isDir() and file_info.fileName().lower() == "settings.json":
                return False  # Hide the row

        # If not filtered out, accept the row
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        source_index = self.mapToSource(index)
        source_model = self.sourceModel()
        if not isinstance(source_model, QFileSystemModel) or not source_index.isValid():
            return super().flags(index)
        source_flags = source_model.flags(source_index)
        return source_flags