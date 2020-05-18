import re
import json
import logging
from lxml import etree
from copy import deepcopy
from xmljson import Parker
from ncclient import xml_
from xml.etree import ElementTree
from collections import OrderedDict, defaultdict

from .errors import ModelError
from .composer import Tag, Composer
from .calculator import BaseCalculator
from cisco_gnmi.proto.gnmi_pb2 import PathElem, Path, SetRequest, TypedValue, Update

# create a logger for this module
logger = logging.getLogger(__name__)

nc_url = xml_.BASE_NS_1_0
config_tag = '{' + nc_url + '}config'
ns_spec = {
    'legacy': {
        'path': Tag.JSON_PREFIX,
        'val_name': Tag.JSON_NAME,
        'val_val': Tag.JSON_PREFIX,
        },
    'rfc7951': {
        'path': Tag.JSON_NAME,
        'val_name': Tag.JSON_NAME,
        'val_val': Tag.JSON_NAME,
        },
    'openconfig': {
        'path': Tag.JSON_NAME,
        'val_name': Tag.JSON_NAME,
        'val_val': Tag.JSON_NAME,
        },
    '': {
        'path': Tag.JSON_NAME,
        'val_name': Tag.JSON_NAME,
        'val_val': Tag.JSON_NAME,
        },
    }


def _tostring(value):
    '''_tostring

    Convert value to XML compatible string.
    '''

    if value is True:
        return 'true'
    elif value is False:
        return 'false'
    elif value is None:
        return None
    else:
        return str(value)

def _fromstring(value):
    '''_fromstring

    Convert XML string value to None, boolean, int or float.
    '''

    if not value:
        return None
    std_value = value.strip().lower()
    if std_value == 'true':
        return 'true'
    elif std_value == 'false':
        return 'false'
#     try:
#         return int(std_value)
#     except ValueError:
#         pass
#     try:
#         return float(std_value)
#     except ValueError:
#         pass
    return value


