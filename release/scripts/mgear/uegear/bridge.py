#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
ueGear Client to interact with ueGear Commands within Unreal Engine.
"""

from __future__ import print_function, division, absolute_import

import json
import pprint

from mgear.core.six.moves import urllib

# from urllib.request import urlopen, Request

Request = urllib.request.Request
urlopen = urllib.request.urlopen

from mgear.uegear import log

logger = log.uegear_logger


class UeGearBridge(object):
    """
    Unreal Engine Gear Bridge
    """

    def __init__(self, port=30010, host_address="127.0.0.1"):
        super(UeGearBridge, self).__init__()

        self._host_address = host_address
        self._port = port
        self._timeout = (
            1000  # connection to the server will time out after this value.
        )
        self._echo_execution = True  # whether client should print the response coming from server.
        self._echo_payload = True  # whether client should print the JSON payload it's sending to server.
        self._is_executing = (
            False  # whether client is still executing a command.
        )
        self._commands_object_path = (
            "/Engine/PythonTypes.Default__PyUeGearCommands"
        )
        self._headers = {
            "Content-type": "application/json",
            "Accept": "text/plain",
        }

    # =================================================================================================================
    # PROPERTIES
    # =================================================================================================================

    @property
    def port(self):
        return self._port

    @property
    def host_address(self):
        return self._host_address

    @property
    def is_executing(self):
        return self._is_executing

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    @property
    def echo_execution(self):
        return self._echo_execution

    @echo_execution.setter
    def echo_execution(self, value):
        self._echo_execution = value

    @property
    def echo_payload(self):
        return self._echo_payload

    @echo_payload.setter
    def echo_payload(self, value):
        self._echo_payload = value

    @property
    def commands_object_path(self):
        return self._commands_object_path

    @commands_object_path.setter
    def commands_object_path(self, value):
        self._commands_object_path = value

    # =================================================================================================================
    # BASE
    # =================================================================================================================

    def execute(self, command, parameters=None, timeout=0):
        """
        Executes given command for this client. The server will look for this command in the modules it has loaded.

        :param str command:  The command name that you want to execute within PyUeGearCommands class.
        :param dict parameters: arguments for the command to execute. These have to match the argument names on the
            function exactly.
        :param float timeout: time in seconds after which the request will timeout.
        :return: response coming from the Unreal Remote Server.
        :rtype: dict
        """

        self._is_executing = True
        timeout = timeout if timeout > 0 else self._timeout
        parameters = parameters or dict()

        url = "http://{}:{}/remote/object/call".format(
            self._host_address, self._port
        )
        payload = {
            "objectPath": self._commands_object_path,
            "functionName": command,
            "parameters": parameters,
            "generateTransaction": True,
        }
        try:
            request = Request(
                url,
                json.dumps(payload).encode("ascii"),
                self._headers,
                method="PUT",
            )
            with urlopen(request, timeout=timeout) as response:
                response = json.load(response)
        except Exception:
            response = {"return": False}
        try:
            evaluated_return = eval(response.get("return"))
            response = {"return": evaluated_return}
        except Exception:
            pass

        if self._echo_payload:
            pprint.pprint(payload)

        if self._echo_execution:
            pprint.pprint(response)

        self._is_executing = False

        return response
