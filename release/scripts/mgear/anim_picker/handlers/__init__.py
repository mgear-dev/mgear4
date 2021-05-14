from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals


from . import mode_handlers
from . import maya_handlers

# INIT HANDLERS INSTANCES
__EDIT_MODE__ = mode_handlers.EditMode()
__SELECTION__ = maya_handlers.SelectionCheck()
