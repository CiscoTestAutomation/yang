import os
import re
import json
import logging
from six import string_types
from cisco_gnmi.client import proto

log = logging.getLogger(__name__)


def get_prefix(origin):
    # TODO: calculate a prefix instead of combining config?
    if origin == 'openconfig':
        # No prefix support for openconfig
        return None
    prefix_path = proto.gnmi_pb2.Path()
    return prefix_path


def combine_configs(payload, last_xpath, cfg):
    """Walking from end to finish, 2 xpaths merge, so combine them.
                               |--config
        |---last xpath config--|
    ----|                      |--config
        |
        |   pick these up -->  |--config
        |---this xpath config--|
                               |--config
    Parameters
    ----------
    payload: dict of partial payload
    last_xpath: last xpath that was processed
    xpath: colliding xpath
    config: dict of values associated to colliding xpath
    """
    xpath, config, is_key = cfg
    lp = last_xpath.split("/")
    xp = xpath.split("/")
    base = []
    top = ""
    for i, seg in enumerate(zip(lp, xp)):
        if seg[0] != seg[1]:
            top = seg[1]
            break
    base = "/" + "/".join(xp[i:])
    cfg = (base, config, False)
    extended_payload = {top: xpath_to_json([cfg])}
    payload.update(extended_payload)
    return payload


def xpath_to_json(configs, last_xpath="", payload={}):
    """Try to combine Xpaths/values into a common payload (recursive).

    Parameters
    ----------
    configs: tuple of xpath/value dict
    last_xpath: str of last xpath that was recusivly processed.
    payload: dict being recursively built for JSON transformation.

    Returns
    -------
    dict of combined xpath/value dict.
    """
    for i, cfg in enumerate(configs, 1):
        xpath, config, is_key = cfg
        if last_xpath and xpath not in last_xpath:
            # Branched config here     |---config
            #   |---last xpath config--|
            # --|                      |---config
            #   |---this xpath config
            payload = combine_configs(payload, last_xpath, cfg)
            return xpath_to_json(configs[i:], xpath, payload)
        xpath_segs = xpath.split("/")
        xpath_segs.reverse()
        for seg in xpath_segs:
            if not seg:
                continue
            if payload:
                if is_key:
                    if seg in payload:
                        if isinstance(payload[seg], list):
                            payload[seg].append(config)
                        elif isinstance(payload[seg], dict):
                            payload[seg].update(config)
                    else:
                        payload.update(config)
                        payload = {seg: [payload]}
                else:
                    config.update(payload)
                    payload = {seg: config}
                return xpath_to_json(configs[i:], xpath, payload)
            else:
                if is_key:
                    payload = {seg: [config]}
                else:
                    payload = {seg: config}
                return xpath_to_json(configs[i:], xpath, payload)
    return payload


# Pattern to detect keys in an xpath
RE_FIND_KEYS = re.compile(r"\[.*?\]")


def get_payload(configs):
    """Common Xpaths were detected so try to consolidate them.

    Parameter
    ---------
    configs: list of {xpath: {name: value}} dicts
    """
    # Number of updates are limited so try to consolidate into lists.
    xpaths_cfg = []
    first_key = set()
    # Find first common keys for all xpaths_cfg of collection.
    for config in configs:
        xpath = next(iter(config.keys()))

        # Change configs to tuples (xpath, config) for easier management
        xpaths_cfg.append((xpath, config[xpath]))

        xpath_split = xpath.split("/")
        for seg in xpath_split:
            if "[" in seg:
                first_key.add(seg)
                break

    # Common first key/configs represents one GNMI update
    updates = []
    for key in first_key:
        update = []
        remove_cfg = []
        for config in xpaths_cfg:
            xpath, cfg = config
            if key in xpath:
                update.append(config)
            else:
                for k, v in cfg.items():
                    if '[{0}="{1}"]'.format(k, v) not in key:
                        break
                else:
                    # This cfg sets the first key so we don't need it
                    remove_cfg.append((xpath, cfg))
        if update:
            for upd in update:
                # Remove this config out of main list
                xpaths_cfg.remove(upd)
            for rem_cfg in remove_cfg:
                # Sets a key in update path so remove it
                xpaths_cfg.remove(rem_cfg)
            updates.append(update)
            break

    # Add remaining configs to updates
    if xpaths_cfg:
        updates.append(xpaths_cfg)

    # Combine all xpath configs of each update if possible
    xpaths = []
    compressed_updates = []
    for update in updates:
        xpath_consolidated = {}
        config_compressed = []
        for seg in update:
            xpath, config = seg
            if xpath in xpath_consolidated:
                xpath_consolidated[xpath].update(config)
            else:
                xpath_consolidated[xpath] = config
                config_compressed.append((xpath, xpath_consolidated[xpath]))
                xpaths.append(xpath)

        # Now get the update path for this batch of configs
        common_xpath = os.path.commonprefix(xpaths)
        cfg_compressed = []
        keys = []

        # Need to reverse the configs to build the dict correctly
        config_compressed.reverse()
        compressed_count = 0
        for seg in config_compressed:
            is_key = False
            prepend_path = ""
            xpath, config = seg
            end_path = xpath[len(common_xpath):]
            if not end_path:
                prepend_path = common_xpath
            elif end_path.startswith("["):
                # Don't start payload with a list
                tmp = common_xpath.split("/")
                prepend_path = "/" + tmp.pop()
                common_xpath = "/".join(tmp)
            end_path = prepend_path + end_path

            # Building json, need to identify configs that set keys
            for key in keys:
                if [k for k in config.keys() if k in key]:
                    is_key = True
            keys += re.findall(RE_FIND_KEYS, end_path)
            cfg_compressed.append((end_path, config, is_key))
            compressed_count += 1

        update = (common_xpath, cfg_compressed)
        compressed_updates.append(update)

    updates = []
    if compressed_count == 1:
        common_xpath, cfg = compressed_updates[0]
        xpath, payload, is_key = cfg[0]
        updates.append({xpath: payload})
    else:
        for update in compressed_updates:
            common_xpath, cfgs = update
            payload = xpath_to_json(cfgs)
            updates.append({common_xpath: payload})
    return updates


