"""yang.ncdiff module defines a set of classes that calculate diff of two
configs, combine two configs or diffs, and predict config when a diff is
applied on a config. A config is the payload of a get-config message, and a
diff is the payload of a edit-config message."""

# metadata
__version__ = '1.0.0'
__author__ = 'Jonathan Yang <yuekyang@cisco.com>'
__contact__ = 'yang-python@cisco.com'
__copyright__ = 'Cisco Systems, Inc. Cisco Confidential'


import builtins
import os
import re
import logging
import pprint
import yang.connector as connector
import six
from copy import deepcopy
from lxml import etree
from ncclient import manager, operations, xml_
from itertools import filterfalse, repeat
from collections import deque

# create a logger for this module
logger = logging.getLogger(__name__)

nc_url = xml_.BASE_NS_1_0
yang_url = 'urn:ietf:params:xml:ns:yang:1'
config_tag = '{' + nc_url + '}config'
filter_tag = '{' + nc_url + '}filter'
operation_tag = '{' + nc_url + '}operation'
insert_tag = '{' + yang_url + '}insert'
value_tag = '{' + yang_url + '}value'
key_tag = '{' + yang_url + '}key'

def _cmperror(x, y):
    raise TypeError("can't compare '%s' to '%s'" % (
                    type(x).__name__, type(y).__name__))

def _inserterror(direction, path, attr_name, attr_value=None):
    if attr_value:
        raise ConfigDeltaError('attribute wrong: try to insert the node ' \
                               '{} {} another node, which cannot be found ' \
                               'by attribute "{}={}"' \
                               .format(path, direction, attr_name, attr_value))
    else:
        raise ConfigDeltaError('attribute missing: try to insert the node ' \
                               '{} {} another node, but it does not have ' \
                               'attribute "{}"' \
                               .format(path, direction, attr_name))

def __repr__(self):
    return '<{}.{} {} at {}>'.format(self.__class__.__module__,
                                     self.__class__.__name__,
                                     self._root.tag,
                                     hex(id(self)))

def __str__(self):
    return etree.tostring(self._root,
                          encoding='unicode',
                          pretty_print=True)

def xpath(self, *args, **kwargs):
    if 'namespaces' not in kwargs:
        kwargs['namespaces'] = self.ns
        return self._root.xpath(*args, **kwargs)
    else:
        return self._root.xpath(*args, **kwargs)

def ns_help(self):
    pprint.pprint(self.ns)

operations.rpc.RPCReply.__repr__ = __repr__
operations.rpc.RPCReply.__str__ = __str__
operations.rpc.RPCReply.xpath = xpath
operations.rpc.RPCReply.ns_help = ns_help


class ModelError(Exception):
    pass


class ConfigError(Exception):
    pass


class ConfigDeltaError(Exception):
    pass


class OpExecutorFix(manager.OpExecutor):

    def __new__(cls, name, bases, attrs):
        def make_wrapper(op_cls):
            def wrapper(self, *args, **kwds):
                return self.execute(op_cls, *args, **kwds)
            wrapper.__doc__ = op_cls.request.__doc__
            return wrapper
        for op_name, op_cls in six.iteritems(manager.OPERATIONS):
            if op_name in attrs: continue
            attrs[op_name] = make_wrapper(op_cls)
        return super(manager.OpExecutor, cls).__new__(cls, name, bases, attrs)


