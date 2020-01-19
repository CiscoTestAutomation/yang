import json
import re
import traceback
import os.path
from collections import OrderedDict
from yangsuite import get_logger
from ysgnmi.generated.gnmi_pb2 import (
    Encoding, GetRequest, Path, PathElem, SetRequest, Update, TypedValue,
)

log = get_logger(__name__)


class RpcInputError(ValueError):
    """Raised by various jsonbuilder functions on invalid input."""

    def __init__(self, parameter, value, reason):
        self.parameter = parameter
        self.value = value
        self.reason = reason
        super(RpcInputError, self).__init__(str(self))

    def __str__(self):
        return "ERROR: Invalid {0}:\n{1}\n  {2}".format(
            self.parameter, self.value, self.reason)


class JsonPathError(RpcInputError):
    """Exception raised when the JSON path is malformed."""

    def __init__(self, value, reason):
        super(JsonPathError, self).__init__('JSON path', value, reason)


IDENTIFIER_RE = re.compile(
    '''(?:[a-zA-Z_][-a-zA-Z0-9_.]*:)?[a-zA-Z_][-a-zA-Z0-9_.]*''')
"""Regex matching an identifier and its possible prefix in a JSON path.

Matches strings like ``openconfig-interfaces:interfaces`` and
``interface``.
"""

PREDICATE_RE = re.compile(
    r"\[([^=\[\]]+)="    # [key=
    r"(?:"               # one of
    r'"([^"]+)"'         # "double-quoted value"
    r"|"                 # or
    r"'([^']+)'"         # 'single-quoted value'
    r"|"                 # or
    r"concat\((.*)\)"    # concat(...)
    r"|"                 # or
    r"([^\]]+)"          # unquoted value
    r")\]"
)
"""Regex for an JSON path predicate representing a list key and value.

Matches strings like ``[name="foobar"]`` and returns the key and value
(here, ``name`` and ``foobar``) as match subgroups. Note that the key is
always subgroup 1, whereas the value will be subgroup 2 (if double-quoted),
3 (if single-quoted), 4 (if based on concat()), or 5 (if unquoted),
depending on the input.
"""

CONCAT_TOKEN_RE = re.compile(
    r"(?:"               # one of
    r'"([^"]*)"'         # double-quoted string
    r"|"                 # or
    r"'([^']*)'"         # single-quoted string
    r")"
)
"""Regex for a single-quoted or double-quoted string.

Double-quoted strings are returned as match group 1, single-quoted as
match group 2.
"""


def xpath_iterator(xpath):
    """Iterator over an XPath.

    Yields:
      tuple: (token, keys_values, kv_tokens, remaining), such as::

        "oc-if:interfaces", {}, [], "/oc-if:interface[oc-if:name="Eth1"]"
        "oc-if:interface", {'oc-if:name':'"Eth1"'}, ['[oc-if:name="Eth1"]'], ''

    Raises:
      JsonPathError: if the path is invalid in various ways.

    Examples:

      >>> for tok, k_v, kv_tokens, remaining in xpath_iterator(
      ... '/oc-if:interfaces/oc-if:interface[oc-if:name="Et1"]/oc-if:state'):
      ...     print("%s %s %s '%s'" % (tok, dict(k_v), kv_tokens, remaining))
      oc-if:interfaces {} [] '/oc-if:interface[oc-if:name="Et1"]/oc-if:state'
      oc-if:interface {'oc-if:name': 'Et1'} ['[oc-if:name="Et1"]'] \
'/oc-if:state'
      oc-if:state {} [] ''
    """
    path = xpath
    while path:
        if not path.startswith('/'):
            raise JsonPathError(xpath, "expected /... but found {0}"
                                .format(path))
        # Strip leading /
        path = path[1:]

        if not path:
            raise JsonPathError(xpath, "trailing slash")

        # A valid component could be:
        # pfx:localname
        # pfx:localname[key1="value1"]
        # localname[key1="value1:value2"][foo:keyA="valueA"]
        # pfx:localname[key1='"foo/bar"'][foo:keyB=concat("hello","world")]
        #
        # TODO: we do not yet support:
        # pfx:localname[key1="value1" and key2="value2"]
        identifier = IDENTIFIER_RE.match(path)
        if not identifier:
            raise JsonPathError(
                xpath,
                'expected an identifier, '
                'but got "{0}"'
                .format(path))
        token = identifier.group(0)
        path = path[identifier.end():]
        log.debug("  ...minus pfx/localname: %s", path)

        keys_values = OrderedDict()
        kv_tokens = []
        while PREDICATE_RE.match(path):
            # PREDICATE_RE may match as:
            # key, value, '', '', ''
            # key, '', value, '', ''
            # key, '', '', value, ''
            # key, '', '', '', value
            predicate_key_value = PREDICATE_RE.match(path)
            kv_tokens.append(predicate_key_value.group(0))
            predicate_key = predicate_key_value.group(1)
            predicate_value = (predicate_key_value.group(2) or
                               predicate_key_value.group(3))
            if predicate_key_value.group(4) is not None:
                predicate_value = ''.join(
                    ''.join(item) for item in CONCAT_TOKEN_RE.findall(
                        predicate_key_value.group(4)
                    )
                )
            elif predicate_key_value.group(5) is not None:
                candidate_value = predicate_key_value.group(5)
                # Unquoted value might be something other than a string:
                if candidate_value == "true":
                    predicate_value = True
                elif candidate_value == 'false':
                    predicate_value = False
                else:
                    try:
                        predicate_value = int(candidate_value)
                    except:
                        predicate_value = candidate_value

            keys_values[predicate_key] = predicate_value
            path = path[predicate_key_value.end():]
            log.debug("  ...minus keys / values: %s", path)

        if path and not path.startswith('/'):
            raise JsonPathError(xpath, "expected /... but found {0}"
                                .format(path))

        log.debug("%s, %s, %s, %s", token, keys_values, kv_tokens, path)
        yield (token, keys_values, kv_tokens, path)