class gNMIParser(object):
    '''gNMIParser

    A parser to convert a gNMI GetResponse to an lxml Element object. gNMI
    specification can be found at
    https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md

    Attributes
    ----------
    ele : `Element`
        An lxml Element object which is the root of the config tree.

    config_nodes : `list`
        A list of config nodes. Each config node is an Element node in the
        config tree, which is corresponding to one 'update' in the gNMI
        GetResponse.

    xpaths : `list`
        A list of strings. Each string is an xpath of an Element node in the
        config tree, which is corresponding to one 'update' in the gNMI
        GetResponse.
    '''

    def __init__(self, device, gnmi_get_reply):
        self.device = device
        self.reply = gnmi_get_reply
        self._config_nodes = None
        self._ele = None
        self._convert_tag = defaultdict(dict)

        self._prefix_to_name = {i[1]: i[0] for i in self.device.namespaces
                                if i[1] is not None}
        self._prefix_to_url = {i[1]: i[2] for i in self.device.namespaces
                               if i[1] is not None}

    @property
    def ele(self):
        if self._ele is None:
            self._ele = self.config_nodes.ele
        return self._ele

    @property
    def config_nodes(self):
        if self._config_nodes is None:
            self._config_nodes = self.get_config_nodes()
        return self._config_nodes

    @property
    def xpaths(self):
        xpaths = []
        if len(self.config_nodes) > 0 and len(self.config_nodes[0]) > 0:
            if len(self.config_nodes[0]) > 1:
                xpaths.append(self.device.get_xpath(self.config_nodes[0][0],
                                                    type=Tag.LXML_XPATH,
                                                    instance=False))
            else:
                xpaths.append(self.device.get_xpath(self.config_nodes[0][0],
                                                    type=Tag.LXML_XPATH,
                                                    instance=True))
        return xpaths

    def parse_value(self, origin, value, tag):

        def convert_xml_to_lxml(xml_element, lxml_parent=None, default_ns=''):
            ns_name, tag = self.convert_tag(default_ns, xml_element.tag,
                                            src=ns_spec[origin]['val_name'],
                                            dst=Tag.LXML_ETREE)
            val_name_ns_tuple = self.convert_ns(ns_name,
                                                src=ns_spec[origin]['val_name'][0])
            nsmap = {None: val_name_ns_tuple[Tag.NAMESPACE]}
            val_name_ns = val_name_ns_tuple[ns_spec[origin]['val_val'][0]]
            if xml_element.text is not None:
                ns_val, text = self.convert_tag(val_name_ns, xml_element.text,
                                                src=ns_spec[origin]['val_val'],
                                                dst=Tag.JSON_PREFIX)
                if ns_val != val_name_ns:
                    v_v_ns = self.convert_ns(ns_val,
                                             src=ns_spec[origin]['val_val'][0])
                    v_v_prefix = v_v_ns[Tag.PREFIX]
                    v_v_url = v_v_ns[Tag.NAMESPACE]
                    nsmap[v_v_prefix] = v_v_url
            if lxml_parent is None:
                lxml_element = etree.Element(tag, nsmap=nsmap)
            else:
                lxml_element = etree.SubElement(lxml_parent, tag, nsmap=nsmap)
            if xml_element.text is not None:
                lxml_element.text = text
            for xml_child in xml_element:
                convert_xml_to_lxml(xml_child,
                                    lxml_parent=lxml_element,
                                    default_ns=ns_name)
            return lxml_element

        n, t = self.convert_tag('', tag,
                                src=Tag.LXML_ETREE,
                                dst=ns_spec[origin]['val_name'])
        json_val_str = '{{"{}": {}}}'.format(t, value.json_ietf_val.decode())
        json_data = json.loads(json_val_str, object_pairs_hook=OrderedDict)
        pk = Parker(xml_tostring=_tostring, element=ElementTree.Element)
        return [convert_xml_to_lxml(i) for i in pk.etree(json_data)]

    @staticmethod
    def parse_tag(tag):
        ret = re.search('^{(.+)}(.+)$', tag)
        if ret:
            return ret.group(1), ret.group(2)
        else:
            raise ModelError("tag '{}' does not have URL info" \
                             .format(tag))

    def convert_tag(self, default_ns, tag, src=Tag.LXML_ETREE, dst=Tag.YTOOL):
        if src == Tag.JSON_NAME and dst == Tag.LXML_ETREE:
            if default_ns not in self._convert_tag or \
               tag not in self._convert_tag[default_ns]:
                self._convert_tag[default_ns][tag] = \
                    self.device.convert_tag(default_ns, tag, src=src, dst=dst)
            return self._convert_tag[default_ns][tag]
        else:
            return self.device.convert_tag(default_ns, tag, src=src, dst=dst)

    def convert_ns(self, ns, src=Tag.NAME):
        entries = [i for i in self.device.namespaces if i[src] == ns]
        c = len(entries)
        if c == 0:
            raise ConfigError("{} '{}' does not exist in device attribute " \
                              "'namespaces'" \
                              .format(Tag.STR[src], ns))
        if c > 1:
            raise ModelError("device has more than one {} '{}': {}" \
                             .format(Tag.STR[src], ns, entries))
        return entries[0]

    def get_config_nodes(self):
        '''get_config_nodes

        High-level api: get_config_nodes returns a list of config nodes. Each
        config node is an Element node in the config tree, which is
        corresponding to one 'update' in the gNMI GetResponse.

        Returns
        -------

        list
            A list of config nodes.
        Config
            A Config object.
        '''

        from .config import Config

        config = Config(self.device, config=None)
        for notification in self.reply.notification:
            updates = []
            for update in notification.update:
                config += self.build_config_node(Config(self.device, config=None),
                                                 notification.prefix,
                                                 update.path, update.val)
        return config

    def get_schema_node(self, parent_schema_node, tag, origin=''):

        def is_parent(node1, node2):
            ancestors = {id(a): a for a in node2.iterancestors()}
            ids_1 = set([id(a) for a in node1.iterancestors()])
            ids_2 = set([id(a) for a in node2.iterancestors()])
            if not ids_1 < ids_2:
                return False
            for i in ids_2 - ids_1:
                if ancestors[i] is not node1 and \
                   ancestors[i].attrib['type'] != 'choice' and \
                   ancestors[i].attrib['type'] != 'case':
                    return False
            return True

        def get_root(tag):
            if origin == 'openconfig' or origin == '':
                models = [m for m in self.device.models_loaded
                                       if m[:10] == 'openconfig']
            else:
                models = self.device.models_loaded
            roots = {}
            for m in models:
                root = get_child(tag, parent=self.device.models[m].tree)
                if root is not None:
                    roots[m] = root
            if len(roots) == 1:
                return list(roots.values())[0]
            elif len(roots) > 1:
                if origin == 'openconfig' or origin == '':
                    tag = self.parse_tag(tag)[1]
                raise ModelError("more than one models have root with tag " \
                                 "'{}': {}" \
                                 .format(tag, ', '.join(roots.keys())))
            else:
                return None

        def get_child(tag, parent):
            if origin == 'openconfig' or origin == '':
                children = [i for i in parent.iterdescendants() \
                              if self.parse_tag(i.tag)[1] == tag and \
                                 i.get('type') != 'choice' and \
                                 i.get('type') != 'case' and \
                                 is_parent(parent, i)]
            else:
                children = [i for i in parent.iterdescendants() \
                              if i.tag == tag and \
                                 i.get('type') != 'choice' and \
                                 i.get('type') != 'case' and \
                                 is_parent(parent, i)]
            if len(children) == 1:
                return children[0]
            elif len(children) > 1:
                if parent.getparent() is None:
                    raise ModelError("model {} has more than one root with " \
                                     "tag '{}'" \
                                     .format(parent.tag, tag))
                else:
                    raise ModelError("node {} has more than one child with " \
                                     "tag '{}'" \
                                     .format(self.device.get_xpath(parent),
                                             tag))
            else:
                return None

        # search roots
        if parent_schema_node is None:
            child = get_root(tag)
            if child is None:
                raise ConfigError("root '{}' cannot be found in loaded models" \
                                  .format(tag))
            else:
                return child

        # search from a parent
        child = get_child(tag, parent_schema_node)
        if child is None:
            raise ConfigError("node {} does not have child with tag '{}'" \
                              .format(self.device.get_xpath(parent_schema_node),
                                      tag))
        else:
            return child

    def build_config_node_per_elem(self, origin, parent_config_node, path_elem,
                                   value=None):

        def cleanup_and_append(origin, parent_config_node, child_schema_node,
                               value):
            for n in parent_config_node.findall(child_schema_node.tag):
                parent_config_node.remove(n)
            for n in self.parse_value(origin, value, child_schema_node.tag):
                parent_config_node.append(n)
            return None

        if parent_config_node.tag == config_tag:
            parent_schema_node = None
            parent_ns = ''
        else:
            parent_schema_node = self.device.get_schema_node(parent_config_node)
            parent_url, parent_tag_name = self.parse_tag(parent_config_node.tag)
            parent_ns_tuple = self.convert_ns(parent_url, src=Tag.LXML_ETREE[0])
            parent_ns = parent_ns_tuple[ns_spec[origin]['path'][0]]
        if origin == 'openconfig' or origin == '':
            child_schema_node = self.get_schema_node(parent_schema_node,
                                                     path_elem.name,
                                                     origin=origin)
        else:
            child_ns, child_tag = self.convert_tag(parent_ns, path_elem.name,
                                                   src=ns_spec[origin]['path'],
                                                   dst=Tag.LXML_ETREE)
            child_schema_node = self.get_schema_node(parent_schema_node,
                                                     child_tag,
                                                     origin=origin)
        type = child_schema_node.get('type')
        if type == 'leaf' or type == 'leaf-list':
            if value is None:
                raise ConfigError("node {} does not have value" \
                                  .format(self.device.get_xpath(child_schema_node)))
            else:
                return cleanup_and_append(origin, parent_config_node,
                                          child_schema_node, value)
        elif type == 'container':
            if value is None:
                match = parent_config_node.find(child_schema_node.tag)
                if match is not None:
                    return match
                else:
                    return self.subelement(origin,
                                           parent_config_node,
                                           child_schema_node.tag)
            else:
                return cleanup_and_append(origin, parent_config_node,
                                          child_schema_node, value)
        elif type == 'list':
            if value is None:
                instance = self.find_instance(origin,
                                              parent_config_node,
                                              child_schema_node,
                                              path_elem.key)
                if instance is not None:
                    return instance
                else:
                    return self.subelement(origin,
                                           parent_config_node,
                                           child_schema_node.tag,
                                           key=path_elem.key)
            else:
                return cleanup_and_append(origin, parent_config_node,
                                          child_schema_node, value)
        else:
            raise ModelError("type of node {} is unknown: '{}'" \
                              .format(self.device.get_xpath(parent_schema_node),
                                      type))

    def build_config_node(self, config, prefix, path, value):
        from .config import Config

        config_node = config.ele
        absolute_path = list(prefix.elem) + list(path.elem)
        for index, elem in enumerate(absolute_path):
            if index == len(path.elem) - 1:
                config_saved = Config(self.device, config=deepcopy(config.ele))
                config_node = self.build_config_node_per_elem(path.origin,
                                                              config_node,
                                                              elem,
                                                              value=value)
                return config_saved + config
            else:
                config_node = self.build_config_node_per_elem(path.origin,
                                                              config_node,
                                                              elem)

    def find_instance(self, origin, parent_config_node, child_schema_node, key):

        def find_key(config_node, key_tag, key_text):
            match = config_node.find(key_tag)
            if match is None:
                return False
            if match.text != key_text:
                return False
            return True

        def find_keys(config_node, key_tuple):
            for key_tag, nsmap, key_text in key_tuple:
                if not find_key(config_node, key_tag, key_text):
                    return False
            return True

        keys = child_schema_node.get('key').split()
        if len(keys) != len(key):
            raise ConfigError("node {} has {} keys in Path object, but the " \
                              "schema node requires {} keys: {}" \
                              .format(self.device.get_xpath(child_schema_node),
                                      len(key), len(keys), ', '.join(keys)))
        key_tuple = self.parse_key(origin, child_schema_node.tag, key)
        for key_tag, nsmap, text in key_tuple:
            url, tag_name = self.parse_tag(key_tag)
            if tag_name not in keys:
                raise ConfigError("node {} does not have key {}" \
                                  .format(self.device.get_xpath(child_schema_node),
                                          key_tag))
        for child in parent_config_node.findall(child_schema_node.tag):
            if find_keys(child, key_tuple):
                return child
        return None

    def get_prefix(self, text):
        if text is None:
            return '', None
        m = re.search('^(.*):(.*)$', text)
        if m:
            if m.group(1) in self._prefix_to_name:
                return m.group(1), m.group(2)
            else:
                return '', text
        else:
            return '', text

    def parse_key(self, origin, tag, key):
        url, tag_name = self.parse_tag(tag)
        text_ns_tuple = self.convert_ns(url, src=Tag.NAMESPACE)
        default_ns = text_ns_tuple[ns_spec[origin]['path'][0]]

        ret = []
        for k, v in key.items():
            tag_ns, key_tag = self.convert_tag(default_ns, k,
                                               src=ns_spec[origin]['path'],
                                               dst=Tag.LXML_ETREE)
            text_ns, text = self.convert_tag(tag_ns, v,
                                             src=ns_spec[origin]['path'],
                                             dst=Tag.XPATH)
            text_ns_tuple = self.convert_ns(tag_ns,
                                            src=ns_spec[origin]['path'][0])
            nsmap = {None: text_ns_tuple[Tag.NAMESPACE]}
            if text_ns != tag_ns:
                text_ns_tuple = self.convert_ns(text_ns,
                                                src=ns_spec[origin]['path'][0])
                nsmap[text_ns_tuple[Tag.PREFIX]] = text_ns_tuple[Tag.NAMESPACE]
            ret.append((key_tag, nsmap, text))
        return ret

    def subelement(self, origin, parent, tag, key={}):
        url, tag_name = self.parse_tag(tag)
        e = etree.SubElement(parent, tag, nsmap={None: url})
        default_ns_tuple = self.convert_ns(url, src=Tag.NAMESPACE)
        default_ns = default_ns_tuple[ns_spec[origin]['path'][0]]
        if key:
            for key_tag, nsmap, text in self.parse_key(origin, tag, key):
                e_child = etree.SubElement(e, key_tag, nsmap=nsmap)
                e_child.text = text
        return e