def xml_path_to_path_elem(request, prefix=False):
    """Convert XML Path Language 1.0 Xpath to gNMI Path/PathElement.

    Modeled after YANG/NETCONF Xpaths.

    References:
    * https://www.w3.org/TR/1999/REC-xpath-19991116/#location-paths
    * https://www.w3.org/TR/1999/REC-xpath-19991116/#path-abbrev
    * https://tools.ietf.org/html/rfc6020#section-6.4
    * https://tools.ietf.org/html/rfc6020#section-9.13
    * https://tools.ietf.org/html/rfc6241

    Parameters
    ---------
    request: dict containing request namespace and nodes to be worked on.
        namespace: dict of <prefix>: <namespace>
        nodes: list of dict
                <xpath>: Xpath pointing to resource
                <value>: value to set resource to
                <edit-op>: equivelant NETCONF edit-config operation

    Returns
    -------
    tuple: namespace_modules, message dict, origin
        namespace_modules: dict of <prefix>: <module name>
            Needed for future support.
        message dict: 4 lists containing possible updates, replaces,
            deletes, or gets derived form input nodes.
        origin str: DME, device, or openconfig
    """

    paths = []
    message = {
        "update": [],
        "replace": [],
        "delete": [],
        "get": [],
    }
    if "nodes" not in request:
        # TODO: raw rpc?
        return paths
    else:
        namespace_modules = {}
        origin = "DME"
        for prefix, nspace in request.get("namespace", {}).items():
            if "/Cisco-IOS-" in nspace:
                module = nspace[nspace.rfind("/") + 1 :]
            elif "/cisco-nx" in nspace:  # NXOS lowercases namespace
                module = "Cisco-NX-OS-device"
            elif "/openconfig.net" in nspace:
                module = "openconfig-"
                module += nspace[nspace.rfind("/") + 1 :]
            elif "urn:ietf:params:xml:ns:yang:" in nspace:
                module = nspace.replace("urn:ietf:params:xml:ns:yang:", "")
            if module:
                namespace_modules[prefix] = module

        for node in request.get("nodes", []):
            if "xpath" not in node:
                log.error("Xpath is not in message")
            else:
                xpath = node["xpath"]
                value = node.get("value", "")
                edit_op = node.get("edit-op", "")

                for pfx, mod in namespace_modules.items():
                    if pfx not in xpath:
                        continue
                    if "Cisco-IOS-" in mod:
                        origin = 'rfc7951'
                        mod += ":"
                    elif 'openconfig' in mod:
                        origin = 'openconfig'
                        mod = ''
                    elif 'Cisco-NX-OS' in mod:
                        origin = 'device'
                        mod = ''
                    # Adjust prefixes of xpaths
                    xpath = xpath.replace(pfx + ":", mod)
                    if isinstance(value, string_types):
                        value = value.replace(pfx + ":", mod)

                if edit_op:
                    if edit_op in ["create", "merge", "replace"]:
                        xpath_lst = xpath.split("/")
                        name = xpath_lst.pop()
                        xpath = "/".join(xpath_lst)
                        if edit_op == "replace":
                            if not message["replace"]:
                                message["replace"] = [{xpath: {name: value}}]
                            else:
                                message["replace"].append({xpath: {name: value}})
                        else:
                            if not message["update"]:
                                message["update"] = [{xpath: {name: value}}]
                            else:
                                message["update"].append({xpath: {name: value}})
                    elif edit_op in ["delete", "remove"]:
                        if message["delete"]:
                            message["delete"].add(xpath)
                        else:
                            message["delete"] = set(xpath)
                else:
                    message["get"].append(xpath)
    return namespace_modules, message, origin


if __name__ == "__main__":
    from pprint import pprint as pp

    request = {
        "namespace": {"oc-acl": "http://openconfig.net/yang/acl"},
        "nodes": [
            {
                "value": "testacl",
                "xpath": "/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set/name",
                "edit-op": "merge",
            },
            {
                "value": "ACL_IPV4",
                "xpath": "/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set/type",
                "edit-op": "merge",
            },
            {
                "value": "10",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry/oc-acl:sequence-id',
                "edit-op": "merge",
            },
            {
                "value": "20.20.20.1/32",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:destination-address',
                "edit-op": "merge",
            },
            {
                "value": "IP_TCP",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:protocol',
                "edit-op": "merge",
            },
            {
                "value": "10.10.10.10/32",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:source-address',
                "edit-op": "merge",
            },
            {
                "value": "DROP",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:actions/oc-acl:config/oc-acl:forwarding-action',
                "edit-op": "merge",
            },
        ],
    }
    modules, message, origin = xml_path_to_path_elem(request)
    pp(modules)
    pp(message)
    pp(origin)
    """
    # Expected output
    =================
    {'oc-acl': 'openconfig-acl'}
    {'delete': [],
    'get': [],
    'replace': [],
    'update': [{'/acl/acl-sets/acl-set': {'name': 'testacl'}},
                {'/acl/acl-sets/acl-set': {'type': 'ACL_IPV4'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry': {'sequence-id': '10'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'destination-address': '20.20.20.1/32'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'protocol': 'IP_TCP'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'source-address': '10.10.10.10/32'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/actions/config': {'forwarding-action': 'DROP'}}]}
    'openconfig'
    """
