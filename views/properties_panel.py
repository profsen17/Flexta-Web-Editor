# website_builder/views/properties_panel.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFormLayout, QLabel, QLineEdit, QScrollArea,
                           QVBoxLayout, QWidget, QComboBox, QSpinBox, QPushButton)
import logging

logger = logging.getLogger(__name__)

class PropertiesPanel(QWidget):
    """
    A panel to display and edit properties of the currently selected
    element (e.g., from the Visual Designer or potentially code analysis).
    Currently a placeholder, needs connection to selection mechanism.
    """
    # Signal to emit when a property value changes (e.g., property_name, new_value, element_id)
    # property_changed = pyqtSignal(str, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.scroll_area)

        # Content widget inside scroll area
        self.content_widget = QWidget()
        self.scroll_area.setWidget(self.content_widget)

        # Layout for the content widget (aligns form to top)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Form layout to hold property label-editor pairs
        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(10, 10, 10, 10) # Add padding
        self.form_layout.setSpacing(10) # Spacing between rows
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight) # Align labels to the right
        self.content_layout.addLayout(self.form_layout)

        # Placeholder label shown when nothing is selected
        self.placeholder_label = QLabel("(Select an element to edit its properties)")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888; padding: 20px;")
        self.content_layout.addWidget(self.placeholder_label)

        self.current_element_id = None # Store ID of element being edited

    def show_properties(self, element_data: dict, element_id: str = None):
        """
        Populates the panel with editors based on the provided element data.
        'element_data' should be a dictionary like {'property_name': value, ...}
        'element_id' is an optional identifier for the element being edited.
        """
        logger.debug(f"Showing properties for element ID: {element_id} Data: {element_data}")
        self.clear_panel() # Clear previous properties first
        self.current_element_id = element_id

        if not element_data:
            self.placeholder_label.show()
            return

        self.placeholder_label.hide()

        # Example: Populate based on a dictionary
        # In a real implementation, this would involve creating specific widgets
        # based on the property type (string, number, color, enum, boolean, etc.)
        for key, value in element_data.items():
            # TODO: Determine appropriate editor widget based on key/value type
            # Example basic editors:
            if isinstance(value, bool):
                 editor = QComboBox()
                 editor.addItems(["True", "False"])
                 editor.setCurrentText(str(value))
                 # editor.currentTextChanged.connect(lambda text, k=key: self._emit_change(k, text == "True"))
            elif isinstance(value, (int, float)):
                 editor = QSpinBox() if isinstance(value, int) else QLineEdit(str(value)) # QDoubleSpinBox for float?
                 if isinstance(value, int):
                     editor.setRange(-10000, 10000) # Example range
                     editor.setValue(value)
                     # editor.valueChanged.connect(lambda val, k=key: self._emit_change(k, val))
                 else: # Float handled as text for now
                      # Add validation for numeric input later
                      pass
            else: # Treat as string default
                 editor = QLineEdit(str(value))
                 # editor.editingFinished.connect(lambda e=editor, k=key: self._emit_change(k, e.text()))

            self.form_layout.addRow(f"{key.replace('_', ' ').capitalize()}:", editor)
            # TODO: Connect the 'change' signal of the created editor widget
            #       to a slot (_emit_change) that emits the property_changed signal.

    def _emit_change(self, property_name: str, new_value):
        """Slot to handle property changes and emit the signal."""
        logger.debug(f"Property '{property_name}' changed to '{new_value}' for element {self.current_element_id}")
        # self.property_changed.emit(property_name, new_value, self.current_element_id)
        # TODO: Implement actual signal emission and connection in controller/visual designer


    def clear_panel(self):
        """Clears all dynamically added rows from the form layout."""
        self.current_element_id = None
        while self.form_layout.count():
            # QFormLayout items are pairs (label, field) or spanning widgets
            item = self.form_layout.takeAt(0)
            if item:
                 widget = item.widget()
                 if widget:
                     widget.deleteLater()
                 else:
                     # If the item is a layout, clear it recursively (though unlikely in simple form)
                     child_layout = item.layout()
                     if child_layout:
                         self._clear_layout_recursive(child_layout)
        self.placeholder_label.show() # Show placeholder after clearing


    def _clear_layout_recursive(self, layout):
        """Helper to recursively clear widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    child_layout = item.layout()
                    if child_layout is not None:
                        self._clear_layout_recursive(child_layout)