class ModelDevice(connector.Netconf, metaclass=OpExecutorFix):
    '''ModelDevice

    Abstraction of a device that supports NetConf protocol and YANG models.

    Attributes
    ----------
    nc : `object`
        An instance of ncclient.manager.Manager, which represents a NetConf
        connection to the device.

    models : `list`
        A list of models this ModelDevice instance can process. In other words,
        the ModelDevice instance contains schema infomation of a set of models,
        which can be added by load_model method.
    '''

    def __init__(self, *args, **kwargs):
        '''
        __init__ instantiates a ModelDevice instance.
        '''

        connector.Netconf.__init__(self, *args, **kwargs)

        # indexed by model name, e.g., Cisco-IOS-XE-native
        self.model = {}
        self.model_url = {}
        self.model_urls = {}
        self.model_prefix = {}
        self.model_prefixes = {}

        # indexed by {http://cisco.com/ns/yang/Cisco-IOS-XE-native}native
        self.nodes = {}
        self.paths = {}
        self.roots = {}

    def __repr__(self):
        return '<{}.{} object at {}>'.format(self.__class__.__module__,
                                             self.__class__.__name__,
                                             hex(id(self)))

    @property
    def models(self):
        '''models

        High-level api: Return a list of models the ModelDevice instance can
        process.

        Returns
        -------

        list
            A list of model names.
        '''

        return sorted(self.model.keys())

    def load_model(self, model):
        '''load_model

        High-level api: Load schema information either from YTool cxml file or
        from the device directly if it supports <get-schema> operation in
        RFC6022.

        Parameters
        ----------

        model : `str`
            Model name.

        Returns
        -------

        None
            Nothing returns.


        YAML Example::

            devices:
                asr22:
                    type: 'ASR'
                    tacacs:
                        login_prompt: "login:"
                        password_prompt: "Password:"
                        username: "admin"
                    passwords:
                        tacacs: admin
                        enable: admin
                        line: admin
                    connections:
                        a:
                            protocol: telnet
                            ip: "1.2.3.4"
                            port: 2004
                        vty:
                            protocol : telnet
                            ip : "2.3.4.5"
                        netconf:
                            class: yang.ncdiff.ModelDevice
                            ip : "2.3.4.5"
                            port: 830
                            username: admin
                            password: admin

        Code Example::

            >>> from ats.topology import loader
            >>> testbed = loader.load('/users/yuekyang/projects/asr21.yaml')
            >>> device = testbed.devices['asr21']
            >>> device.connect(alias='nc', via='netconf')
            >>> device.nc.load_model('/models/openconfig-interfaces@2016-12-22.xml')
            >>>
        '''

        if os.path.isfile(model):
            logger.info('Loading model file {}'.format(model))
            with open(model, 'r') as f:
                xml = f.read()
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.XML(xml, parser)
            model_name = tree.attrib['name']
            ns = tree.findall('namespace')
            self.model_prefixes[model_name] = \
                {c.attrib['prefix']: c.text for c in ns}
            self.model_prefix[model_name] = tree.attrib['prefix']
            self.model_url[model_name] = \
                self.model_prefixes[model_name][self.model_prefix[model_name]]
            self.model_urls[model_name] = \
                {v: k for k, v in self.model_prefixes[model_name].items()}
            self.model[model_name] = self._convert_tree(tree)
            roots = [c.tag for c in self.model[model_name].getchildren()]
            self.roots.update({r: model_name for r in roots})

    def execute(self, operation, *args, **kwargs):
        '''execute

        High-level api: Supported operations are get, get_config, get_schema,
        dispatch, edit_config, copy_config, validate, commit, discard_changes,
        delete_config, lock, unlock, close_session, kill_session,
        poweroff_machine and reboot_machine. Refer to ncclient document for
        more details.
        '''

        # allow for operation string type
        if type(operation) is str:
            try:
                cls = manager.OPERATIONS[operation]
            except KeyError:
                raise ValueError('No such operation "%s".\n'
                                 'Supported operations are: %s' %
                                 (operation, list(manager.OPERATIONS.keys())))
        else:
            cls = operation
        return super().execute(operation, *args, **kwargs)

    def get_config(self, source='running', filter=None, *, models=None):
        '''get_config

        High-level api: A modified version of get_config method in ncclient,
        and it is backward compatible to get_config method in ncclient.

        Parameters
        ----------

        source : `str`
            Same as source parameter in ncclient get_config method.

        filter : `Element`, optional
            A filter defined as an element, same as filter parameter in
            ncclient get_config method.
            If filter is not specified, all config data of models will be
            retrieved from the device.

        models : `str` or `list`
            A list of configuration model names.

        Returns
        -------

        RPCReply
            An instance of ncclient.operations.rpc.RPCReply.


        Code Example::

            >>> reply = device.nc.get_config(models=['openconfig-interfaces',
                                                     'openconfig-network-instance'])
            >>> assert(reply.ok)
            >>>
        '''

        operation = operations.retrieve.GetConfig
        if models:
            if filter:
                logger.warning('Argument filter is ignored as models is '
                               'specified')
            if isinstance(models, str):
                models = [models]
            roots = list(builtins.filter(
                lambda x: self.roots[x] in models,
                self.roots.keys()))
            writable_roots = list(builtins.filter(
                lambda x: self.get_node([x]).get('access') == 'read-write',
                roots))
            filter = etree.Element(filter_tag, type='subtree')
            for root in writable_roots:
                etree.SubElement(filter, root)
            filter_xml = etree.tostring(filter,
                                        encoding='unicode',
                                        pretty_print=False)
            logger.info('Argument filter is set to {}'.format(filter_xml))
        reply = super().execute(operation, source=source, filter=filter)
        reply.ns = self._get_ns(reply._root)
        return reply

    def get(self, filter=None, *, models=None):
        '''get

        High-level api: A modified version of get method in ncclient, and
        it is backward compatible to get method in ncclient.

        Parameters
        ----------

        filter : `Element`, optional
            A filter defined as an element, same as filter parameter in
            ncclient get method.
            If filter is not specified, all state data of models will be
            retrieved from the device.

        models : `str` or `list`
            A list of configuration model names.

        Returns
        -------

        RPCReply
            An instance of ncclient.operations.rpc.RPCReply.


        Code Example::

            >>> reply = device.nc.get(models=['openconfig-interfaces',
                                              'openconfig-network-instance'])
            >>> assert(reply.ok)
            >>>
        '''

        operation = operations.retrieve.Get
        if models:
            if filter:
                logger.warning('Argument filter is ignored as models is '
                               'specified')
            if isinstance(models, str):
                models = [models]
            roots = list(builtins.filter(
                lambda x: self.roots[x] in models,
                self.roots.keys()))
            writable_roots = list(builtins.filter(
                lambda x: self.get_node([x]).get('access') == 'read-write' or \
                          self.get_node([x]).get('access') == 'read',
                roots))
            filter = etree.Element(filter_tag, type='subtree')
            for root in writable_roots:
                etree.SubElement(filter, root)
            filter_xml = etree.tostring(filter,
                                        encoding='unicode',
                                        pretty_print=False)
            logger.info('Argument filter is set to {}'.format(filter_xml))
        reply = super().execute(operation, filter=filter)
        reply.ns = self._get_ns(reply._root)
        return reply

    def edit_config(self, config, format='xml', target='candidate',
                     default_operation=None, test_option=None,
                     error_option=None):
        '''edit_config

        High-level api: A modified version of edit_config method in ncclient,
        and it is backward compatible to edit_config method in ncclient.

        Parameters
        ----------

        operation : `class`
            Operation class pointing to ncclient.

        config : `Element` or `str` or `NcConfigDelta`, optional
            A config defined as an element, XML string or NcConfigDelta,
            similar to config parameter in ncclient edit_config method.

        target : `str`
            Same as target parameter in ncclient edit_config method.

        Returns
        -------

        RPCReply
            An instance of ncclient.operations.rpc.RPCReply.


        Code Example::

            >>> reply = device.nc.edit_config(delta, target='running')
            >>> assert(reply.ok)
            >>>
        '''

        operation = operations.edit.EditConfig
        if isinstance(config, NcConfig):
            config = config.ele
        reply = super().execute(operation, config=config,
                                format=format,
                                target=target,
                                default_operation=default_operation,
                                test_option=test_option,
                                error_option=error_option)
        reply.ns = self._get_ns(reply._root)
        return reply

    def extract_config(self, reply):
        '''extract_config

        High-level api: Extract config from a rpc-reply of get-config message.

        Parameters
        ----------

        reply : `RPCReply`
            An instance of ncclient.operations.rpc.RPCReply. It has to be
            a successful reply in order to extract config, since there is no
            config data in an errored reply.

        Returns
        -------

        NcConfig
            An instance of NcConfig, which represents a config state of the
            device.


        Code Example::

            >>> reply = device.nc.get_config(models='openconfig-interfaces')
            >>> assert(reply.ok)
            >>> config = device.nc.extract_config(reply)
            >>>
        '''

        return NcConfig(self, reply._root)

    def get_node(self, path):
        '''get_node

        High-level api: Given a path in config, in particular, a list of
        identifiers starting from roots, get_node returns a schema node.

        Parameters
        ----------

        path : `list`
            A list of identifiers starting from roots. Each identifier should
            use the `{namespace}tagname` notation. The path should be in the
            context of config data.

        Returns
        -------

        Element
            A schema node in Element, or None when nothing can be found.

        Raises
        ------

        ModelError
            If identify is not unique in a namespace.


        Code Example::

            >>> device.nc.load_model('/models/openconfig-interfaces@2016-12-22.xml')
            >>> path = [
                        '{http://openconfig.net/yang/interfaces}interfaces',
                        '{http://openconfig.net/yang/interfaces}interface',
                        '{http://openconfig.net/yang/interfaces/ethernet}ethernet',
                        '{http://openconfig.net/yang/interfaces/ethernet}config',
                        '{http://openconfig.net/yang/interfaces/ethernet}port-speed',
                        ]
            >>> schema_node = device.nc.get_node(path)
            >>>
        '''

        if ' '.join(path) in self.nodes:
            return self.nodes[' '.join(path)]
        m_name = self.roots[path[0]]
        nodes = deque(map(self._url_to_prefix, [m_name]*len(path), path))
        nodes.appendleft(m_name)
        nodes.appendleft('')
        a = self.model[m_name].xpath('/'.join(nodes),
                                     namespaces=self.model_prefixes[m_name])
        b = list(filterfalse(lambda x: x.attrib['type'] == 'choice' or
                                       x.attrib['type'] == 'case', a))
        if len(b) == 1:
            self.nodes[' '.join(path)] = b[0]
            self.paths[' '.join(path)] = self.schema_path(b[0])
            return b[0]
        elif len(b) > 1:
            raise ModelError('More than one child called {}'.format(nodes[-1]))
        parent = self.get_node(path[:-1])
        if parent is not None:
            path_str = './/' + self._url_to_prefix(m_name, path[-1])
            a = parent.findall(path_str,
                               namespaces=self.model_prefixes[m_name])
            b = list(filterfalse(lambda x: x.attrib['type'] == 'choice' or
                                           x.attrib['type'] == 'case', a))
            c = list(filterfalse(lambda x: not self._is_parent(parent, x), b))
            if len(c) == 1:
                self.nodes[' '.join(path)] = c[0]
                self.paths[' '.join(path)] = self.schema_path(c[0])
                return c[0]
            elif len(c) > 1:
                raise ModelError('More than one child with name {}' \
                                 .format(path[-1]))
            else:
                return None
        else:
            return None

    def schema_path(self, node):
        '''schema_path

        High-level api: Given a schema node, schema_path returns an xpath of
        the schema node, which starts from the model name. Each identify uses
        the `prefix:tagname` notation, except for the default namespace.
        Default namespace uses `tagname` notation.

        Parameters
        ----------

        node : `Element`
            A schema node.

        Returns
        -------

        Element
            An xpath of the schema node, which starts from the model name. Each
            identify uses the `prefix:tagname` notation, except for the default
            namespace. Default namespace uses `tagname` notation.


        Code Example::

            >>> device.nc.load_model('/models/openconfig-interfaces@2016-12-22.xml')
            >>> path = [
                        '{http://openconfig.net/yang/interfaces}interfaces',
                        '{http://openconfig.net/yang/interfaces}interface',
                        '{http://openconfig.net/yang/interfaces/ethernet}ethernet',
                        '{http://openconfig.net/yang/interfaces/ethernet}config',
                        '{http://openconfig.net/yang/interfaces/ethernet}port-speed',
                        ]
            >>> schema_node = device.nc.get_node(path)
            >>> schema_path = device.nc.schema_path(schema_node)
            >>> assert(schema_path == 'openconfig-interfaces/interfaces/'
                                      'interface/oc-eth:ethernet/'
                                      'oc-eth:config/oc-eth:port-speed')
            >>>
        '''

        path = list(reversed([a.tag for a in node.iterancestors()])) + \
               [node.tag]
        prefixes = list(map(self._url_to_prefix, [path[0]]*len(path), path))
        return '/'.join(map(self._remove_model_prefix,
                            [path[0]]*len(path),
                            prefixes))

    def get_prefix(self, url):
        '''get_prefix

        High-level api: Search URL in loaded models. If found, return the
        corresponding prefix. Otherwise, return None.

        Parameters
        ----------

        url : `str`
            URL of a namespace.

        Returns
        -------

        string or None
            The corresponding prefix if URL is found in loaded models. None if
            URL is not found.


        Code Example::

            >>> device.nc.load_model('/models/openconfig-interfaces@2016-12-22.xml')
            >>> prefix = device.nc.get_prefix('http://openconfig.net/yang/interfaces/ethernet')
            >>> assert(prefix == 'oc-eth')
            >>>
        '''

        for model in self.model_urls:
            if url in self.model_urls[model]:
                return self.model_urls[model][url]
        return None

    def _convert_tree(self, element1, element2=None):
        '''_convert_tree

        Low-level api: Convert YTool cxml tree to an internal schema tree. This
        method is recursive.

        Parameters
        ----------

        element1 : `Element`
            The element to be converted.

        element2 : `Element`
            A new element being constructed.

        Returns
        -------

        Element
            An internal schema element.
        '''

        model_name = element1.getroottree().getroot().get('name')
        if element2 is None:
            attributes = deepcopy(element1.attrib)
            tag = attributes['name']
            del attributes['name']
            element2 = etree.Element(tag, attributes)
        for e1 in element1.findall('node'):
            attributes = deepcopy(e1.attrib)
            tag = self._prefix_to_url(model_name, attributes['name'])
            del attributes['name']
            e2 = etree.SubElement(element2, tag, attributes)
            self._convert_tree(e1, e2)
        return element2

    @staticmethod
    def _is_parent(node1, node2):
        '''_is_parent

        Low-level api: Return True if node1 is parent of node2, otherwise,
        return False.

        Parameters
        ----------

        node1 : `Element`
            An element to be considered as a parent.

        node2 : `Element`
            An element to be considered as a child.

        Returns
        -------

        boolean
            True if node1 is parent of node2, otherwise, return False.
        '''

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

    def _prefix_to_url(self, model_name, id):
        '''_prefix_to_url

        Low-level api: Convert an identifier from `prefix:tagname` notation to
        `{namespace}tagname` notation. If the identifier does not have a
        prefix, it is assumed that the tagname uses default namespace, i.e.,
        the namespace of the model.

        Parameters
        ----------

        model_name : `str`
            Model name in which identifier will be converted.

        id : `str`
            Identifier in `prefix:tagname` notation.

        Returns
        -------

        str
            Identifier in `{namespace}tagname` notation.
        '''

        parts = id.split(':')
        if len(parts) > 1:
            return '{' + self.model_prefixes[model_name][parts[0]] + '}' + \
                   parts[1]
        else:
            return '{' + self.model_url[model_name] + '}' + id

    def _url_to_prefix(self, model_name, id):
        '''_url_to_prefix

        Low-level api: Convert an identifier from `{namespace}tagname` notation
        to `prefix:tagname` notation. If the identifier does not have a
        namespace, the identifier is simply returned without modification.

        Parameters
        ----------

        model_name : `str`
            Model name in which identifier will be converted.

        id : `str`
            Identifier in `{namespace}tagname` notation.

        Returns
        -------

        str
            Identifier in `prefix:tagname` notation.
        '''

        ret = re.search('^{(.+)}(.+)$', id)
        if ret:
            return self.model_urls[model_name][ret.group(1)] + ':' + \
                   ret.group(2)
        else:
            return id

    def _remove_model_prefix(self, model_name, id):
        '''_remove_model_prefix

        Low-level api: If prefix is the model prefix, return tagname without
        prefix. If prefix is not the model prefix, simply return the identifier
        without modification.

        Parameters
        ----------

        model_name : `str`
            Model name in which identifier will be converted.

        id : `str`
            Identifier in `prefix:tagname` notation.

        Returns
        -------

        str
            Identifier in `prefix:tagname` notation if prefix is not the model
            prefix. Or identifier in `tagname` notation if prefix is the model
            prefix.
        '''

        reg_str = '^' + self.model_prefix[model_name] + ':(.+)$'
        ret = re.search(reg_str, id)
        if ret:
            return ret.group(1)
        else:
            return id

    def _get_ns(self, reply):
        '''_get_ns

        Low-level api: Return a dict of nsmap.

        Parameters
        ----------

        reply : `Element`
            rpc-reply as an instance of Element.

        Returns
        -------

        dict
            A dict of nsmap.
        '''

        ns = {'nc': nc_url}
        root = reply.getroottree()
        urls = {}
        for node in root.iter():
            for p, u in node.nsmap.items():
                if p is None:
                    if u not in urls:
                        urls[u] = None
                else:
                    if u not in urls or \
                       u in urls and urls[u] is None:
                        urls[u] = p
        leftover = [u for u, p in urls.items() if p is None]
        i = 0
        for url in leftover:
            prefix = self.get_prefix(url)
            if prefix is None:
                logger.debug('{} cannot be found in namespaces of ' \
                             'any loaded models' \
                             .format(url))
                urls[url] = 'ns{:02d}'.format(i)
                i += 1
            else:
                urls[url] = prefix
        return {v: k for k, v in urls.items()}


