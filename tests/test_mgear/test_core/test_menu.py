"""mgear.core.menu and mgear.menu tests"""

import ast
import importlib
from functools import partial


def _menu_calls(source):
    """Get the (module, function) pairs called in a menu command string.

    Args:
        source (str): Python source of a menu command.

    Returns:
        list: (module_name, function_name) tuples.
    """
    calls = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            calls.append((node.func.value.id, node.func.attr))
    return calls


def test_skinning_menu_commands_are_strings(run_with_maya_standalone, setup_path):
    from mgear.core import menu

    commands = [c for c in menu.skinning_menu_commands() if c[1]]
    assert commands
    for conf in commands:
        label, command = conf[0], conf[1]
        assert isinstance(command, str), label


def test_skinning_menu_commands_resolve(run_with_maya_standalone, setup_path):
    from mgear.core import menu

    for conf in menu.skinning_menu_commands():
        label, command = conf[0], conf[1]
        if not command:
            continue
        compile(command, label, "exec")
        calls = _menu_calls(command)
        assert calls, label
        for module_name, func_name in calls:
            module = importlib.import_module("mgear.core." + module_name)
            assert callable(getattr(module, func_name, None)), (
                label,
                func_name,
            )


def test_install_warns_on_callable_command(
    run_with_maya_standalone, setup_path, monkeypatch
):
    import mgear.menu

    created = []
    warnings = []
    monkeypatch.setattr(
        mgear.menu.pm,
        "menuItem",
        lambda *args, **kwargs: created.append(kwargs) or "subMenu",
    )
    monkeypatch.setattr(mgear.menu.pm, "displayWarning", warnings.append)
    errors = []
    monkeypatch.setattr(mgear.menu.pm, "displayError", errors.append)

    commands = (
        ("String Item", "print('ok')", "a.svg"),
        ("-----", None),
        ("Callable Item", partial(print, "ok"), "b.svg"),
    )
    mgear.menu.install("Test Menu", commands, parent="parentMenu")

    assert errors == []
    assert len(warnings) == 1
    assert "'Test Menu' > 'Callable Item'" in warnings[0]
    # The warning does not block the item from being created.
    assert created[-1]["label"] == "Callable Item"
