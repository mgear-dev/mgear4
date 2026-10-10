"""Shifter build profiling harness.

Builds a bundled Shifter guide template in a new scene with mayapy and
reports the total build time, the time of each build phase, the scene node
count and the top cProfile entries. Phases are timed by wrapping the build
methods from this script, so the build code needs no timing code.

Not a pytest module. Run it with mayapy from the repository root::

    mayapy tests/perf/profile_build.py biped.sgt
    mayapy tests/perf/profile_build.py biped.sgt --out biped.prof
    mayapy tests/perf/profile_build.py biped.sgt --save-baseline base.json
    mayapy tests/perf/profile_build.py biped.sgt --baseline base.json
"""

import argparse
import cProfile
import importlib
import json
import os
import pstats
import sys
import time
from functools import wraps

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SCRIPTS = os.path.join(REPO, "release", "scripts")
PLATFORMS = os.path.join(REPO, "release", "platforms")
PLUGINS = ("mgear_solvers", "mGearWeightDriver")
# Timed build phases in build order: (module, class, method, label). The
# modules are imported after Maya starts.
PHASES = (
    ("mgear.shifter", "Rig", "preCustomStep", "Pre custom steps"),
    ("mgear.shifter.guide", "Rig", "setFromSelection", "Guide read"),
    ("mgear.shifter", "Rig", "initialHierarchy", "Initial hierarchy"),
    ("mgear.shifter.component", "Main", "step_00", "Step Objects"),
    ("mgear.shifter.component", "Main", "step_01", "Step Properties"),
    ("mgear.shifter.component", "Main", "step_02", "Step Operators"),
    ("mgear.shifter.component", "Main", "step_03", "Step Connect"),
    ("mgear.shifter.component", "Main", "step_04", "Step Joints"),
    ("mgear.shifter.component", "Main", "step_05", "Step Finalize"),
    ("mgear.shifter", "Rig", "finalize", "Finalize"),
    ("mgear.shifter", "Rig", "postCustomStep", "Post custom steps"),
)


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
        help="Bundled template file name (shifter/component/_templates).",
    )
    parser.add_argument("--out", help="Write the cProfile stats to this file.")
    parser.add_argument(
        "--baseline", help="Compare the phase times with this baseline JSON."
    )
    parser.add_argument(
        "--save-baseline", help="Write the phase times to this JSON file."
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Time the build without cProfile (closer to real build time).",
    )
    parser.add_argument(
        "--top", type=int, default=30, help="Number of cProfile entries to print."
    )
    return parser.parse_args(argv)


def start_maya():
    """Start maya.standalone, make mgear importable and load the plug-ins."""
    import maya.standalone

    maya.standalone.initialize(name="python")

    from maya import cmds

    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)

    version = cmds.about(majorVersion=True)
    for name in PLUGINS:
        if cmds.pluginInfo(name, query=True, loaded=True):
            continue
        path = os.path.join(
            PLATFORMS, version, "windows", "x64", "plug-ins", name + ".mll"
        )
        try:
            cmds.loadPlugin(path if os.path.exists(path) else name)
        except RuntimeError:
            print("WARNING: plug-in {} not loaded".format(name))


def _timed(func, key, timings):
    """Wrap a function to add its run time to ``timings[key]``.

    Args:
        func (callable): The function to wrap.
        key (str): The timings key.
        timings (dict): Phase name to accumulated seconds.

    Returns:
        callable: The wrapped function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            timings[key] = timings.get(key, 0.0) + time.perf_counter() - start

    return wrapper


def install_phase_timers(timings):
    """Wrap the Shifter build phase methods to time them.

    Args:
        timings (dict): Filled with phase name to accumulated seconds.
    """
    for module_name, class_name, method_name, label in PHASES:
        cls = getattr(importlib.import_module(module_name), class_name)
        method = getattr(cls, method_name)
        setattr(cls, method_name, _timed(method, label, timings))


def build_template(template, profile=True):
    """Import a bundled template in a new scene and build it.

    Args:
        template (str): Template file name, e.g. ``biped.sgt``.
        profile (bool, optional): Run the build under cProfile.

    Returns:
        tuple: (total seconds, cProfile.Profile or None, shifter.Rig)
    """
    from maya import cmds

    import mgear
    from mgear import shifter
    from mgear.shifter import io

    mgear.log = lambda *args, **kwargs: None

    cmds.file(new=True, force=True)
    io.import_sample_template(template)
    cmds.select("guide")

    rig = shifter.Rig()
    profiler = cProfile.Profile() if profile else None
    start = time.perf_counter()
    if profiler:
        profiler.enable()
    rig.buildFromSelection()
    if profiler:
        profiler.disable()
    return time.perf_counter() - start, profiler, rig


def report(result, baseline=None):
    """Print the build report.

    Args:
        result (dict): Result with ``template``, ``total``, ``nodes``,
            ``components`` and ``phases`` keys.
        baseline (dict, optional): An earlier result to compare with.
    """
    print("\n" + "=" * 64)
    print(
        "{template}: {total:.2f}s  ({components} components, "
        "{nodes} nodes)".format(**result)
    )
    print("=" * 64)
    base_phases = (baseline or {}).get("phases", {})
    for name, seconds in result["phases"].items():
        line = "  {:<22}{:>8.3f}s".format(name, seconds)
        if name in base_phases:
            line += "   {:+.3f}s".format(seconds - base_phases[name])
        print(line)
    if baseline:
        print(
            "  {:<22}{:>8.3f}s   {:+.3f}s ({:.0%} of baseline)".format(
                "Total",
                result["total"],
                result["total"] - baseline["total"],
                result["total"] / baseline["total"],
            )
        )
        if baseline.get("nodes") != result["nodes"]:
            print(
                "  WARNING: node count {} differs from baseline {}".format(
                    result["nodes"], baseline.get("nodes")
                )
            )


def main(argv=None):
    """Run the harness.

    Args:
        argv (list of str, optional): Command line arguments.

    Returns:
        dict: The build result.
    """
    args = parse_args(argv)
    start_maya()

    from maya import cmds

    timings = {}
    install_phase_timers(timings)
    total, profiler, rig = build_template(args.template, profile=not args.no_profile)
    labels = [phase[-1] for phase in PHASES]
    result = {
        "template": args.template,
        "maya": cmds.about(version=True),
        "profiled": profiler is not None,
        "total": total,
        "nodes": len(cmds.ls()),
        "components": len(rig.componentsIndex),
        "phases": {name: timings[name] for name in labels if name in timings},
    }

    baseline = None
    if args.baseline:
        with open(args.baseline) as f:
            baseline = json.load(f)
    report(result, baseline)

    if profiler:
        stats = pstats.Stats(profiler)
        stats.sort_stats("tottime").print_stats(args.top)
        if args.out:
            stats.dump_stats(args.out)
            print("Profile written to {}".format(args.out))
    if args.save_baseline:
        with open(args.save_baseline, "w") as f:
            json.dump(result, f, indent=4)
        print("Baseline written to {}".format(args.save_baseline))
    return result


if __name__ == "__main__":
    main()