class gNMIComposer(Composer):
    '''gNMIComposer

    A composer to convert an lxml Element object to gNMI JSON format. gNMI
    adopts RFC 7951 when encoding data. One gNMIComposer instance abstracts
    a config node in config tree.
    '''

    def __init__(self, *args, **kwargs):
        super(gNMIComposer, self).__init__(*args, **kwargs)
        self._url_to_prefix = {i[2]: i[1] for i in self.device.namespaces
                               if i[1] is not None}

    def get_json(self, instance=True, origin='openconfig'):
        '''get_json

        High-level api: get_json returns json_val of the config node.

        Parameters
        ----------

        instance : `bool`
            True if only one instance of list or leaf-list is required. False if
            all instances of list or leaf-list are needed.

        Returns
        -------

        str
            A string in JSON format.
        '''

        def get_json_instance(node):
            pk = Parker(xml_fromstring=_fromstring, dict_type=OrderedDict)
            default_ns = {}
            for item in node.iter():
                parents = [p for p in node.iter() if item in p]
                if parents and id(parents[0]) in default_ns:
                    ns, tag = self.device.convert_tag(default_ns[id(parents[0])],
                                                      item.tag,
                                                      dst=ns_spec[origin]['val_name'])
                else:
                    ns, tag = self.device.convert_tag('',
                                                      item.tag,
                                                      dst=ns_spec[origin]['val_name'])
                default_ns[id(item)] = ns
                item.tag = tag
                if item.text:
                    text = self.device.convert_tag(self._url_to_prefix[ns],
                                                   item.text,
                                                   src=Tag.JSON_PREFIX,
                                                   dst=ns_spec[origin]['val_val'])[1]
                    item.text = text
            return pk.data(node)

        def convert_node(node):
            # lxml.etree does not allow tag name like oc-if:enable
            # so it is converted to xml.etree.ElementTree
            string = etree.tostring(node, encoding='unicode',
                                    pretty_print=False)
            return ElementTree.fromstring(string)

        if instance:
            return json.dumps(get_json_instance(convert_node(self.node)))
        else:
            nodes = [n for n in
                     self.node.getparent().iterchildren(tag=self.node.tag)]
            if len(nodes) > 1:
                return json.dumps([get_json_instance(convert_node(n))
                                   for n in nodes])
            else:
                return json.dumps(get_json_instance(convert_node(nodes[0])))

    def get_path(self, instance=True, origin='openconfig'):
        '''get_path

        High-level api: get_path returns gNMI path object of the config node.
        Note that gNMI Path can specify list instance but cannot specify
        leaf-list instance.

        Parameters
        ----------

        instance : `bool`
            True if the gNMI Path object refers to only one instance of a list.
            False if the gNMI Path object refers to all instances of a list.

        Returns
        -------

        Path
            An object of gNMI Path class.
        '''

        def get_name(node, default_ns):
            if origin == 'openconfig' or origin == '':
                return gNMIParser.parse_tag(node.tag)
            else:
                return self.device.convert_tag(default_ns,
                                               node.tag,
                                               src=Tag.LXML_ETREE,
                                               dst=ns_spec[origin]['path'])

        def get_keys(node, default_ns):
            keys = Composer(self.device, node).keys
            ret = {}
            for key in keys:
                if origin=='openconfig' or origin == '':
                    key_ns, key_val = gNMIParser.parse_tag(key)
                else:
                    key_ns, key_val = self.device.convert_tag(default_ns,
                                                              key,
                                                              src=Tag.LXML_ETREE,
                                                              dst=ns_spec[origin]['path'])
                ns_tuple = self.convert_ns(key_ns, src=Tag.NAMESPACE)
                val_ns, val_val = self.device.convert_tag(ns_tuple[Tag.PREFIX],
                                                          node.find(key).text,
                                                          src=Tag.XPATH,
                                                          dst=ns_spec[origin]['path'])
                ret[key_val] = val_val
            return ret

        def get_pathelem(node, default_ns):
            ns, name = get_name(node, default_ns)
            schema_node = self.device.get_schema_node(node)
            if schema_node.get('type') == 'list' and \
               (node != self.node or instance):
                return ns, PathElem(name=name, key=get_keys(node, ns))
            else:
                return ns, PathElem(name=name)

        nodes = list(reversed(list(self.node.iterancestors())))[1:] + \
                [self.node]
        path_elems = []
        default_ns = ''
        for node in nodes:
            default_ns, path_elem = get_pathelem(node, default_ns)
            path_elems.append(path_elem)
        return Path(elem=path_elems, origin=origin)

    def convert_ns(self, ns, src=Tag.NAME):
        entries = [i for i in self.device.namespaces if i[src] == ns]
        c = len(entries)
        if c == 0:
            raise ConfigError("{} '{}' does not exist in device attribute " \
                              "'namespaces'" \
                              .format(Tag.STR[src], ns))
        if c > 1:
            raise ModelError("device has more than one {} '{}': {}" \
                             .format(Tag.STR[src], ns, entries))
        return entries[0]


