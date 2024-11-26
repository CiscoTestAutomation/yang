
class Settings(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self
        # Default number of lines to log to screen
        self.NETCONF_SCREEN_LOGGING_MAX_LINES = 40
        # Enable XML formatting by default
        self.NETCONF_LOGGING_FORMAT_XML = True
        # Default receive message length
        self.GRPC_MAX_RECEIVE_MESSAGE_LENGTH = 1000000000
        # Default send message length
        self.GRPC_MAX_SEND_MESSAGE_LENGTH = 1000000000