def convert_xpath_by_origin(xpath, origin, namespace_modules):
    """Convert the given xpath_pfx string to the appropriate origin variant.

    Helper function to :func:`GetRequest_from_jsondata`.

    Args:
      xpath (str): As in yangtree node ``xpath_pfx``.
      origin (str): One of 'openconfig', 'rfc7951', 'legacy'.
      namespace_modules (dict): Mapping of namespace prefix to module name.

    Returns:
      str: Origin-specific path string variant.

    Examples:

      >>> xpath = '/oc-if:interfaces/oc-if:interface[oc-if:name="Eth0"]/\
oc-eth:ethernet/oc-vlan:switched-vlan/oc-vlan:config'
      >>> convert_xpath_by_origin(xpath, "openconfig", {})
      '/interfaces/interface[name="Eth0"]/ethernet/switched-vlan/config'
      >>> convert_xpath_by_origin(xpath, "rfc7951", {
      ... "oc-if": "openconfig-interfaces",
      ... "oc-eth": "openconfig-ethernet",
      ... "oc-vlan": "openconfig-vlan",
      ... })
      '/openconfig-interfaces:interfaces/interface[name="Eth0"]/\
openconfig-ethernet:ethernet/openconfig-vlan:switched-vlan/config'
      >>> convert_xpath_by_origin(xpath, "legacy", {})
      '/oc-if:interfaces/interface[name="Eth0"]/oc-eth:ethernet/\
oc-vlan:switched-vlan/config'
    """
    path = ""
    last_pfx = ""
    for token, _, kv_tokens, _ in xpath_iterator(xpath):
        if ':' in token:
            pfx, localname = token.split(':', 1)
            # Given ['[x:name="foo"]', '[x:num=\'"1"\']'],
            # get   ['[name="foo"]', '[num=\'"1"\']']
            unpfx_tokens = ['[' + kv.split(':', 1)[1] for kv in kv_tokens]
        else:
            pfx = ''
            localname = token
            unpfx_tokens = kv_tokens
        tail = localname + "".join(unpfx_tokens)
        if origin == 'openconfig':
            path += '/' + tail
        elif origin == 'rfc7951':
            if pfx != last_pfx:
                if pfx not in namespace_modules:
                    log.error('Origin RFC 7951 {0} not in namespace'.format(
                        pfx
                    ))
                    continue
                node_mod = namespace_modules[pfx]
                path += '/' + node_mod + ':' + tail
            else:
                path += '/' + tail
        elif origin == 'legacy':
            if pfx != last_pfx:
                path += '/' + pfx + ':' + tail
            else:
                path += '/' + tail
        elif origin == 'none':
            path += '/' + tail
        last_pfx = pfx
    return path


def fixup_xpaths(data, origin):
    """Iterate through the given data and call convert_xpath_by_origin.

    Args:
      data (dict): of form::

        {
          foo: {
            namespace_modules: { ... },
            entries: [ ... ],
          },
          bar: { ... }
        }

      origin (str): One of 'openconfig', 'rfc7951', 'legacy'.

    Returns:
      list: of all converted xpaths
    """
    all_paths = []
    for grouping in data.values():
        for entry in grouping['entries']:
            xpath = entry['xpath']
            path = convert_xpath_by_origin(xpath, origin,
                                           grouping['namespace_modules'])
            all_paths.append(path)
            entry['path'] = path

    return all_paths