class gNMICalculator(BaseCalculator):
    '''gNMICalculator

    A gNMI calculator to do subtraction and addition. A subtraction is to
    compute the delta between two Config instances in a form of gNMI SetRequest.
    An addition is to apply one gNMI SetRequest to a Config instance (TBD).

    Attributes
    ----------
    sub : `SetRequest`
        A gNMI SetRequest which can achieve a transition from one config, i.e.,
        self.etree2, to another config, i.e., self.etree1.
    '''

    @property
    def sub(self):
        deletes, replaces, updates = self.node_sub(self.etree1, self.etree2)
        return SetRequest(prefix=None,
                          delete=deletes,
                          replace=replaces,
                          update=updates)

    def node_sub(self, node_self, node_other):
        '''node_sub

        High-level api: Compute the delta of two config nodes. This method is
        recursive, assuming two config nodes are different.

        Parameters
        ----------

        node_self : `Element`
            A config node in the destination config that is being processed.
            node_self cannot be a leaf node.

        node_other : `Element`
            A config node in the source config that is being processed.

        Returns
        -------

        tuple
            There are three elements in the tuple: a list of gNMI Path
            instances that need to be deleted, a list of gNMI Update instances
            for replacement purpose, and a list of gNMI Update instances for
            merging purpose.
        '''

        paths_delete = []
        updates_replace = []
        updates_update = []
        done_list = []

        # if a leaf-list node, delete the leaf-list totally
        # if a list node, by default delete the list instance
        # if a list node and delete_whole=True, delete the list totally
        def generate_delete(node, instance=True):
            paths_delete.append(gNMIComposer(self.device, node) \
                        .get_path(instance=instance))

        # if a leaf-list node, replace the leaf-list totally
        # if a list node, replace the list totally
        def generate_replace(node, instance=True):
            n = gNMIComposer(self.device, node)
            json_value = n.get_json(instance=instance).encode()
            value = TypedValue(json_val=json_value)
            path = n.get_path(instance=instance)
            updates_replace.append(Update(path=path, val=value))

        # if a leaf-list node, update the leaf-list totally
        # if a list node, by default update the list instance
        # if a list node and update_whole=True, update the list totally
        def generate_update(node, instance=True):
            n = gNMIComposer(self.device, node)
            json_value = n.get_json(instance=instance).encode()
            value = TypedValue(json_val=json_value)
            path = n.get_path(instance=instance)
            updates_update.append(Update(path=path, val=value))

        # the leaf-list value sequence under node_self is different from the one
        # under node_other
        def leaf_list_seq_is_different(tag):
            if [i.text for i in node_self.iterchildren(tag=tag)] == \
               [i.text for i in node_other.iterchildren(tag=tag)]:
                return False
            else:
                return True

        # the leaf-list value set under node_self is different from the one
        # under node_other
        def leaf_list_set_is_different(tag):
            s_list = [i.text for i in node_self.iterchildren(tag=tag)]
            o_list = [i.text for i in node_other.iterchildren(tag=tag)]
            if set(s_list) == set(o_list):
                return False
            else:
                return True

        # the leaf-list or list under node_self is empty
        def list_is_empty(tag):
            if [i for i in node_self.iterchildren(tag=tag)]:
                return False
            else:
                return True

        # the sequence of list instances under node_self is different from the
        # one under node_other
        def list_seq_is_different(tag):
            s_list = [i for i in node_self.iterchildren(tag=tag)]
            o_list = [i for i in node_other.iterchildren(tag=tag)]
            if [self.device.get_xpath(n) for n in s_list] == \
               [self.device.get_xpath(n) for n in o_list]:
                return False
            else:
                return True

        # all list instances under node_self have peers under node_other, and
        # the sequence of list instances under node_self that have peers under
        # node_other is same as the sequence of list instances under node_other
        def list_seq_is_inclusive(tag):
            s_list = [i for i in node_self.iterchildren(tag=tag)]
            o_list = [i for i in node_other.iterchildren(tag=tag)]
            s_seq = [self.device.get_xpath(n) for n in s_list]
            o_seq = [self.device.get_xpath(n) for n in o_list]
            if set(s_seq) <= set(o_seq) and \
               [i for i in s_seq if i in o_seq] == o_seq:
                return True
            else:
                return False

        in_s_not_in_o, in_o_not_in_s, in_s_and_in_o = \
            self._group_kids(node_self, node_other)
        for child_s in in_s_not_in_o:
            schema_node = self.device.get_schema_node(child_s)
            if schema_node.get('type') == 'leaf':
                generate_update(child_s)
            elif schema_node.get('type') == 'leaf-list':
                if child_s.tag not in done_list:
                    generate_replace(child_s, instance=False)
                    done_list.append(child_s.tag)
            elif schema_node.get('type') == 'container':
                generate_update(child_s)
            elif schema_node.get('type') == 'list':
                if schema_node.get('ordered-by') == 'user':
                    if child_s.tag not in done_list:
                        generate_replace(child_s, instance=False)
                        done_list.append(child_s.tag)
                else:
                    generate_update(child_s, instance=True)
        for child_o in in_o_not_in_s:
            schema_node = self.device.get_schema_node(child_o)
            if schema_node.get('type') == 'leaf':
                generate_delete(child_o)
            elif schema_node.get('type') == 'leaf-list':
                if child_o.tag not in done_list:
                    child_s = node_self.find(child_o.tag)
                    if child_s is None:
                        generate_delete(child_o, instance=False)
                    else:
                        generate_replace(child_s, instance=False)
                    done_list.append(child_o.tag)
            elif schema_node.get('type') == 'container':
                generate_delete(child_o)
            elif schema_node.get('type') == 'list':
                if schema_node.get('ordered-by') == 'user':
                    if list_seq_is_inclusive(child_o.tag):
                        generate_delete(child_o, instance=True)
                    else:
                        if child_o.tag not in done_list:
                            generate_replace(child_o, instance=False)
                            done_list.append(child_o.tag)
                else:
                    if list_is_empty(child_o.tag):
                        if child_o.tag not in done_list:
                            generate_delete(child_o, instance=False)
                            done_list.append(child_o.tag)
                    else:
                        generate_delete(child_o, instance=True)
        for child_s, child_o in in_s_and_in_o:
            schema_node = self.device.get_schema_node(child_s)
            if schema_node.get('type') == 'leaf':
                if child_s.text != child_o.text:
                    generate_update(child_s)
            elif schema_node.get('type') == 'leaf-list':
                if child_s.tag not in done_list:
                    if schema_node.get('ordered-by') == 'user':
                        if leaf_list_seq_is_different(child_s.tag):
                            generate_replace(child_s, instance=False)
                    else:
                        if leaf_list_set_is_different(child_s.tag):
                            generate_replace(child_s, instance=False)
                    done_list.append(child_s.tag)
            elif schema_node.get('type') == 'container':
                if BaseCalculator(self.device, child_s, child_o).ne:
                    d, r, u = self.node_sub(child_s, child_o)
                    paths_delete += d
                    updates_replace += r
                    updates_update += u
            elif schema_node.get('type') == 'list':
                if schema_node.get('ordered-by') == 'user':
                    if list_seq_is_different(child_s.tag):
                        if child_s.tag not in done_list:
                            generate_replace(child_s, instance=False)
                            done_list.append(child_s.tag)
                        else:
                            if BaseCalculator(self.device, child_s, child_o).ne:
                                d, r, u = self.node_sub(child_s, child_o)
                                paths_delete += d
                                updates_replace += r
                                updates_update += u
                else:
                    if BaseCalculator(self.device, child_s, child_o).ne:
                        d, r, u = self.node_sub(child_s, child_o)
                        paths_delete += d
                        updates_replace += r
                        updates_update += u
        return (paths_delete, updates_replace, updates_update)
