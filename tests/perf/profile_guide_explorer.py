"""Shifter Guide Explorer profiling harness.

Imports a guide template with mayapy, builds the Guide Explorer widget and
times its tree and settings panel operations: a forced tree rebuild, a scene
refresh with no guide change, opening the guide settings panel and opening a
component settings panel. Reports the times and the top cProfile entries of
each operation.

Not a pytest module. Run it with mayapy from the repository root::

    mayapy tests/perf/profile_guide_explorer.py biped.sgt
    mayapy tests/perf/profile_guide_explorer.py path/to/guide.sgt --no-profile
    mayapy tests/perf/profile_guide_explorer.py biped.sgt --save-baseline base.json
    mayapy tests/perf/profile_guide_explorer.py biped.sgt --baseline base.json

A guide using custom components needs ``MGEAR_SHIFTER_COMPONENT_PATH`` set
to their folder.
"""

import argparse
import json
import os
import sys

from profile_build import add_common_args
from profile_build import print_stats
from profile_build import run_profiled
from profile_build import start_maya
from profile_guide import template_path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qt_helpers import start_qt  # noqa: E402
from qt_helpers import stub_main_window  # noqa: E402

OPERATIONS = ("Tree rebuild", "Scene refresh", "Guide panel", "Component panel")


def parse_args(argv=None):
    """Parse the command line arguments.

    Args:
        argv (list of str, optional): Arguments to parse. Defaults to
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "template",
        nargs="?",
        default="biped.sgt",
        help="Bundled template file name or path of a .sgt file.",
    )
    add_common_args(parser, top=25)
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Run each operation this many times and keep the fastest.",
    )
    return parser.parse_args(argv)


def profile_explorer(path, profile=True, repeat=3):
    """Import a guide template and time the Guide Explorer operations.

    Args:
        path (str): Path of the guide template file.
        profile (bool, optional): Run the operations under cProfile.
        repeat (int, optional): Runs per operation; the fastest is kept.

    Returns:
        tuple: (result dict, dict of operation name to cProfile.Profile)
    """
    from maya import cmds

    import mgear
    from mgear.shifter import io
    from mgear.shifter.guide_explorer import guide_explorer_widget
    from mgear.shifter.guide_explorer import guide_tree_widget
    from mgear.shifter.guide_explorer.models import ShifterComponent

    mgear.log = lambda *args, **kwargs: None

    with open(path) as f:
        conf = json.load(f)

    cmds.file(new=True, force=True)
    io.import_guide_template(conf=conf)
    cmds.select(clear=True)

    explorer = guide_explorer_widget.GuideExplorerWidget()
    tree = explorer.guide_tree_widget
    tree.refresh(force=True)

    root_item = tree.topLevelItem(0)
    components = root_item.childCount()
    guide_data = root_item.data(0, guide_tree_widget.DATA_ROLE)
    comp_data = None
    for i in range(root_item.childCount()):
        data = root_item.child(i).data(0, guide_tree_widget.DATA_ROLE)
        if isinstance(data, ShifterComponent):
            comp_data = data
            break

    operations = {
        "Tree rebuild": lambda: tree.refresh(force=True),
        "Scene refresh": explorer.refresh,
        "Guide panel": lambda: explorer.open_guide_widget(guide_data, force=True),
    }
    if comp_data:
        operations["Component panel"] = lambda: explorer.open_component_widget(
            comp_data, force=True
        )

    times = {}
    profilers = {}
    for name in OPERATIONS:
        if name not in operations:
            continue
        best = None
        for _ in range(max(1, repeat)):
            seconds, profiler, _value = run_profiled(operations[name], profile)
            if best is None or seconds < best[0]:
                best = (seconds, profiler)
        times[name] = best[0]
        if best[1]:
            profilers[name] = best[1]

    result = {
        "template": os.path.basename(path),
        "maya": cmds.about(version=True),
        "profiled": profile,
        "components": components,
        "transforms": len(cmds.ls(dag=True, type="transform")),
        "times": times,
    }
    explorer.teardown()
    return result, profilers


def report(result, baseline=None):
    """Print the Guide Explorer operations report.

    Args:
        result (dict): Result from ``profile_explorer``.
        baseline (dict, optional): An earlier result to compare with.
    """
    print("\n" + "=" * 64)
    print(
        "{template}: {components} components, {transforms} transforms".format(**result)
    )
    print("=" * 64)
    base_times = (baseline or {}).get("times", {})
    for name in OPERATIONS:
        if name not in result["times"]:
            continue
        seconds = result["times"][name]
        line = "  {:<16}{:>8.3f}s".format(name, seconds)
        if base_times.get(name):
            line += "   {:+.3f}s ({:.0%} of baseline)".format(
                seconds - base_times[name], seconds / base_times[name]
            )
        print(line)


def main(argv=None):
    """Run the harness.

    Args:
        argv (list of str, optional): Command line arguments.

    Returns:
        dict: The result.
    """
    args = parse_args(argv)
    app = start_qt()  # noqa: F841 - must exist before Maya starts
    start_maya()
    try:
        stub_main_window()
        result, profilers = profile_explorer(
            template_path(args.template),
            profile=not args.no_profile,
            repeat=args.repeat,
        )
        baseline = None
        if args.baseline:
            with open(args.baseline) as f:
                baseline = json.load(f)
        report(result, baseline)

        for name in OPERATIONS:
            if name not in profilers:
                continue
            print("\n--- {} (sorted by self time)".format(name))
            print_stats(profilers[name], args.top)
        if args.save_baseline:
            with open(args.save_baseline, "w") as f:
                json.dump(result, f, indent=4)
            print("Baseline written to {}".format(args.save_baseline))
        return result
    finally:
        import maya.standalone

        maya.standalone.uninitialize()


if __name__ == "__main__":
    main()