def greatest_common_path_prefix(paths):
    """Get the greatest common prefix of the given list of xpaths.

    Args:
      paths (list): Of xpath-like strings

    Returns:
      str: Greatest common prefix.

    Examples::

      >>> paths = ['/interfaces/interface[name="Ethernet0/0"]/state']
      >>> greatest_common_path_prefix(paths)
      '/interfaces/interface[name="Ethernet0/0"]'
      >>> paths.append('/interfaces/interface[name="Ethernet0/0"]/config')
      >>> greatest_common_path_prefix(paths)
      '/interfaces/interface[name="Ethernet0/0"]'
      >>> paths.append('/interfaces/interface[name="Ethernet0/1"]/config')
      >>> greatest_common_path_prefix(paths)
      '/interfaces'
      >>> paths.append('/internet/networks/network')
      >>> greatest_common_path_prefix(paths)
      ''
    """
    initial_guess = os.path.dirname(os.path.commonprefix(paths))
    # initial guess could be:
    # /foo/bar                                  <-- correct
    # /foo/bar[baz="frobozz                     <-- incorrect
    # /foo/bar[baz="frobozz/bar"][boz="frobozz  <-- incorrect
    actual_prefix = ""
    try:
        for token, _, kv_tokens, _ in xpath_iterator(initial_guess):
            actual_prefix += "/" + token + "".join(kv_tokens)
    except JsonPathError:
        # expected, as trailing token is almost certainly invalid
        pass
    return actual_prefix


def origin_for_platform(generic_origin, platform):
    """Translate generic 'origin' string to platform-specific equivalent.

    Args:
      generic_origin (str): One of "openconfig", "rfc7951", "legacy", ""
      platform (str): One of "iosxe", "iosxr".

    Returns:
      str: Platform-appropriate origin string

    Raises:
      ValueError: if either arg is unrecognized, or the combination of args
        is invalid.

    Examples:

      >>> origin_for_platform("rfc7951", "iosxr")
      'yang'
      >>> origin_for_platform("", "iosxe")
      'openconfig'
    """
    if platform == 'iosxe':
        if generic_origin == 'openconfig' or generic_origin == '':
            return 'openconfig'
        elif generic_origin == 'rfc7951':
            return 'rfc7951'
        elif generic_origin == 'legacy':
            return 'legacy'
        else:
            raise ValueError(generic_origin)
    elif platform == 'iosxr':
        if generic_origin == 'openconfig' or generic_origin == '':
            return 'openconfig'
        elif generic_origin == 'rfc7951':
            return 'yang'
        elif generic_origin == 'legacy':
            return ''
        else:
            raise ValueError(generic_origin)
    else:
        raise ValueError(platform)


def Path_from_pathstring(pathstring, origin, platform):
    r"""Convert a JSON path string into a gNMI Path object.

    Args:
      pathstring (str): Path such as '/interfaces/interface[name="Eth0"]'
      origin (str): Value to set on the constructed Path, such as 'openconfig'
      platform (str): One of "iosxe", "iosxr"

    Returns:
      ysgnmi.generated.gnmi_pb2.Path: or None, if pathstring was empty

    Examples:

      >>> path = Path_from_pathstring('/interfaces/interface[name="Eth0"]',
      ...                             "openconfig", "iosxe")
      >>> print(path)
      origin: "openconfig"
      elem {
        name: "interfaces"
      }
      elem {
        name: "interface"
        key {
          key: "name"
          value: "Eth0"
        }
      }
      <BLANKLINE>
      >>> path = Path_from_pathstring('/interfaces/interface[name="Eth0"]',
      ...                             "openconfig", "iosxr")
      >>> print(path)
      origin: "openconfig"
      elem {
        name: "interfaces"
      }
      elem {
        name: "interface"
        key {
          key: "name"
          value: "\"Eth0\""
        }
      }
      <BLANKLINE>
    """
    tokens = []
    for token, keys_values, _, _ in xpath_iterator(pathstring):
        if platform == "iosxr":
            # Work around CSCvk26949 - wrap string values in literal "" chars
            for k in keys_values.keys():
                value = keys_values[k]
                if not (isinstance(value, int) or isinstance(value, bool)):
                    value = '"' + value + '"'
                keys_values[k] = value

        tokens.append(PathElem(name=token, key=keys_values))
    if not tokens:
        return Path()
    result = Path(origin=origin, elem=tokens)
    log.debug("pathstring %s -> Path %s", pathstring, result)
    return result


