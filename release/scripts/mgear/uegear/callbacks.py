#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains custom Maya callbacks used by ueGear.
"""

from __future__ import print_function, division, absolute_import

import maya.OpenMayaUI as OpenMayaUI

from mgear.uegear import log

logger = log.uegear_logger


def register_callbacks():
    try:
        UeGearExternalDropCallback.instance = UeGearExternalDropCallback()
        OpenMayaUI.MExternalDropCallback.addCallback(
            UeGearExternalDropCallback.instance
        )
        logger.info(
            "Successfully registered callback: UeGearExternalDropCallback"
        )
    except Exception:
        logger.error("Failed to register callback: UeGearExternalDropCallback")
        raise


def unregister_callbacks():
    try:
        OpenMayaUI.MExternalDropCallback.removeCallback(
            UeGearExternalDropCallback.instance
        )
        logger.info(
            "Successfully deregistered callback: UeGearExternalDropCallback"
        )
    except Exception:
        logger.erro(
            "Failed to deregister callback: UeGearExternalDropCallback"
        )
        raise


class UeGearExternalDropCallback(OpenMayaUI.MExternalDropCallback):
    instance = None

    def externalDropCallback(self, doDrop, controlName, data):
        str = "External Drop:  doDrop = %d,  controlName = %s" % (
            doDrop,
            controlName,
        )
        print(str)
