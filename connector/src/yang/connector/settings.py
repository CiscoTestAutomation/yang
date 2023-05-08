
class Settings(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self
        # Default number of lines to log to screen
        self.NETCONF_SCREEN_LOGGING_MAX_LINES = 40
        # Enable XML formatting by default
        self.NETCONF_LOGGING_FORMAT_XML = True

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                        super(AttrDict, self).__repr__())

