try:
    from pyats.datastructures import AttrDict
except ImportError:
    class AttrDict:
        pass


class Settings(AttrDict):

    def __init__(self):
        # Default number of lines to log to screen
        self.NETCONF_SCREEN_LOGGING_MAX_LINES = 40
        # Enable XML formatting by default
        self.NETCONF_LOGGING_FORMAT_XML = True
