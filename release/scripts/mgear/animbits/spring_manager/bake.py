"""Bake and delete spring setups of any backend."""

from collections import OrderedDict

from maya import cmds

import mgear
from mgear.core import anim_utils
from mgear.core import utils

from . import constants
from .backends import get_backend


def group_by_backend(springs, available=False):
    """Group springs by backend. Springs of unknown backends are skipped.

    Args:
        springs (list): :class:`registry.Spring` records.
        available (bool, optional): Also skip the springs whose backend
            can't be used (e.g. solver plug-in not loaded).

    Returns:
        OrderedDict: ``{backend: [spring, ...]}``.
    """
    groups = OrderedDict()
    for spring in springs:
        backend = get_backend(spring.backend)
        if backend and available and not backend.is_available():
            mgear.log(
                "{} skipped: the {} solver is not available".format(
                    spring.label, backend.label
                ),
                mgear.sev_warning,
            )
        elif backend:
            groups.setdefault(backend, []).append(spring)
        else:
            mgear.log(
                "Unknown spring backend {} on {}".format(spring.backend, spring.node),
                mgear.sev_warning,
            )
    return groups


def collect_channels(groups):
    """Return the plugs a bake must key for grouped springs.

    Args:
        groups (dict): ``{backend: [spring, ...]}``.

    Returns:
        list: ``node.attr`` plugs, without duplicates.
    """
    plugs = []
    seen = set()
    for backend, springs in groups.items():
        for spring in springs:
            for node, attrs in backend.bake_channels(spring).items():
                for attr in attrs:
                    plug = "{}.{}".format(node, attr)
                    if plug not in seen:
                        seen.add(plug)
                        plugs.append(plug)
    return plugs


def delete(springs, transfer_animation=True):
    """Delete spring setups of any backend, in one undo chunk.

    Args:
        springs (list): :class:`registry.Spring` records.
        transfer_animation (bool, optional): Give the animation back to the
            controls.
    """
    with utils.undo_chunk("springManagerDelete"):
        for backend, group in group_by_backend(springs).items():
            for spring in group:
                if spring.exists():
                    backend.delete(spring, transfer_animation)


def bake(
    springs,
    start=None,
    end=None,
    preroll=0,
    delete_springs=True,
    destination_layer=None,
):
    """Bake springs onto their controls.

    Args:
        springs (list): :class:`registry.Spring` records. Baked and
            missing springs are skipped.
        start (float, optional): First frame, the playback start when None.
        end (float, optional): Last frame, the playback end when None.
        preroll (int, optional): Frames evaluated before ``start`` so the
            simulation is settled when baking starts. No keys are written
            before ``start``.
        delete_springs (bool, optional): Delete the setups after baking.
            Otherwise they are kept, detached from the controls, and
            marked as baked.
        destination_layer (str, optional): Bake to this animation layer,
            created when missing, keeping the original animation.

    Returns:
        bool: True if something was baked.
    """
    groups = group_by_backend(
        (
            spring
            for spring in springs
            if spring.exists() and spring.state != constants.STATE_BAKED
        ),
        available=True,
    )
    plugs = collect_channels(groups)
    if not plugs:
        mgear.log("No spring channels to bake", mgear.sev_warning)
        return False
    if start is None:
        start = cmds.playbackOptions(query=True, minTime=True)

    with utils.undo_chunk("springManagerBake"):
        for backend, group in groups.items():
            backend.prepare_bake(group, start - max(0, preroll))
        try:
            anim_utils.bake_attributes(
                plugs,
                start=start,
                end=end,
                preroll=preroll,
                destination_layer=destination_layer,
            )
        finally:
            for backend, group in groups.items():
                backend.finish_bake(group)
        if delete_springs:
            # baked on a layer: the original animation goes back to the base
            delete(
                [spring for group in groups.values() for spring in group],
                transfer_animation=bool(destination_layer),
            )
        else:
            for backend, group in groups.items():
                for spring in group:
                    backend.detach(spring)
                    spring.set_state(constants.STATE_BAKED)
    count = sum(len(group) for group in groups.values())
    mgear.log("Baked {} spring(s)".format(count))
    return True
