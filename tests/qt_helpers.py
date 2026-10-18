"""Qt helpers shared by the tests and the mayapy profiling harnesses.

Importable without Maya: the Maya modules are imported when the helpers run.
"""

import types


def start_qt():
    """Create the GUI QApplication, before Maya starts.

    Widget code needs a GUI QApplication, and maya.standalone.initialize()
    creates a non-GUI one if none exists yet.

    Returns:
        QtWidgets.QApplication: The application, or None when no PySide
            binding is installed (e.g. CI without Maya).
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PySide2 import QtWidgets
        except ImportError:
            return None
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def stub_main_window(setattr_func=setattr):
    """Let Maya's dockable mixin build widgets without a main window.

    ``MayaQWidgetDockableMixin`` compares its parent with
    ``MQtUtil.mainWindow()``, which is None in mayapy. Only the mixin's
    module gets the stub; mGear's ``pyqt.maya_main_window`` still gets None.

    Args:
        setattr_func (callable, optional): Sets the stub on the mixin module,
            e.g. ``monkeypatch.setattr`` to undo it after a test.
    """
    import maya.OpenMayaUI as omui
    from maya.app.general import mayaMixin

    if omui.MQtUtil.mainWindow() is not None:
        return

    class _MQtUtil(omui.MQtUtil):
        @staticmethod
        def mainWindow():
            return 0

    proxy = types.ModuleType("omui_stub")
    proxy.__dict__.update(omui.__dict__)
    proxy.MQtUtil = _MQtUtil
    setattr_func(mayaMixin, "omui", proxy)