def GetRequest_from_jsondata(modules, origin, platform, get_type, encoding):
    """Construct a GetRequest object from the given parameters.

    Args:
      modules (dict): with structure::

        {
          'moduleA': {
            namespace_modules: { ... },
            entries: [
              {xpath:, value:, nodetype:, datatype:},
              ...
            ]
          }
        }

      origin (str): One of 'openconfig', 'rfc7951', 'legacy'
      platform (str): One of "iosxe", "iosxr"
      get_type (str): One of "all", TODO
      encoding (str): One of "json_ietf", TODO

    Returns:
      ysgnmi.generated.gnmi_pb2.GetRequest
    """
    all_paths = fixup_xpaths(modules, origin)
    greatest_common_prefix = greatest_common_path_prefix(all_paths)
    if origin != 'none':
        actual_origin = origin_for_platform(origin, platform)
    else:
        actual_origin = None
    prefix_obj = Path_from_pathstring(greatest_common_prefix,
                                      actual_origin, platform)
    # Strip the greatest_common_prefix from the paths
    paths = [p[len(greatest_common_prefix):] for p in all_paths]
    path_objs = [Path_from_pathstring(p, actual_origin, platform)
                 for p in paths]
    get_type_val = GetRequest.DataType.Value(get_type.upper())
    encoding_val = Encoding.Value(encoding.upper())

    return GetRequest(prefix=prefix_obj, path=path_objs,
                      type=get_type_val, encoding=encoding_val)


def SetRequest_from_jsondata(modules, origin, platform):
    """Construct a SetRequest object from the given parameters.

    Args:
      modules (dict): with structure::

        {
          'moduleA': {
            namespace_modules: { ... },
            entries: [
              {xpath:, value:, nodetype:, datatype:, edit-op:},
              ...
            ]
          }
        }

      origin (str): One of 'openconfig', 'rfc7951', 'legacy'
      platform (str): One of "iosxe", "iosxr"

    Returns:
      ysgnmi.generated.gnmi_pb2.SetRequest
    """
    # First, determine the maximal prefix
    all_paths = fixup_xpaths(modules, origin)
    greatest_common_prefix = greatest_common_path_prefix(all_paths)
    actual_origin = origin_for_platform(origin, platform)
    prefix_obj = Path_from_pathstring(greatest_common_prefix,
                                      actual_origin, platform)

    # Now, begin constructing the actual set request
    deletes = []
    replaces = []
    updates = []
    for mod_name, mod_entry in modules.items():
        subtree_op = None
        subtree_prefix = None
        subtree_data = None

        for entry in mod_entry['entries']:
            edit_op = entry.get('edit-op')
            value = entry.get('value')
            path = entry['path'][len(greatest_common_prefix):]
            if edit_op == "delete":
                # Delete this node and any descendants it may have
                # No associated value, just a path
                path_obj = Path_from_pathstring(path, actual_origin, platform)
                deletes.append(path_obj)
            elif edit_op and value is not None:
                # Update/replace on a leaf or leaf-list node
                path_obj = Path_from_pathstring(path, actual_origin, platform)
                # TODO: let value type be user-specified (ascii, json_ietf)
                value_obj = TypedValue(json_val=json.dumps(value).encode())
                update_obj = Update(path=path_obj, val=value_obj)
                if edit_op == 'update':
                    updates.append(update_obj)
                elif edit_op == 'replace':
                    replaces.append(update_obj)
            elif edit_op:
                # Update/replace on a whole subtree
                subtree_op = edit_op
                subtree_prefix = path
                subtree_data = OrderedDict()
            elif subtree_prefix:
                # Subtree items being updated/replaced
                if path.startswith(subtree_prefix):
                    subpath = path[len(subtree_prefix):]
                    subdata = subtree_data
                    for token, kvs, _, remaining in xpath_iterator(subpath):
                        if kvs:
                            # Heading into a dict within a sublist
                            if token not in subdata:
                                subdata[token] = [kvs]
                                subdata = kvs
                            elif remaining:
                                matches = [x for x in subdata[token]
                                           if kvs.items() <= x.items()]
                                if matches:
                                    subdata = matches[0]
                                else:
                                    subdata[token].append(kvs)
                                    subdata = kvs
                            else:
                                log.error("Unexpected!!")
                        else:
                            # Heading directly into a dict
                            if token not in subdata:
                                subdata[token] = OrderedDict()

                            if remaining:
                                subdata = subdata[token]
                            else:
                                subdata[token] = value
                else:
                    # No longer in the subtree
                    log.error("Exited subtree %s by reaching %s",
                              subtree_prefix, path)
                    subtree_op = None
                    subtree_prefix = None
                    subtree_data = None
            else:
                log.error("Value (%s -> %s) without an associated operation",
                          path, value)

        if subtree_data:
            path_obj = Path_from_pathstring(subtree_prefix,
                                            actual_origin, platform)
            # TODO: let value type be user-specified (ascii, json_ietf)
            value_obj = TypedValue(json_val=json.dumps(subtree_data).encode())
            update_obj = Update(path=path_obj, val=value_obj)
            if subtree_op == 'update':
                updates.append(update_obj)
            else:
                replaces.append(update_obj)

    return SetRequest(prefix=prefix_obj,
                      delete=deletes, replace=replaces, update=updates)