class NcConfig(object):
    '''NcConfig

    Abstraction of a config for a device.

    Attributes
    ----------
    device : `object`
        An instance of yang.ncdiff.ModelDevice, which represents a modeled
        device.

    ele : `Element`
        A lxml elementtree which contains the config.

    xml : `str`
        A string presentation of self.ele.

    ns : `dict`
        A dictionary of namespaces used by the config.
    '''

    def __init__(self, modeldevice, config=None):
        '''
        __init__ instantiates a NcConfig instance.
        '''

        self.device = modeldevice
        if config is None:
            self.ele = etree.Element(config_tag, nsmap={'nc': nc_url})
        elif isinstance(config, str):
            parser = etree.XMLParser(remove_blank_text=True)
            self.ele = self._retrieve_config(etree.XML(config, parser))
        elif isinstance(config, etree._Element):
            self.ele = self._retrieve_config(config)
        else:
            raise TypeError('NcConfig() argument must be None, or XML ' \
                            'string, or lxml.etree.Element, but not {}' \
                            .format(type(config)))
        self._validate_config()

    def __repr__(self):
        return '<{}.{} {} at {}>'.format(self.__class__.__module__,
                                             self.__class__.__name__,
                                             self.ele.tag,
                                             hex(id(self)))

    def __str__(self):
        return etree.tostring(self.ele,
                              encoding='unicode',
                              pretty_print=True)

    def __add__(self, other):
        if isinstance(other, NcConfig):
            sum = NcConfig(self.device, self.ele)
            NcConfig._node_add(sum, other, sum.ele, other.ele)
            return sum
        else:
            return NotImplemented

    @staticmethod
    def _node_add(sum, other, node_sum, node_other):
        '''_node_add

        Low-level api: Combine two configs or apply a config delta to a config.
        This method is recursive. NcConfig sum will be modified during the
        process, and it becomes the result at the end.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        node_sum : `Element`
            A config node in sum that is being processed.

        node_other : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        supported_node_type = [
            'leaf',
            'leaf-list',
            'container',
            'list',
            ]
        in_s_not_in_o, in_o_not_in_s, in_s_and_in_o = \
            NcConfig._group_kids(sum, other, node_sum, node_other)
        for child_s in in_s_not_in_o:
            pass
        for child_o in in_o_not_in_s:
            # delete
            if child_o.get(operation_tag) == 'delete':
                raise ConfigDeltaError('data-missing: try to delete node {} ' \
                                       'but it does not exist in config' \
                                       .format(other.get_schema_path(child_o)))
            # remove
            elif child_o.get(operation_tag) == 'remove':
                pass
            # merge, replace, create or none
            else:
                s_node = other.get_schema_node(child_o)
                if s_node.get('type') in supported_node_type:
                    getattr(NcConfig,
                            '_node_add_without_peer_{}' \
                            .format(s_node.get('type').replace('-', ''))) \
                            (sum, other, node_sum, child_o)
        for child_s, child_o in in_s_and_in_o:
            s_node = sum.get_schema_node(child_s)
            if s_node.get('type') in supported_node_type:
                getattr(NcConfig,
                        '_node_add_with_peer_{}' \
                        .format(s_node.get('type').replace('-', ''))) \
                        (sum, other, child_s, child_o)

    @staticmethod
    def _node_add_without_peer_leaf(sum, other, node_sum, child_o):
        '''_node_add_without_peer_leaf

        Low-level api: Apply delta child_o to node_sum when there is no peer of
        child_o can be found under node_sum. child_o is a leaf node. Element
        node_sum will be modified during the process.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        node_sum : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        e = deepcopy(child_o)
        node_sum.append(NcConfig._del_attrib(e))

    @staticmethod
    def _node_add_without_peer_leaflist(sum, other, node_sum, child_o):
        '''_node_add_without_peer_leaflist

        Low-level api: Apply delta child_o to node_sum when there is no peer of
        child_o can be found under node_sum. child_o is a leaf-list node.
        Element node_sum will be modified during the process.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        node_sum : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        s_node = other.get_schema_node(child_o)
        e = deepcopy(child_o)
        scope = node_sum.getchildren()
        siblings = NcConfig._get_sequence(scope,
                                          child_o.tag,
                                          node_sum)
        if s_node.get('ordered-by') == 'user' and \
           child_o.get(insert_tag) is not None:
            if child_o.get(insert_tag) == 'first':
                if siblings:
                    siblings[0].addprevious(NcConfig._del_attrib(e))
                else:
                    node_sum.append(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'last':
                if siblings:
                    siblings[-1].addnext(NcConfig._del_attrib(e))
                else:
                    node_sum.append(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'before':
                if child_o.get(value_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('before', path, 'value')
                siblings = node_sum.findall(child_o.tag)
                sibling = [s for s in siblings
                           if s.text == child_o.get(value_tag)]
                if not sibling:
                    path = other.get_schema_path(child_o)
                    value = child_o.get(value_tag)
                    _inserterror('before', path, 'value', value)
                sibling[0].addprevious(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'after':
                if child_o.get(value_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('after', path, 'value')
                siblings = node_sum.findall(child_o.tag)
                sibling = [s for s in siblings
                           if s.text == child_o.get(value_tag)]
                if not sibling:
                    path = other.get_schema_path(child_o)
                    value = child_o.get(value_tag)
                    _inserterror('after', path, 'value', value)
                sibling[0].addnext(NcConfig._del_attrib(e))
        else:
            if siblings:
                siblings[-1].addnext(NcConfig._del_attrib(e))
            else:
                node_sum.append(NcConfig._del_attrib(e))

    @staticmethod
    def _node_add_without_peer_container(sum, other, node_sum, child_o):
        '''_node_add_without_peer_container

        Low-level api: Apply delta child_o to node_sum when there is no peer of
        child_o can be found under node_sum. child_o is a container node.
        Element node_sum will be modified during the process.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        node_sum : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        e = deepcopy(child_o)
        node_sum.append(NcConfig._del_attrib(e))

    @staticmethod
    def _node_add_without_peer_list(sum, other, node_sum, child_o):
        '''_node_add_without_peer_list

        Low-level api: Apply delta child_o to node_sum when there is no peer of
        child_o can be found under node_sum. child_o is a list node. Element
        node_sum will be modified during the process.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        node_sum : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        s_node = other.get_schema_node(child_o)
        e = deepcopy(child_o)
        scope = node_sum.getchildren()
        siblings = NcConfig._get_sequence(scope,
                                          child_o.tag,
                                          node_sum)
        if s_node.get('ordered-by') == 'user' and \
           child_o.get(insert_tag) is not None:
            if child_o.get(insert_tag) == 'first':
                if siblings:
                    siblings[0].addprevious(NcConfig._del_attrib(e))
                else:
                    node_sum.append(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'last':
                if siblings:
                    siblings[-1].addnext(NcConfig._del_attrib(e))
                else:
                    node_sum.append(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'before':
                if child_o.get(key_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('before', path, 'key')
                sibling = node_sum.find(child_o.tag +
                                        child_o.get(key_tag),
                                        namespaces=child_o.nsmap)
                if sibling is None:
                    path = other.get_schema_path(child_o)
                    key = child_o.get(key_tag)
                    _inserterror('before', path, 'key', key)
                sibling.addprevious(NcConfig._del_attrib(e))
            elif child_o.get(insert_tag) == 'after':
                if child_o.get(key_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('after', path, 'key')
                sibling = node_sum.find(child_o.tag +
                                        child_o.get(key_tag),
                                        namespaces=child_o.nsmap)
                if sibling is None:
                    path = other.get_schema_path(child_o)
                    key = child_o.get(key_tag)
                    _inserterror('after', path, 'key', key)
                sibling.addnext(NcConfig._del_attrib(e))
        else:
            if siblings:
                siblings[-1].addnext(NcConfig._del_attrib(e))
            else:
                node_sum.append(NcConfig._del_attrib(e))

    @staticmethod
    def _node_add_with_peer_leaf(sum, other, child_s, child_o):
        '''_node_add_with_peer_leaf

        Low-level api: Apply delta child_o to child_s when child_s is the peer
        of child_o. Element child_s and child_o are leaf nodes. Element child_s
        will be modified during the process. RFC6020 section 7.6.7 is a
        reference of this method.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        child_s : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        if child_o.get(operation_tag) is None:
            if isinstance(other, NcConfigDelta):
                child_s.text = child_o.text
            elif isinstance(other, NcConfig):
                if child_s.text != child_o.text:
                    path = other.get_schema_path(child_o)
                    raise ConfigError('conflicting config: try to ' \
                                      'combine two nodes {} but ' \
                                      'their values are different' \
                                      .format(path))
        elif child_o.get(operation_tag) == 'merge':
            child_s.text = child_o.text
        elif child_o.get(operation_tag) == 'replace':
            child_s.text = child_o.text
        elif child_o.get(operation_tag) == 'create':
            raise ConfigError('data-exists: try to create ' \
                              'node {} but it already exists' \
                              .format(other.get_schema_path(child_o)))
        elif child_o.get(operation_tag) == 'delete' or \
             child_o.get(operation_tag) == 'remove':
            node_sum.remove(child_s)
        else:
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('unknown operation: node {} ' \
                                   'contains operation {}' \
                                   .format(path,
                                           child_o.get(operation_tag)))

    @staticmethod
    def _node_add_with_peer_leaflist(sum, other, child_s, child_o):
        '''_node_add_with_peer_leaflist

        Low-level api: Apply delta child_o to child_s when child_s is the peer
        of child_o. Element child_s and child_o are leaf-list nodes. Element
        child_s will be modified during the process. RFC6020 section 7.7.7 is a
        reference of this method.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        child_s : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        s_node = sum.get_schema_node(child_s)
        node_sum = child_s.getparent()
        if child_o.get(operation_tag) is None or \
           child_o.get(operation_tag) == 'merge' or \
           child_o.get(operation_tag) == 'replace':
            if s_node.get('ordered-by') == 'user' and \
               child_o.get(insert_tag) is not None:
                if child_o.get(insert_tag) == 'first':
                    scope = node_sum.getchildren()
                    siblings = NcConfig._get_sequence(scope,
                                                      child_o.tag,
                                                      node_sum)
                    if siblings[0] != child_s:
                        siblings[0].addprevious(child_s)
                elif child_o.get(insert_tag) == 'last':
                    scope = node_sum.getchildren()
                    siblings = NcConfig._get_sequence(scope,
                                                      child_o.tag,
                                                      node_sum)
                    if siblings[-1] != child_s:
                        siblings[-1].addnext(child_s)
                elif child_o.get(insert_tag) == 'before':
                    if child_o.get(value_tag) is None:
                        path = other.get_schema_path(child_o)
                        _inserterror('before', path, 'value')
                    siblings = node_sum.findall(child_o.tag)
                    sibling = [s for s in siblings
                               if s.text == child_o.get(value_tag)]
                    if not sibling:
                        path = other.get_schema_path(child_o)
                        value = child_o.get(value_tag)
                        _inserterror('before', path, 'value', value)
                    if sibling[0] != child_s:
                        sibling[0].addprevious(child_s)
                elif child_o.get(insert_tag) == 'after':
                    if child_o.get(value_tag) is None:
                        path = other.get_schema_path(child_o)
                        _inserterror('after', path, 'value')
                    siblings = node_sum.findall(child_o.tag)
                    sibling = [s for s in siblings
                               if s.text == child_o.get(value_tag)]
                    if not sibling:
                        path = other.get_schema_path(child_o)
                        value = child_o.get(value_tag)
                        _inserterror('after', path, 'value', value)
                    if sibling[0] != child_s:
                        sibling[0].addnext(child_s)
        elif child_o.get(operation_tag) == 'create':
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('data-exists: try to create ' \
                                   'node {} but it already exists' \
                                   .format(path))
        elif child_o.get(operation_tag) == 'delete' or \
             child_o.get(operation_tag) == 'remove':
            node_sum.remove(child_s)
        else:
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('unknown operation: node {} ' \
                                   'contains operation "{}"' \
                                   .format(path,
                                           child_o.get(operation_tag)))

    @staticmethod
    def _node_add_with_peer_container(sum, other, child_s, child_o):
        '''_node_add_with_peer_container

        Low-level api: Apply delta child_o to child_s when child_s is the peer
        of child_o. Element child_s and child_o are container nodes. Element
        child_s will be modified during the process. RFC6020 section 7.5.8 is a
        reference of this method.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        child_s : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        if child_o.get(operation_tag) is None or \
           child_o.get(operation_tag) == 'merge':
            NcConfig._node_add(sum, other, child_s, child_o)
        elif child_o.get(operation_tag) == 'replace':
            e = deepcopy(child_o)
            node_sum.replace(child_s, NcConfig._del_attrib(e))
        elif child_o.get(operation_tag) == 'create':
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('data-exists: try to create ' \
                                   'node {} but it already exists' \
                                   .format(path))
        elif child_o.get(operation_tag) == 'delete' or \
             child_o.get(operation_tag) == 'remove':
            node_sum.remove(child_s)
        else:
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('unknown operation: node {} ' \
                                   'contains operation "{}"' \
                                   .format(path,
                                           child_o.get(operation_tag)))

    @staticmethod
    def _node_add_with_peer_list(sum, other, child_s, child_o):
        '''_node_add_with_peer_list

        Low-level api: Apply delta child_o to child_s when child_s is the peer
        of child_o. Element child_s and child_o are list nodes. Element child_s
        will be modified during the process. RFC6020 section 7.8.6 is a
        reference of this method.

        Parameters
        ----------

        sum : `NcConfig`
            One config to be combined.

        other : `NcConfig`
            The other config to be combined.

        child_s : `Element`
            A config node in sum that is being processed.

        child_o : `Element`
            A config node in other that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        s_node = sum.get_schema_node(child_s)
        node_sum = child_s.getparent()
        if child_o.get(operation_tag) != 'delete' and \
           child_o.get(operation_tag) != 'remove' and \
           s_node.get('ordered-by') == 'user' and \
           child_o.get(insert_tag) is not None:
            if child_o.get(insert_tag) == 'first':
                scope = node_sum.getchildren()
                siblings = NcConfig._get_sequence(scope,
                                                  child_o.tag,
                                                  node_sum)
                if siblings[0] != child_s:
                    siblings[0].addprevious(child_s)
            elif child_o.get(insert_tag) == 'last':
                scope = node_sum.getchildren()
                siblings = NcConfig._get_sequence(scope,
                                                  child_o.tag,
                                                  node_sum)
                if siblings[-1] != child_s:
                    siblings[-1].addnext(child_s)
            elif child_o.get(insert_tag) == 'before':
                if child_o.get(key_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('before', path, 'key')
                sibling = node_sum.find(child_o.tag +
                                        child_o.get(key_tag),
                                        namespaces=child_o.nsmap)
                if sibling is None:
                    path = other.get_schema_path(child_o)
                    key = child_o.get(key_tag)
                    _inserterror('before', path, 'key', key)
                if sibling != child_s:
                    sibling.addprevious(child_s)
            elif child_o.get(insert_tag) == 'after':
                if child_o.get(key_tag) is None:
                    path = other.get_schema_path(child_o)
                    _inserterror('after', path, 'key')
                sibling = node_sum.find(child_o.tag +
                                        child_o.get(key_tag),
                                        namespaces=child_o.nsmap)
                if sibling is None:
                    path = other.get_schema_path(child_o)
                    key = child_o.get(key_tag)
                    _inserterror('after', path, 'key', key)
                if sibling != child_s:
                    sibling.addnext(child_s)
        if child_o.get(operation_tag) is None or \
           child_o.get(operation_tag) == 'merge':
            NcConfig._node_add(sum, other, child_s, child_o)
        elif child_o.get(operation_tag) == 'replace':
            e = deepcopy(child_o)
            node_sum.replace(child_s, NcConfig._del_attrib(e))
        elif child_o.get(operation_tag) == 'create':
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('data-exists: try to create ' \
                                   'node {} but it already exists' \
                                   .format(path))
        elif child_o.get(operation_tag) == 'delete' or \
             child_o.get(operation_tag) == 'remove':
            node_sum.remove(child_s)
        else:
            path = other.get_schema_path(child_o)
            raise ConfigDeltaError('unknown operation: node {} ' \
                                   'contains operation "{}"' \
                                   .format(path,
                                           child_o.get(operation_tag)))

    def __sub__(self, other):
        if type(other) == NcConfig:
            if self == other:
                return None
            else:
                config_s = deepcopy(self.ele)
                config_o = deepcopy(other.ele)
                self._node_sub(other, config_s, config_o)
                return NcConfigDelta(self.device, config_s, config_o)
        elif isinstance(other, NcConfigDelta):
            return self.__add__(-other)
        else:
            return NotImplemented

    def _node_sub(self, other, node_self, node_other):
        '''_node_sub

        Low-level api: Compute the delta of two configs. This method is
        recursive. Assume two configs are different.

        Parameters
        ----------

        other : `NcConfig`
            The destination config while self is the source config.

        node_self : `Element`
            A config node in the source config that is being processed.
            node_self cannot be a leaf node.

        node_other : `Element`
            A config node in destination config that is being processed.

        Returns
        -------

        None
            There is no return of this method.
        '''

        in_s_not_in_o, in_o_not_in_s, in_s_and_in_o = \
            NcConfig._group_kids(self, other, node_self, node_other)
        ordered_by_user = {}
        for child_s in in_s_not_in_o:
            child_o = etree.Element(child_s.tag,
                                    {operation_tag: 'delete'})
            siblings = [c for c in node_other.iterchildren(tag=child_s.tag)]
            if siblings:
                siblings[-1].addnext(child_o)
            else:
                node_other.append(child_o)
            s_node = self.get_schema_node(child_s)
            if s_node.get('type') == 'leaf-list':
                if s_node.get('ordered-by') == 'user' and \
                   s_node.tag not in ordered_by_user:
                    ordered_by_user[s_node.tag] = 'leaf-list'
                child_o.text = child_s.text
            elif s_node.get('type') == 'list':
                keys = self._get_list_keys(s_node)
                if s_node.get('ordered-by') == 'user' and \
                   s_node.tag not in ordered_by_user:
                    ordered_by_user[s_node.tag] = keys
                for key in keys:
                    e = etree.SubElement(child_o, key)
                    e.text = child_s.find(key).text
        for child_o in in_o_not_in_s:
            child_s = etree.Element(child_o.tag,
                                    {operation_tag: 'delete'})
            siblings = [c for c in node_self.iterchildren(tag=child_o.tag)]
            if siblings:
                siblings[-1].addnext(child_s)
            else:
                node_self.append(child_s)
            s_node = other.get_schema_node(child_o)
            if s_node.get('type') == 'leaf-list':
                if s_node.get('ordered-by') == 'user' and \
                   s_node.tag not in ordered_by_user:
                    ordered_by_user[s_node.tag] = 'leaf-list'
                child_s.text = child_o.text
            elif s_node.get('type') == 'list':
                keys = other._get_list_keys(s_node)
                if s_node.get('ordered-by') == 'user' and \
                   s_node.tag not in ordered_by_user:
                    ordered_by_user[s_node.tag] = keys
                for key in keys:
                    e = etree.SubElement(child_s, key)
                    e.text = child_o.find(key).text
        for child_s, child_o in in_s_and_in_o:
            s_node = self.get_schema_node(child_s)
            if s_node.get('type') == 'leaf':
                if child_s.text == child_o.text:
                    if not s_node.get('is_key'):
                        node_self.remove(child_s)
                        node_other.remove(child_o)
            elif s_node.get('type') == 'leaf-list':
                if s_node.get('ordered-by') == 'user':
                    if s_node.tag not in ordered_by_user:
                        ordered_by_user[s_node.tag] = 'leaf-list'
                else:
                    node_self.remove(child_s)
                    node_other.remove(child_o)
            elif s_node.get('type') == 'container':
                if self._node_le(child_s, child_o) and \
                   other._node_le(child_o, child_s):
                    node_self.remove(child_s)
                    node_other.remove(child_o)
                else:
                    self._node_sub(other, child_s, child_o)
            elif s_node.get('type') == 'list':
                if s_node.get('ordered-by') == 'user' and \
                   s_node.tag not in ordered_by_user:
                    ordered_by_user[s_node.tag] = self._get_list_keys(s_node)
                if self._node_le(child_s, child_o) and \
                   other._node_le(child_o, child_s):
                    if s_node.get('ordered-by') == 'user':
                        for child in child_s.getchildren():
                            schema_node = self.get_schema_node(child)
                            if not schema_node.get('is_key'):
                                child_s.remove(child)
                        for child in child_o.getchildren():
                            schema_node = other.get_schema_node(child)
                            if not schema_node.get('is_key'):
                                child_o.remove(child)
                    else:
                        node_self.remove(child_s)
                        node_other.remove(child_o)
                else:
                    self._node_sub(other, child_s, child_o)
            else:
                path = self.device.schema_path(s_node)
                raise ConfigError('unknown schema node type: type of node {}' \
                                  'is {}' \
                                  .format(path, s_node.get('type')))
        for tag in ordered_by_user:
            scope_s = in_s_not_in_o + in_s_and_in_o
            scope_o = in_o_not_in_s + in_s_and_in_o
            for sequence in NcConfig._get_sequence(scope_s, tag, node_self), \
                            NcConfig._get_sequence(scope_o, tag, node_other):
                for item in sequence:
                    # modifying the namespace mapping of a node is not possible
                    # in lxml. See https://bugs.launchpad.net/lxml/+bug/555602
#                   if 'yang' not in item.nsmap:
#                       item.nsmap['yang'] = yang_url

                    i = sequence.index(item)
                    if i == 0:
                        item.set(insert_tag, 'first')
                    else:
                        item.set(insert_tag, 'after')
                        precursor = sequence[i - 1]
                        if ordered_by_user[tag] == 'leaf-list':
                            item.set(value_tag, precursor.text)
                        else:
                            keys = ordered_by_user[tag]
                            key_nodes = {k: precursor.find(k) for k in keys}
                            ids = {k: NcConfig._url_to_prefix(n, k) \
                                   for k, n in key_nodes.items()}
                            l = ["[{}='{}']".format(ids[k],
                                                    key_nodes[k].text) \
                                 for k in keys]
                            item.set(key_tag, ''.join(l))

    @staticmethod
    def _url_to_prefix(node, id):
        '''_url_to_prefix

        Low-level api: Convert an identifier from `{namespace}tagname` notation
        to `prefix:tagname` notation by looking at nsmap of the node. If the
        identifier does not have a namespace, the identifier is simply returned
        without modification.

        Parameters
        ----------

        model_name : `str`
            Model name in which identifier will be converted.

        id : `str`
            Identifier in `{namespace}tagname` notation.

        Returns
        -------

        str
            Identifier in `prefix:tagname` notation.
        '''

        prefixes = {v: k for k, v in node.nsmap.items()}
        ret = re.search('^{(.+)}(.+)$', id)
        if ret:
            if ret.group(1) in prefixes:
                if prefixes[ret.group(1)] is None:
                    return ret.group(2)
                else:
                    return prefixes[ret.group(1)] + ':' + ret.group(2)
        return id

    @staticmethod
    def _del_attrib(element):
        '''_del_attrib

        Low-level api: Delete four attributes from an ElementTree node if they
        exist: operation, insert, value and key.

        Parameters
        ----------

        element : `Element`
            The ElementTree node needs to be looked at.

        Returns
        -------

        Element
            The ElementTree node is returned after processing.
        '''

        for tag in operation_tag, insert_tag, value_tag, key_tag:
            if element.get(tag):
                del element.attrib[tag]
        return element

    @staticmethod
    def _get_sequence(scope, tag, parent):
        '''_get_sequence

        Low-level api: Return a list of children of a parent with the same tag
        within the scope.

        Parameters
        ----------

        scope : `list`
            Members can be an element, or a tuple of two elements.

        tag : `str`
            Identifier in `{url}tagname` notation.

        parent : `Element`
            The parent node.

        Returns
        -------

        list
            A list of children with the same tag within the scope.
        '''

        new_scope = []
        for item in scope:
            if isinstance(item, tuple):
                one, two = item
                if one.getparent() == parent:
                    new_scope.append(one)
                else:
                    new_scope.append(two)
            else:
                new_scope.append(item)
        return [child for child in parent.iterchildren(tag=tag) \
                if child in new_scope]

    @staticmethod
    def _group_kids(one, two, node_one, node_two):
        '''_group_kids

        Low-level api: Consider an ElementTree node in a NcConfig instance. Now
        we have two NcConfig instances and we want to compare two corresponding
        ElementTree nodes. This method group children of these nodes in three
        categories: some only exist in node #1, some only exist in node #2, and
        some chiildren of node #1 have peers in node #2.

        Parameters
        ----------

        one : `NcConfig`
            An instance of NcConfig.

        two : `NcConfig`
            Another instance of NcConfig.

        node_one : `Element`
            An ElementTree node in NcConfig instance one.

        node_two : `Element`
            An ElementTree node in NcConfig instance two.

        Returns
        -------

        tuple
            There are three elements in the tuple. The first element is a list
            of children of node #1 that do not have any peers in node #2. The
            second element is a list of children of node #2 that do not have
            any peers in node #1. The last element is a list of tuples, and
            each tuple represents a pair of peers.
        '''

        in_1_not_in_2 = []
        in_2_not_in_1 = []
        in_1_and_in_2 = []
        for child in node_one.getchildren():
            peers = one._get_peers(child, node_two)
            if len(peers) < 1:
                # child in self but not in other
                in_1_not_in_2.append(child)
            elif len(peers) > 1:
                # one child in self matches multiple children in other
                raise ConfigError('not unique peer: {}' \
                                  .format(one.get_config_path(child)))
            else:
                # child matches one peer in other
                in_1_and_in_2.append((child, peers[0]))
        for child in node_two.getchildren():
            peers = two._get_peers(child, node_one)
            if len(peers) < 1:
                # child in other but not in self
                in_2_not_in_1.append(child)
            elif len(peers) > 1:
                # one child in other matches multiple children in self
                raise ConfigError('not unique peer: {}' \
                                  .format(two.get_config_path(child)))
            else:
                # child in self matches one peer in self
                pass
        return (in_1_not_in_2, in_2_not_in_1, in_1_and_in_2)

    @staticmethod
    def _get_list_keys(model_node):
        '''_get_list_keys

        Low-level api: Given a schema node, in particular, a list type node, it
        returns a list of keys.

        Parameters
        ----------

        model_node : `Element`
            A schema node.

        Returns
        -------

        list
            A list of tags of keys in `{url}tagname` notation.
        '''

        nodes = list(filter(lambda x: x.get('is_key'),
                            model_node.getchildren()))
        return [n.tag for n in nodes]

    def __lt__(self, other):
        if isinstance(other, NcConfig):
            return self._node_le(self.ele, other.ele) and \
                   not other._node_le(other.ele, self.ele)
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, NcConfig):
            return other._node_le(other.ele, self.ele) and \
                   not self._node_le(self.ele, other.ele)
        else:
            _cmperror(self, other)

    def __le__(self, other):
        if isinstance(other, NcConfig):
            return self._node_le(self.ele, other.ele)
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, NcConfig):
            return other._node_le(other.ele, self.ele)
        else:
            _cmperror(self, other)

    def __eq__(self, other):
        if isinstance(other, NcConfig):
            return self._node_le(self.ele, other.ele) and \
                   other._node_le(other.ele, self.ele)
        else:
            _cmperror(self, other)

    def __ne__(self, other):
        if isinstance(other, NcConfig):
            return not self._node_le(self.ele, other.ele) or \
                   not other._node_le(other.ele, self.ele)
        else:
            _cmperror(self, other)

    def _node_le(self, node_self, node_other):
        '''_node_le

        Low-level api: Return True if all descendants of one node exist in the
        other node. Otherwise False. This is a recursive method.

        Parameters
        ----------

        node_self : `Element`
            A node to be compared.

        node_other : `Element`
            Another node to be compared.

        Returns
        -------

        boolean
            True if all descendants of node_self exist in node_other, otherwise
            False.
        '''

        for x in ['tag', 'text', 'tail']:
            if node_self.__getattribute__(x) != node_other.__getattribute__(x):
                return False
        for a in node_self.attrib:
            if a not in node_other.attrib or \
               node_self.attrib[a] != node_other.attrib[a]:
                return False
        for child in node_self.getchildren():
            peers = self._get_peers(child, node_other)
            if len(peers) < 1:
                return False
            elif len(peers) > 1:
                raise ConfigError('not unique peer: {}' \
                                  .format(self.get_config_path(child)))
            else:
                schma_node = self.get_schema_node(child)
                if schma_node.get('ordered-by') == 'user' and \
                   schma_node.get('type') == 'leaf-list' or \
                   schma_node.get('ordered-by') == 'user' and \
                   schma_node.get('type') == 'list':
                    elder_siblings = list(child.itersiblings(tag=child.tag,
                                                             preceding=True))
                    if elder_siblings:
                        immediate_elder_sibling = elder_siblings[0]
                        peers_of_immediate_elder_sibling = \
                            self._get_peers(immediate_elder_sibling,
                                            node_other)
                        if len(peers_of_immediate_elder_sibling) < 1:
                            return False
                        elif len(peers_of_immediate_elder_sibling) > 1:
                            raise ConfigError('not unique peer: {}' \
                                              .format(self \
                                                      .get_config_path(child)))
                        elder_siblings_of_peer = \
                            list(peers[0].itersiblings(tag=child.tag,
                                                       preceding=True))
                        if peers_of_immediate_elder_sibling[0] not in \
                           elder_siblings_of_peer:
                            return False
                if not self._node_le(child, peers[0]):
                    return False
        return True

    def _get_peers(self, child_self, parent_other):
        '''_get_peers

        Low-level api: Given a config node, find peers under a parent node.

        Parameters
        ----------

        child_self : `Element`
            An element node on this side.

        parent_other : `Element`
            An element node on the other side.

        Returns
        -------

        list
            A list of children of parent_other who are peers of child_self.
        '''

        peers = parent_other.findall(child_self.tag)
        s_node = self.get_schema_node(child_self)
        if s_node.get('type') == 'leaf-list':
            return list(filter(lambda x:
                               child_self.text == x.text,
                               peers))
        elif s_node.get('type') == 'list':
            keys = self._get_list_keys(s_node)
            return list(filter(lambda x:
                               self._is_peer(keys, child_self, x),
                               peers))
        else:
            return peers

    @staticmethod
    def _is_peer(keys, node_self, node_other):
        '''_is_peer

        Low-level api: Return True if node_self and node_other are considered
        as peer with regards to a set of keys.

        Parameters
        ----------

        keys : `list`
            A list of keys in `{url}tagname` notation.

        node_self : `Element`
            An element node on this side.

        node_other : `Element`
            An element node on the other side.

        Returns
        -------

        list
            True if node_self is a peer of node_other, otherwise, return False.
        '''

        for key in keys:
            s = list(node_self.iterchildren(tag=key))
            o = list(node_other.iterchildren(tag=key))
            if len(s) < 1 or len(o) < 1:
                raise ConfigError('cannot find leaf {} in a node: {}' \
                                  .format(key,
                                          NcConfig.get_config_path(node_self)))
            if len(s) > 1 or len(o) > 1:
                raise ConfigError('not unique leaf {} in a node: {}' \
                                  .format(key,
                                          NcConfig.get_config_path(node_self)))
            if s[0].text != o[0].text:
                return False
        return True

    @staticmethod
    def get_config_path(node):
        '''get_config_path

        High-level api: Return config node path by a list of tags, starting
        from the root node of a model.

        Parameters
        ----------

        node : `Element`
            An element node in config tree.

        Returns
        -------

        list
            A list of tags, starting from the root node of a model. All tags
            are in `{url}tagname` notation.
        '''

        path = list(reversed([a.tag for a in node.iterancestors()]))
        return path[1:] + [node.tag]

    def get_schema_path(self, node):
        '''get_schema_path

        High-level api: Return schema node path by a list of tags, starting
        from the model name.

        Parameters
        ----------

        node : `Element`
            An element node in config tree.

        Returns
        -------

        list
            A list of tags, starting from the model name. All tags are in
            `{url}tagname` notation.
        '''

        s_node = self.get_schema_node(node)
        return self.device.schema_path(s_node)

    def get_schema_node(self, node):
        '''get_schema_node

        High-level api: Return schema node of a config node.

        Parameters
        ----------

        node : `Element`
            An element node in config tree.

        Returns
        -------

        Element
            A schema node of the config node.
        '''

        path = self.get_config_path(node)
        return self.device.get_node(path)

    def get_model_name(self, node):
        '''get_model_name

        High-level api: Return model name of a config node.

        Parameters
        ----------

        node : `Element`
            An element node in config tree.

        Returns
        -------

        Element
            Model name of the config node.
        '''

        return self.device.roots[self.get_config_path(node)[0]]

    def _validate_node(self, node):
        '''_validate_node

        Low-level api: Validate one config node. This is a recursive method.

        Parameters
        ----------

        node : `Element`
            An element node in config tree.

        Returns
        -------

        None
            There is no return of this method.
        '''

        s_node = self.get_schema_node(node)
        if s_node is None:
            raise ConfigError('schema node cannot be found for this config ' \
                              'node: {}'.format(self.get_config_path(node)))
        for tag in operation_tag, insert_tag, value_tag, key_tag:
            if node.get(tag):
                raise ConfigError('your config node contains {}: {}' \
                                  .format(tag, self.get_config_path(node)))
        for child in node.getchildren():
            self._validate_node(child)

    def _validate_config(self):
        '''_validate_config

        Low-level api: Validate config against models. ConfigError is raised
        if config has error.

        Returns
        -------

        None
            There is no return of this method.

        Raises
        ------

        ConfigError
            If config contains error.
        '''

        for child in self.ele.getchildren():
            if child.tag in self.device.roots:
                self._validate_node(child)
            else:
                raise ConfigError('node cannot be found in any models: {}' \
                                  .format(self.get_config_path(child)))

    def _retrieve_config(self, element):
        '''_retrieve_config

        Low-level api: Retrive config from rpc-reply.

        Parameters
        ----------

        element : `Element`
            A rpc-reply.

        Returns
        -------

        Element
            A new element with config data.
        '''

        if not isinstance(element, etree._Element):
            raise TypeError('_retrieve_config() argument must be ' \
                            'lxml.etree.Element, not ' \
                            '{}'.format(type(element)))
        ret = etree.Element(config_tag, nsmap={'nc': nc_url})
        ret.extend(deepcopy(element.xpath('/nc:rpc-reply/nc:data/*',
                            namespaces={'nc': nc_url})))
        ret.extend(deepcopy(element.xpath('/nc:data/*',
                            namespaces={'nc': nc_url})))
        ret.extend(deepcopy(element.xpath('/nc:config/*',
                            namespaces={'nc': nc_url})))
        ret.extend(deepcopy(element.xpath('/nc:rpc/nc:edit-config/nc:config/*',
                            namespaces={'nc': nc_url})))
        ret.extend(deepcopy(element.xpath('/nc:edit-config/nc:config/*',
                            namespaces={'nc': nc_url})))
        return ret

    @property
    def xml(self):
        return etree.tostring(self.ele,
                              encoding='unicode',
                              pretty_print=False)

    @property
    def ns(self):
        ns = {'nc': nc_url}
        urls = {}
        for r in self.ele.xpath('/nc:config/*', namespaces=ns):
            model = self.get_model_name(r)
            urls[model] = set()
            for node in r.iter():
                urls[model] |= set(node.nsmap.values())
        prefix_model = {}
        for model in urls:
            urls[model].discard(nc_url)
            for url in urls[model]:
                if url in ns.values():
                    continue
                elif url in self.device.model_urls[model]:
                    prefix = self.device.model_urls[model][url]
                    if prefix in ns:
                        raise ModelError('prefix {} in {} confilcts with ' \
                                         'the same prefix in {}' \
                                         .format(prefix,
                                                 prefix_model[prefix],
                                                 model))
                    else:
                        ns[prefix] = url
                        prefix_model[prefix] = model
                else:
                    raise ModelError('{} cannot be found in namespaces of ' \
                                     'model {}' \
                                     .format(url, model))
        return ns

    def ns_help(self):
        '''ns_help

        High-level api: Print known namespaces to make writing xpath easier.

        Returns
        -------

        None
            There is no return of this method.
        '''

        pprint.pprint(self.ns)

    def xpath(self, *args, **kwargs):
        '''xpath

        High-level api: It is a wrapper of xpath method in lxml package. If
        namespaces is not given, self.ns is used by default.

        Returns
        -------

        boolean or float or str or list
            Refer to http://lxml.de/xpathxslt.html#xpath-return-values
        '''

        if 'namespaces' not in kwargs:
            kwargs['namespaces'] = self.ns
            return self.ele.xpath(*args, **kwargs)
        else:
            return self.ele.xpath(*args, **kwargs)

    def filter(self, *args, **kwargs):
        '''filter

        High-level api: Filter our config using xpath method. If namespaces is
        not given, self.ns is used by default.

        Returns
        -------

        NcConfig
            A new NcConfig instance which has less content according to your
            xpath expression.
        '''

        ancestors = set()
        filtrates = set()
        config = NcConfig(self.device,  deepcopy(self.ele))
        results = config.xpath(*args, **kwargs)
        if isinstance(results, list):
            for node in results:
                if isinstance(node, etree._Element):
                    ancestors |= set(list(node.iterancestors()))
                    filtrates.add(node)
            if filtrates:
                config._node_filter(config.ele, ancestors, filtrates)
            else:
                config.ele = etree.Element(config_tag, nsmap={'nc': nc_url})
        return config

    def _node_filter(self, node, ancestors, filtrates):
        '''_node_filter

        Low-level api: Remove unrelated nodes in config. This is a recursive
        method.

        Parameters
        ----------

        node : `Element`
            A node to be processed.

        ancestors : `list`
            A list of ancestors of filtrates.

        filtrates : `list`
            A list of filtrates which are result of xpath evaluation.

        Returns
        -------

        None
            There is no return of this method.
        '''

        if node in filtrates:
            return
        elif node in ancestors:
            if node.tag != config_tag:
                s_node = self.get_schema_node(node)
            if node.tag != config_tag and \
               s_node.get('type') == 'list':
                for child in node.getchildren():
                    s_node = self.get_schema_node(child)
                    if s_node.get('is_key') or child in filtrates:
                        continue
                    elif child in ancestors:
                        self._node_filter(child, ancestors, filtrates)
                    else:
                        node.remove(child)
            else:
                for child in node.getchildren():
                    if child in filtrates:
                        continue
                    elif child in ancestors:
                        self._node_filter(child, ancestors, filtrates)
                    else:
                        node.remove(child)
        else:
            node.getparent().remove(node)


class NcConfigDelta(NcConfig):
    '''NcConfigDelta

    Abstraction of a delta of two configs.

    Attributes
    ----------
    device : `object`
        An instance of yang.ncdiff.ModelDevice, which represents a modeled
        device.

    ele : `Element`
        A lxml elementtree which contains the delta.

    xml : `str`
        A string presentation of self.ele.

    ns : `dict`
        A dictionary of namespaces used by the config.
    '''

    def __init__(self, modeldevice, delta, delta2=None):
        '''
        __init__ instantiates a NcConfigDelta instance.
        '''

        self.device = modeldevice
        for i in ['', '2']:
            d = locals().get('delta' + i)
            if d is None:
                setattr(self, 'ele' + i,
                        etree.Element(config_tag, nsmap={'nc': nc_url}))
            elif isinstance(d, str):
                parser = etree.XMLParser(remove_blank_text=True)
                setattr(self, 'ele' + i,
                        self._retrieve_config(etree.XML(d, parser)))
            elif isinstance(d, etree._Element):
                setattr(self, 'ele' + i, self._retrieve_config(d))
            else:
                raise TypeError('NcConfigDelta() argument must be None, or ' \
                                'XML string, or lxml.etree.Element, but not ' \
                                '{}'.format(type(d)))

    def __neg__(self):
        return NcConfigDelta(self.device, self.ele2, self.ele)

    def __pos__(self):
        return self

    def __add__(self, other):
        if type(other) == NcConfig:
            sum = NcConfig(other.device, other.ele)
            NcConfig._node_add(sum, self, sum.ele, self.ele)
            return sum
        else:
            return NotImplemented

    def __sub__(self, other):
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, NcConfigDelta):
            return self._node_le(self.ele, other.ele) and \
                   self._node_le(self.ele2, other.ele2) and \
                   not other._node_le(other.ele, self.ele) and \
                   not other._node_le(other.ele2, self.ele2)
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, NcConfigDelta):
            return other._node_le(other.ele, self.ele) and \
                   other._node_le(other.ele2, self.ele2) and \
                   not self._node_le(self.ele, other.ele) and \
                   not self._node_le(self.ele2, other.ele2)
        else:
            _cmperror(self, other)

    def __le__(self, other):
        if isinstance(other, NcConfigDelta):
            return self._node_le(self.ele, other.ele) and \
                   self._node_le(self.ele2, other.ele2)
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, NcConfigDelta):
            return other._node_le(other.ele, self.ele) and \
                   other._node_le(other.ele2, self.ele2)
        else:
            _cmperror(self, other)

    def __eq__(self, other):
        if isinstance(other, NcConfigDelta):
            return self._node_le(self.ele, other.ele) and \
                   self._node_le(self.ele2, other.ele2) and \
                   other._node_le(other.ele, self.ele) and \
                   other._node_le(other.ele2, self.ele2)
        else:
            _cmperror(self, other)

    def __ne__(self, other):
        if isinstance(other, NcConfigDelta):
            return not self._node_le(self.ele, other.ele) or \
                   not self._node_le(self.ele2, other.ele2) or \
                   not other._node_le(other.ele, self.ele) or \
                   not other._node_le(other.ele2, self.ele2)
        else:
            _cmperror(self, other)
