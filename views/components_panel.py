# website_builder/views/components_panel.py
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QAbstractItemView
import json # For serializing data

class ComponentsPanel(QWidget):
    """
    A panel displaying available HTML components that can be dragged
    onto the visual designer canvas. (Drag functionality TBD)
    """
    def __init__(self, parent=None):
        print(f"--- Creating ComponentsPanel instance (Parent: {parent}) ---")
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # Add some margin

        self.list_widget = QListWidget()
        self.list_widget.setDragEnabled(True)
        # Set drag-only mode; dropping onto this list is not intended
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        # Optional: Use IconMode for visual appeal
        # self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        # self.list_widget.setIconSize(QSize(48, 48))
        # self.list_widget.setGridSize(QSize(70, 70))

        # Add components with data payload
        # The 'data' could be the HTML string, or a more structured representation
        # The 'type' helps the drop target understand what it's receiving
        self.add_component("Heading 1", {"html": "<h1>Heading 1</h1>", "tag": "h1"}, "html_component")
        self.add_component("Paragraph", {"html": "<p>Some text...</p>", "tag": "p"}, "html_component")
        self.add_component("Button", {"html": "<button>Click Me</button>", "tag": "button"}, "html_component")
        self.add_component("Image", {"html": "<img src='placeholder.png' alt='Image'>", "tag": "img"}, "html_component")
        self.add_component("Div Container", {"html": "<div>\n  \n</div>", "tag": "div"}, "html_component")
        self.add_component("Text Input", {"html": "<input type='text' placeholder='Text Input'>", "tag": "input"}, "html_component")
        # TODO: Add more components (Link, List, Table, Form elements etc.)

        layout.addWidget(self.list_widget)

        # Override mimeData generation for the list widget itself
        self.list_widget.mimeData = self._create_mime_data

    def add_component(self, name: str, data: dict, data_type: str):
        """Adds a component item to the list."""
        item = QListWidgetItem(name)
        # Store component data within the item
        item_data = {"data": data, "type": data_type}
        item.setData(Qt.ItemDataRole.UserRole, item_data)
        # TODO: Add relevant icons using item.setIcon(QIcon(...))
        self.list_widget.addItem(item)

    def _create_mime_data(self, items: list[QListWidgetItem]) -> QMimeData:
        """
        Custom function to create QMimeData for dragged component items.
        Called internally by QListWidget when a drag starts.
        """
        if not items:
            return QMimeData()

        mime_data = QMimeData()
        item = items[0] # Typically only one item is dragged
        component_info = item.data(Qt.ItemDataRole.UserRole)

        if component_info and isinstance(component_info, dict):
            # Define a custom MIME type
            mime_type = "application/x-websitebuilder-component"
            # Serialize the component info (e.g., to JSON)
            try:
                encoded_data = json.dumps(component_info).encode('utf-8')
                mime_data.setData(mime_type, encoded_data)
                # Also set plain text for external drop targets (optional)
                if isinstance(component_info.get("data"), dict):
                     html_snippet = component_info["data"].get("html", "")
                     if html_snippet:
                           mime_data.setText(html_snippet)
                           mime_data.setHtml(html_snippet) # For targets accepting HTML
                print(f"Dragging: {component_info}") # Debug
            except (TypeError, json.JSONDecodeError) as e:
                 print(f"Error encoding component data: {e}") # Use logger
        else:
             # Fallback for unexpected item data
             mime_data.setText(item.text())

        return mime_data