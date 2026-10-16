# mGear UI Style Guide

These rules apply to **new tools**. Existing tools move to them one at a time,
only when a migration is asked for.

The code side lives in two modules:
- `mgear.core.ui_style` holds colour roles and metrics.
- `mgear.core.widgets` holds the shared widgets.

The `/ui-style` skill audits a UI file against this guide, and the `/mgear-ui`
skill has the class template.

## 1. Principles

1. **Follow Maya's look.** Tools use Maya's native widgets and palette. No
   window or application stylesheets.
2. **Roles, not colours.** Never write hex or `rgb()` values in a tool. Style
   a widget with `ui_style.set_role(widget, role)`.
3. **One primary action per section.** It is the button the section exists
   for. Everything else is plain, `secondary` or `danger`.
4. **No logic in the UI.** Windows collect input and show results. The work
   happens in Qt-free functions that tests can call.
5. **Reuse the core widgets.** Never re-implement a collapsible section,
   resize grip, colour swatch or node list. If a widget is missing and three
   or more tools need it, add it to `mgear.core.widgets`.

## 2. Window anatomy

From top to bottom:

```
+-----------------------------------------+
| File  Edit  <Tool menus>  Help          |  menu bar (optional)
+-----------------------------------------+
| > 1. First Section                      |  scrollable content:
|   ...                                   |  CollapsibleWidget sections,
| > 2. Second Section                     |  tabs or a splitter (see 3)
|   ...                                   |
+-----------------------------------------+
| [ Cancel ]  [ Secondary ]  [ Primary ]  |  ActionBar (optional)
| Status message                          |  StatusLine (optional)
+-----------------------------------------+
```

- **Base class:** `MayaQWidgetDockableMixin, QtWidgets.QDialog,
  pyqt.SettingsMixin`.
- **Showing the window:** `pyqt.showDialog(MyTool, dockable=True)`. Tool
  windows are dockable by default.
- **Modal dialogs:** use a modal `QDialog` (`exec_()`) only for short
  questions and choices that block a single action. Guide Import is an
  example.
- **Menu bar:**
  - Build a `QMenuBar` and attach it with `main_layout.setMenuBar(...)`.
  - Use the usual menus: **File** (Import/Export Configuration, recent
    files), **Edit** (Reset to Defaults), tool menus, then **Help**.
  - Commands that are used rarely belong in the menu, not in buttons.
- **Scrollable content:** put the sections in a `QScrollArea` with
  `setWidgetResizable(True)` and `setFrameShape(QtWidgets.QFrame.NoFrame)`.
  End the column with `addStretch()` unless one section expands to fill the
  space.
- **ActionBar:** used when the window has a final action, such as Build,
  Apply or Export. A tool made of independent sections, where every section
  has its own action, puts a full-width primary button at the end of each
  section instead.
- **Window flags:**
  - On Windows, clear the help button with
    `self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint`. XOR would
    add the button on Qt6.
  - On macOS, use `QtCore.Qt.Tool`.

## 3. Choosing a container

| Need | Use | Notes |
|---|---|---|
| Several groups of controls in a vertical tool panel | `widgets.CollapsibleWidget` | The default. Number the headers ("1. Create Wire Deformer") when the steps run in order. Use `expandable=False` for sections that should not grow. |
| Separate modes that are not used at the same time | `QTabWidget` | For example Components / Guide Explorer / Templates. Never put tabs inside tabs. |
| Two views side by side, both always visible, user-resizable | `QSplitter` | For example list and editor, or canvas and edit panel. Save `saveState()` in the settings. Set a minimum width on each child. |
| One list or table in a stack of sections that needs a resizable height | `widgets.HeightGrip` | Use this instead of a vertical splitter between sections. |
| A small set of related options inside a section | `QGroupBox` | One level deep. Not as a section container; that is the CollapsibleWidget's job. |
| Steps or pages where only one is shown | `QStackedWidget` | Wizards, a choice page followed by a result page. |
| Label/field pairs | `QFormLayout` | Labels align right. |

- Never nest CollapsibleWidgets more than one level deep.
- Never build a collapse from a checkable `QToolButton` or a checkable
  `QGroupBox`.
- A section that holds a single row does not need a collapsible.

## 4. Buttons and colour roles

| Role | Use | Maya colour |
|---|---|---|
| `primary` | The single main action: Create, Apply, Build, Import | `#4a7c4e` (pressed `#3a6c3e`) |
| `secondary` | Alternative emphasised action: Convert, Add & Snap | `#4a6b8c` |
| `danger` | Destructive action: Delete, Remove All, Clear | `#8c4a4a` |
| *(no role)* | Every other button | native |
| `text_hint` | Hints, empty states, the idle status line | `#888888` |
| `text_success` / `text_warning` / `text_error` | Results in the status line or next to a field | `#66cc66` / `#e6a03c` / `#cc6666` |
| `selection` | Custom-painted selected or checked state | `#5285a6` |
| `tooltip_accent` | Title of `pyqt.rich_tooltip` (applied by it) | `#4a90d9` |

```python
from mgear.core import ui_style
from mgear.core import widgets

build_btn = widgets.action_button("Build Rig")  # primary
ui_style.set_role(delete_btn, "danger")
color = ui_style.color("selection")  # QColor, for custom painting
```

- `set_role` replaces the widget's stylesheet. Don't add your own
  stylesheet to the same widget.
- **Labels:** Title Case, verb + noun: "Create Wire Deformer", "Add
  Selected", "Apply to All". Leave out "Click to" and "Button".
