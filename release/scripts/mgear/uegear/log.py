#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains ueGear logger.
"""

from __future__ import print_function, division, absolute_import

import logging

uegear_logger = logging.getLogger('ueGear')
uegear_logger.propagate = False
handlers = uegear_logger.handlers
if not handlers:
	handler = logging.StreamHandler()
	handler.setFormatter(logging.Formatter("[%(name)s - %(module)s - %(funcName)s - %(levelname)s]: %(message)s"))
	uegear_logger.addHandler(handler)
