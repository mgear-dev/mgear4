from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals


import os
import json
import functools

from mgear.core import pyqt
from mgear.vendor.Qt import QtWidgets

from mgear.anim_picker.widgets import basic

ANIM_PICKER_VAR = "ANIM_PICKER_PATH"

# i/o -------------------------------------------------------------------------


def _importData(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(e)


def _exportData(data, file_path):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, sort_keys=False, indent=4)
    except Exception as e:
        print(e)


def _convert_path_token(file_path):
    """convert ANIM_PICKER_PATH env var to a full path

    Args:
        file_path (str): file path

    Returns:
        str: file path with updated token to path
    """
    path_token = "[{}]".format(ANIM_PICKER_VAR)
    if path_token in file_path:
        if os.environ.get(ANIM_PICKER_VAR, ""):
            file_path = file_path.replace(path_token,
                                          os.environ.get(ANIM_PICKER_VAR, ""))
    return file_path


def convert_path_token(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        if args:
            list(args)[0] = _convert_path_token(args[0])
        else:
            kwargs["file_path"] = _convert_path_token(kwargs["file_path"])
        x = f(*args, **kwargs)
        return x
    return wrap


@convert_path_token
def read_data_file(file_path):
    '''Read data from file
    '''
    msg = "{} does not seem to be a file".format(file_path)
    assert os.path.isfile(file_path), msg
    pkr_data = _importData(file_path) or {}
    return pkr_data


@convert_path_token
def write_data_file(file_path, data={}, force=False):
    '''Write data to file

    # kwargs:
    file_path: the file path to write to
    data: the data to write
    f (bool): force write mode, if false, will ask for confirmation when
    overwriting existing files
    '''

    # Ask for confirmation on existing file
    if os.path.exists(file_path) and not force:
        decision = basic.promptAcceptance(pyqt.maya_main_window(),
                                          "File already exists! Overwrite?",
                                          "YOU SURE?")
        if decision in [QtWidgets.QMessageBox.Discard,
                        QtWidgets.QMessageBox.Cancel]:
            return

    # write file
    _exportData(data, file_path)