- **Primary placement:** the primary button is the last one in the
  `ActionBar` (on the right), or a full-width button at the end of its
  section.
- **Destructive actions:**
  - Use `danger` only when the action is hard to undo. Otherwise use a plain
    button.
  - Ask for confirmation first, with
    `QtWidgets.QMessageBox.question(self, ...)` parented to the tool window.
- **Dialogs:** call `setAutoDefault(False)` on dialog buttons so Enter in a
  field does not trigger them. `action_button` does this for you.
- **Icon-only buttons:**
  - Use `widgets.create_button(icon=...)`.
  - They always get a tooltip. Use `pyqt.rich_tooltip` for tools that need
    more than one line.
- **Small helper buttons:**
  - Use `create_button(size=17)` for in-row helpers such as `<<` (pick
    selection), `+`/`-` and Pick.
  - Put them at the right end of the row.

## 5. Text

- **Title Case:** window titles, section headers, tab names, menu entries,
  buttons.
- **Sentence case:** field labels, check boxes, tooltips, hints, status
  messages.
- **Window titles:** use the tool name only ("Spring Manager"), stored in a
  `TOOL_TITLE` constant.
- **Placeholders:**
  - Say what goes in the field: "Select mesh to deform".
  - Filter fields name their syntax: "Filter (regex)" or "Filter springs (*
    wildcard)".
- **Status messages:** short and specific, without a trailing full stop
  ("Converted 3 wires to skin").

## 6. Metrics

Constants are in 96 DPI pixels. Always pass them through
`ui_style.scaled()` (or `pyqt.dpi_scale`).

| Constant | Value | Use |
|---|---|---|
| `XS` | 2 | Spacing inside dense rows |
| `S` | 4 | Default spacing between widgets |
| `M` | 6 | Spacing between groups |
| `L` | 10 | Spacing between major blocks |
| `SECTION_MARGINS` | 4, 2, 4, 2 | Section bodies, ActionBar, StatusLine |
| `BUTTON_HEIGHT_PRIMARY` | 32 | Buttons made with `action_button` / `ActionBar` |

- **Layouts:**
  - The outer window layout has margins 0 and spacing 0, so sections touch
    the window edges like Maya panels.
  - Section bodies use `SECTION_MARGINS`.
- **Window size:**
  - Set minimum widths with `dpi_scale`, for example
    `setMinimumWidth(pyqt.dpi_scale(320))`.
  - Size the window so that every section is readable without scrolling
    sideways.
- **Never hard-code pixel sizes** without scaling them for DPI.

## 7. Lists, tables and trees

- **Filter field:** put it above the list, not below.
- **Multi-selection:** lists with many items allow it
  (`ExtendedSelection`).
- **Item actions:**
  - Double-click runs the obvious action, for example selecting the item in
    Maya.
  - Secondary actions go in a context menu.
- **Empty lists** show a hint in `text_hint`, for example "No bindControl
  guides found".
- **Proxy filtering:** reuse `pyqt.set_proxy_filter` and
  `pyqt.wildcard_to_regex`.

## 8. Feedback

- **Results** go to the `StatusLine` with the matching role. Don't open a
  modal popup on success.
- **Errors:**
  - Show them in the `StatusLine` with `text_error`, and log them.
  - Use a modal message only when the user must act before going on.
- **Long jobs:** use Maya's main progress bar through the existing core
  helpers (`$gMainProgressBar`), not a `QProgressBar` in the window.
- **Logging:** use `logging.getLogger(__name__)`. Don't use `print`.

## 9. Settings

- **Persistence:** use `pyqt.SettingsMixin`. Keys are named
  `<toolName>_<field>`, in `self.user_settings = {key: (widget, default)}`.
- **What to save:**
  - splitter state;
  - collapsible expanded state (`expandedChanged`);
  - the last used options.
- **Reset:** File or Edit > Reset to Defaults resets the widgets to their
  `user_settings` defaults.

## 10. Naming and instances

- `toolName = "mgear<ToolName>"`. It is the objectName and the workspace
  control prefix.
- `TOOL_TITLE = "<Tool Name>"` is the window title.
- **One window per tool:**
  - Open it through `pyqt.showDialog`, which deletes old instances and the
    workspace control.
  - Release resources in `close()` and `dockCloseEventTriggered()`, for
    example callbacks via `mgear.core.callbackManager` (never scriptJobs).
  - Save the settings there too.

## 11. Icons

- Use the SVG icons in `release/icons/`, loaded with `pyqt.get_icon(name,
  size)`.
- New icons are SVG with an `mgear_` prefix.
- Don't add icon loaders local to a tool.

## 12. Review checklist

- [ ] No hex or `rgb()` colours; roles come from `ui_style`
- [ ] At most one `primary` per section or window
- [ ] Containers follow the table in section 3; no hand-made collapses
- [ ] Window anatomy: menu bar, scroll content, ActionBar, StatusLine
- [ ] Sizes and margins scaled with `ui_style.scaled` or `pyqt.dpi_scale`
- [ ] Title Case buttons and headers; Sentence case labels and hints
- [ ] Filter fields name their syntax; lists show an empty-state hint
- [ ] Results go to the StatusLine; no success popups
- [ ] `SettingsMixin` with `<toolName>_` keys; splitter and collapse state saved
- [ ] `toolName`, `TOOL_TITLE`, opened with `pyqt.showDialog`
- [ ] Icons through `pyqt.get_icon`; icon-only buttons have tooltips
- [ ] Logic lives outside the UI and has tests