def gen_custom_rpc(rpc):
    """Convert RPC XML text into a GNMI request."""
    return {}


edit_op_switcher = {
    'create': 'update',
    'merge': 'update',
    'replace': 'replace',
    'delete': 'delete',
    'remove': 'delete'
}


def gen_gnmi_task(task, request={}):
    """Given a replay task, construct GNMI request with the given options.

    Args:
      task (dict): contains replay data from a stored file (see task.py)
      request (dict):
        -  prefixes (str): Namespace prefix setting
        -  gentype (str): 'basic', 'raw', or 'run'.

    Returns:
      modules (dict): with structure::

        {
          'moduleA': {
            namespace_modules: { ... },
            entries: [
              {xpath:, value:, nodetype:, datatype:, edit-op:},
              ...
            ]
        }
    """
    errors = ''
    requests = []

    # Some APIs send replay inside a dict
    replay = task.get('task', task)

    for seg in replay.get('segments', []):
        try:
            cfgd = seg.get('yang', {})
            if 'rpc' in cfgd:
                # This is an RPC pasted into a replay
                return gen_custom_rpc(cfgd.get('rpc', ''))
            action = 'get_request'
            proto_op = cfgd.get('proto-op', '')
            modules = {}
            model_dict = {}
            namespace_modules = {}

            for model, data in cfgd.get('modules', {}).items():
                configs = data.get('configs', [])
                namespaces = data.get('namespace_prefixes', {})
                entries_list = []

                for prefix, nspace in namespaces.items():
                    module = ''
                    if '/Cisco-IOS-' in nspace:
                        module = nspace[nspace.rfind('/') + 1:]
                    elif '/openconfig.net' in nspace:
                        module = 'openconfig-'
                        module += nspace[nspace.rfind('/') + 1:]
                    elif 'urn:ietf:params:xml:ns:yang:' in nspace:
                        module = nspace.replace(
                            'urn:ietf:params:xml:ns:yang:', '')
                    if module:
                        namespace_modules[prefix] = module

                for entry in configs:
                    xpath = entry.get('xpath', '')
                    value = entry.get('value', '')

                    for pfx, ns in namespace_modules.items():
                        if '="' + pfx + ':' in xpath:
                            xpath = xpath.replace('="' + pfx + ':',
                                                  '="' + ns + ':')
                        if value.startswith(pfx + ':'):
                            value = value.replace(pfx + ':', ns + ':')

                    if not xpath:
                            raise RpcInputError(
                                parameter=proto_op,
                                value=value,
                                reason='Replay conversion missing Xpath'
                            )

                    if proto_op in ['get', 'get-config']:
                        entry_dict = {'xpath': xpath}
                        if value:
                            entry_dict['value'] = value

                    elif proto_op == 'edit-config':
                        action = 'set_request'
                        edit_op = edit_op_switcher.get(
                            entry.get('edit-op', 'merge')
                        )
                        if value:
                            entry_dict = {
                                'xpath': xpath,
                                'value': value,
                                'edit-op': edit_op,
                            }
                        else:
                            entry_dict = {
                                'xpath': xpath
                            }

                    if entry_dict and entry_dict not in entries_list:
                        entries_list.append(entry_dict)

                model_dict = {
                    'namespace_modules': namespace_modules,
                    'entries': entries_list
                }
                modules[model] = model_dict

                requests.append((action, modules))

        except Exception:
            log.error("Failed to gen segment %s", seg['segment'])
            log.debug(traceback.format_exc())
            errors += "Failed to gen segment {0}\n{1}\n".format(
                str(seg['segment']), traceback.format_exc())
            continue

    return requests


if __name__ == "__main__":  # pragma: no cover
    import doctest
    doctest.testmod()
