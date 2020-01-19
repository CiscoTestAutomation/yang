import traceback
import os
from collections import OrderedDict

from grpc._channel import _Rendezvous
from google.protobuf.json_format import MessageToDict
from .generated.gnmi_pb2_grpc import gNMIStub
from .generated.gnmi_pb2 import CapabilityRequest
import grpc

try:
    from pyats.connections import BaseConnection
except ImportError:
    try:
        from ats.connections import BaseConnection
    except ImportError:
        raise ImportError('Cannot import pyATS - make sure pyATS is installed ' 
                          'in your environment') from None
try:
    from pyats.utils.secret_strings import to_plaintext
except ImportError:
    def to_plaintext(string):
        return(str(string))

# try to record usage statistics
#  - only internal cisco users will have stats.CesMonitor module
#  - below code does nothing for DevNet users -  we DO NOT track usage stats
#    for PyPI/public/customer users
try:
    # new internal cisco-only pkg since devnet release
    from ats.cisco.stats import CesMonitor
except Exception:
    try:
        # legacy pyats version, stats was inside utils module
        from ats.utils.stats import CesMonitor
    except Exception:
        CesMonitor = None
finally:
    if CesMonitor is not None:
        # CesMonitor exists -> this is an internal cisco user
        CesMonitor(action = __name__, application='pyATS Packages').post()


# create a logger for this module
logger = logging.getLogger(__name__)


class GnmiSession:
    """Session handling for gNMI connections."""

    instances = {}

    @classmethod
    def get(cls, key, user, custom_log=None):
        """Retrieve or create a GNMI session instance.

        The key can be a string or a device profile.

        Args:
          key (str): Device name or uses the base.profile_name as key.
        Returns:
          GnmiSession
        """
        # accept device name or profile
        if not isinstance(key, YSDeviceProfile):
            dev_profile = YSDeviceProfile.get(key)
        else:
            dev_profile = key
            key = dev_profile.base.profile_name

        if key not in cls.instances:
            if dev_profile.gnmi.enabled:
                cls.instances[key] = cls(key, user, custom_log)
            else:
                raise ValueError("gNMI not enabled in device profile")

        return cls.instances[key]

    @classmethod
    def destroy(cls, key):
        """Remove the session instance from the cache.

        The key can be a string or a device profile.

        Args:
          key (str): Device name or uses the base.profile_name as key.
        """
        if isinstance(key, YSDeviceProfile):
            key = key.base.profile_name

        if key in cls.instances:
            session = cls.instances[key]
            if session.connected:
                session.disconnect()
            del cls.instances[key]

    def __init__(self, key, user, custom_log=None):
        self.key = key
        self.dev_profile = YSDeviceProfile.get(key)
        self.creds = None
        self.channel = None
        self.stub = None
        if custom_log:
            self.log = custom_log
        else:
            # Adding yangsuite logger
            self.log = log

        certificate = None

        if self.dev_profile.gnmi.secure:
            if hasattr(self.dev_profile.base, 'certificate'):
                certificate = self.dev_profile.base.certificate

        if user and certificate:
            user_device_path = get_path('user_devices_dir',
                                        user=user)
            if os.path.isfile(
                os.path.join(user_device_path,
                             self.dev_profile.base.profile_name,
                             certificate)):
                with open(
                    os.path.join(user_device_path,
                                 self.dev_profile.base.profile_name,
                                 certificate), 'rb') as fd:
                    self.creds = grpc.ssl_channel_credentials(fd.read())
            else:
                self.log.error("{0} certificate not found".format(
                    certificate
                ))
                self.log.info("Trying insecure channel")

        self.metadata = [
            ('username', self.dev_profile.base.username),
            ('password', self.dev_profile.base.password),
        ]
        self.timeout = self.dev_profile.base.timeout
        self.connect()

    @property
    def connected(self):
        """Return True if session is connected."""
        return self.channel

    def send_config(self, cmd, lock_retry=30):
        """Send any Set data command.

        Args:
          cmd (str): Configuration CLI command.
        Returns:
          (str): CLI response
        """
        if not self.connected:
            self.connect()
        try:
            response = self.stub.Set(cmd, self.timeout, self.metadata)
            request_dict = MessageToDict(response,
                                         preserving_proto_field_name=True)
            # Not generally needed for SetResponse, but let's be cautious:
            gnmi.fixup_json_val_from_base64_recursive(request_dict)
            return request_dict
        except grpc.RpcError as exe:
            # if "Database is locked" in exe.details() and lock_retry:
            #     time.sleep(1)
            #     self.log.info(
            #         'gNMI: Datastore is locked, retrying {0}'.format(
            #             str(lock_retry)
            #         )
            #     )
            #     self.send_config(cmd, lock_retry-1)
            self.log.error('{0}: {1}'.format(exe.code(), exe.details()))
            raise Exception('{0}: {1}'.format(exe.code(), exe.details()))

    def send_exec(self, cmd):
        """Send any Get data commmand.

        Args:
          cmd (str): Configuration CLI command.
        Returns:
          (str): CLI response
        """
        if not self.connected:
            self.connect()
        response = self.stub.Get(cmd, self.timeout, self.metadata)
        request_dict = MessageToDict(response,
                                     preserving_proto_field_name=True)
        gnmi.fixup_json_val_from_base64_recursive(request_dict)
        return request_dict

    def get_capabilities(self, request):
        """Retrieve capabilities from device."""
        if not self.connected:
            self.connect()
        return self.stub.Capabilities(request, self.timeout, self.metadata)

    def connect(self):
        """Connect to gRPC device."""
        if not self.connected:
            if self.creds:
                self.channel = grpc.secure_channel("{0}:{1}".format(
                    self.dev_profile.base.address,
                    self.dev_profile.gnmi.port),
                    self.creds,
                    (
                        ('grpc.ssl_target_name_override',
                         self.dev_profile.base.profile_name,),
                    )
                )
            else:
                self.channel = grpc.insecure_channel("{0}:{1}".format(
                    self.dev_profile.base.address,
                    self.dev_profile.gnmi.port)
                )

            self.stub = gNMIStub(self.channel)

    def disconnect(self):
        """Disconnect from SSH device."""
        if self.connected:
            self.channel.close()
            self.stub = None

    def __enter__(self):
        """Establish a session using a Context Manager."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Gracefully close connection on Context Manager exit."""
        self.disconnect()
