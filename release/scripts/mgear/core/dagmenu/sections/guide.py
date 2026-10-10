"""Built-in dag menu sections for Shifter guides.

Shifter is imported when a command runs, so importing the dag menu doesn't
load it.
"""

import importlib
from functools import partial

CONTEXT = "guide"


def _call(module, function, *args):
    """Import a module and call one of its functions.

    Args:
        module (str): Module path. i.e: "mgear.shifter.guide_manager"
        function (str): Function name.
        *args: Function arguments.
    """
    getattr(importlib.import_module(module), function)(*args)


def _command(module, function, *args):
    return partial(_call, module, function, *args)


_GUIDE_MANAGER = "mgear.shifter.guide_manager"
_GUIDE_TEMPLATE = "mgear.shifter.guide_template"

# (section name, order, ((label, command, icon), ...))
SECTIONS = (
    (
        "settings",
        100,
        (
            (
                "Settings",
                _command(_GUIDE_MANAGER, "inspect_settings", 0),
                "mgear_sliders.svg",
            ),
        ),
    ),
    (
        "build",
        200,
        (
            (
                "Build From Selection",
                _command(_GUIDE_MANAGER, "build_from_selection"),
                "mgear_play.svg",
            ),
        ),
    ),
    (
        "duplicate",
        300,
        (
            (
                "Duplicate",
                _command(_GUIDE_MANAGER, "duplicate", False),
                "mgear_copy.svg",
            ),
            (
                "Duplicate Symme",
                _command(_GUIDE_MANAGER, "duplicate", True),
                "mgear_duplicate_sym.svg",
            ),
        ),
    ),
    (
        "guide_manager",
        400,
        (
            (
                "Guide Manager",
                _command("mgear.shifter.guide_manager_gui", "show_guide_manager"),
                "mgear_list.svg",
            ),
        ),
    ),
    (
        "export",
        500,
        (
            (
                "Export Guide From Selection",
                _command("mgear.shifter.io", "export_guide_template", None, None),
                "mgear_log-out.svg",
            ),
        ),
    ),
    (
        "update",
        600,
        (
            (
                "Update Guide",
                _command(_GUIDE_TEMPLATE, "updateGuide"),
                "mgear_loader.svg",
            ),
            (
                "Update Selected Components Type",
                _command(
                    "mgear.compatible.compatible_comp_dagmenu",
                    "update_component_type_and_update_guide_with_dagmenu",
                ),
                "mgear_loader.svg",
            ),
            (
                "Reload Components",
                _command("mgear.shifter", "reloadComponents"),
                "mgear_refresh-cw.svg",
            ),
        ),
    ),
    (
        "xray",
        700,
        (
            (
                "X-Ray Guide Toggle",
                _command(_GUIDE_TEMPLATE, "guide_toggle_xray"),
                "mgear_x.svg",
            ),
        ),
    ),
)


def _build_items(items, builder, ctx):
    for label, command, image in items:
        builder.item(label, command, image=image)


def register(registry):
    """Register the built-in guide sections.

    Args:
        registry (Registry): Dag menu registry.
    """
    for name, order, items in SECTIONS:
        registry.register_section(CONTEXT, name, order, partial(_build_items, items))
