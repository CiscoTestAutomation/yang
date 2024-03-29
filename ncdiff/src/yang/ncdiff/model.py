import math
import os
import re
import queue
import logging
from lxml import etree
from copy import deepcopy
from ncclient import operations
from threading import Thread, current_thread
from pyang import statements
from subprocess import PIPE, Popen
try:
    from pyang.repository import FileRepository
except ImportError:
    from pyang import FileRepository
try:
    from pyang.context import Context
except ImportError:
    from pyang import Context
from .errors import ModelError

# create a logger for this module
logger = logging.getLogger(__name__)

class Model(object):
    '''Model

    Abstraction of a YANG module. It supports str() which returns a string
    similar to the output of 'pyang -f tree'.

    Attributes
    ----------
    name : `str`
        Model name.

    prefix : `str`
        Prefix of the model.

    prefixes : `dict`
        All prefixes used in the model. Dictionary keys are prefixes, and
        values are URLs.

    url : `str`
        URL of the model.

    urls : `dict`
        All URLs used in the model. Dictionary keys are URLs, and values are
        URLs.

    tree : `Element`
        The model tree as an Element object.

    roots : `list`
        All root nodes of the model. Each node is an Element object.

    width : `dict`
        This is used to facilitate pretty print of a model. Dictionary keys are
        nodes in the model tree, and values are indents.
    '''

    def __init__(self, tree):
        '''
        __init__ instantiates a Model instance.
        '''

        self.name = tree.attrib['name']
        ns = tree.findall('namespace')
        self.prefixes = {c.attrib['prefix']: c.text for c in ns}
        self.prefix = tree.attrib['prefix']
        self.url = self.prefixes[self.prefix]
        self.urls = {v: k for k, v in self.prefixes.items()}
        self.tree = self.convert_tree(tree)
        self.roots = [c.tag for c in self.tree.getchildren()]
        self.width = {}

    def __str__(self):
        ret = []
        ret.append('module: {}'.format(self.tree.tag))
        ret += self.emit_children(type='other')
        rpc_lines = self.emit_children(type='rpc')
        if rpc_lines:
            ret += ['', '  rpcs:'] + rpc_lines
        notification_lines = self.emit_children(type='notification')
        if notification_lines:
            ret += ['', '  notifications:'] + notification_lines
        return '\n'.join(ret)

    def emit_children(self, type='other'):
        '''emit_children

        High-level api: Emit a string presentation of the model.

        Parameters
        ----------

        type : `str`
            Type of model content required. Its value can be 'other', 'rpc', or
            'notification'.

        Returns
        -------

        str
            A string presentation of the model that is very similar to the
            output of 'pyang -f tree'
        '''

        def is_type(element, type):
            type_info = element.get('type')
            if type == type_info:
                return True
            if type == 'rpc' or type == 'notification':
                return False
            if type_info == 'rpc' or type_info == 'notification':
                return False
            return True

        ret = []
        for root in [i for i in self.tree.getchildren() if is_type(i, type)]:
            for i in root.iter():
                line = self.get_depth_str(i, type=type)
                name_str = self.get_name_str(i)
                room_consumed = len(name_str)
                line += name_str
                if i.get('type') == 'anyxml' or \
                   i.get('type') == 'anydata' or \
                   i.get('datatype') is not None or \
                   i.get('if-feature') is not None:
                    line += self.get_datatype_str(i, room_consumed)
                ret.append(line)
        return ret

    def get_width(self, element):
        '''get_width

        High-level api: Calculate how much indent is needed for a node.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        Returns
        -------

        int
            Start position from the left margin.
        '''

        parent = element.getparent()
        if parent in self.width:
            return self.width[parent]
        ret = 0
        for sibling in parent.getchildren():
            w = len(self.get_name_str(sibling))
            if w > ret:
                ret = w
        self.width[parent] = math.ceil((ret + 3) / 3.0) * 3
        return self.width[parent]

    @staticmethod
    def get_depth_str(element, type='other'):
        '''get_depth_str

        High-level api: Produce a string that represents tree hierarchy.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        type : `str`
            Type of model content required. Its value can be 'other', 'rpc', or
            'notification'.

        Returns
        -------

        str
            A string that represents tree hierarchy.
        '''

        def following_siblings(element, type):
            if type == 'rpc' or type == 'notification':
                return [s for s in list(element.itersiblings()) \
                        if s.get('type') == type]
            else:
                return [s for s in list(element.itersiblings()) \
                        if s.get('type') != 'rpc' and \
                           s.get('type') != 'notification']

        ancestors = list(reversed(list(element.iterancestors())))
        ret = ' '
        for i, ancestor in enumerate(ancestors):
            if i == 1:
                if following_siblings(ancestor, type):
                    ret += '|  '
                else:
                    ret += '   '
            else:
                if ancestor.getnext() is None:
                    ret += '   '
                else:
                    ret += '|  '
        ret += '+--'
        return ret

    @staticmethod
    def get_flags_str(element):
        '''get_flags_str

        High-level api: Produce a string that represents the type of a node.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        Returns
        -------

        str
            A string that represents the type of a node.
        '''

        type_info = element.get('type')
        if type_info == 'rpc' or type_info == 'action':
            return '-x'
        elif type_info == 'notification':
            return '-n'
        access_info = element.get('access')
        if access_info is None:
            return ''
        elif access_info == 'write':
            return '-w'
        elif access_info == 'read-write':
            return 'rw'
        elif access_info == 'read-only':
            return 'ro'
        else:
            return '--'

    def get_name_str(self, element):
        '''get_name_str

        High-level api: Produce a string that represents the name of a node.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        Returns
        -------

        str
            A string that represents the name of a node.
        '''

        name = self.remove_model_prefix(self.url_to_prefix(element.tag))
        flags = self.get_flags_str(element)
        type_info = element.get('type')
        if type_info is None:
            pass
        elif type_info == 'choice':
            if element.get('mandatory') == 'true':
                return flags + ' ({})'.format(name)
            else:
                return flags + ' ({})?'.format(name)
        elif type_info == 'case':
            return ':({})'.format(name)
        elif type_info == 'container':
            return flags + ' {}'.format(name)
        elif type_info == 'leaf' or \
             type_info == 'anyxml' or \
             type_info == 'anydata':
            if element.get('mandatory') == 'true':
                return flags + ' {}'.format(name)
            else:
                return flags + ' {}?'.format(name)
        elif type_info == 'list':
            if element.get('key') is not None:
                return flags + ' {}* [{}]'.format(name, element.get('key'))
            else:
                return flags + ' {}*'.format(name)
        elif type_info == 'leaf-list':
            return flags + ' {}*'.format(name)
        else:
            return flags + ' {}'.format(name)

    def get_datatype_str(self, element, length):
        '''get_datatype_str

        High-level api: Produce a string that indicates the data type of a node.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        length : `int`
            String length that has been consumed.

        Returns
        -------

        str
            A string that indicates the data type of a node.
        '''

        spaces = ' '*(self.get_width(element) - length)
        type_info = element.get('type')
        ret = ''
        if type_info == 'anyxml' or type_info == 'anydata':
            ret = spaces + '<{}>'.format(type_info)
        elif element.get('datatype') is not None:
            ret = spaces + element.get('datatype')
        if element.get('if-feature') is not None:
            return ret + ' {' + element.get('if-feature') + '}?'
        else:
            return ret

    def prefix_to_url(self, id):
        '''prefix_to_url

        High-level api: Convert an identifier from `prefix:tagname` notation to
        `{namespace}tagname` notation. If the identifier does not have a
        prefix, it is assumed that the whole identifier is a tag name.

        Parameters
        ----------

        id : `str`
            Identifier in `prefix:tagname` notation.

        Returns
        -------

        str
            Identifier in `{namespace}tagname` notation.
        '''

        parts = id.split(':')
        if len(parts) > 1:
            return '{' + self.prefixes[parts[0]] + '}' + parts[1]
        else:
            return '{' + self.url + '}' + id

    def url_to_prefix(self, id):
        '''url_to_prefix

        High-level api: Convert an identifier from `{namespace}tagname` notation
        to `prefix:tagname` notation. If the identifier does not have a
        namespace, it is assumed that the whole identifier is a tag name.

        Parameters
        ----------

        id : `str`
            Identifier in `{namespace}tagname` notation.

        Returns
        -------

        str
            Identifier in `prefix:tagname` notation.
        '''

        ret = re.search('^{(.+)}(.+)$', id)
        if ret:
            return self.urls[ret.group(1)] + ':' + ret.group(2)
        else:
            return id

    def remove_model_prefix(self, id):
        '''remove_model_prefix

        High-level api: If prefix is the model prefix, return tagname without
        prefix. If prefix is not the model prefix, simply return the identifier
        without modification.

        Parameters
        ----------

        id : `str`
            Identifier in `prefix:tagname` notation.

        Returns
        -------

        str
            Identifier in `prefix:tagname` notation if prefix is not the model
            prefix. Or identifier in `tagname` notation if prefix is the model
            prefix.
        '''

        reg_str = '^' + self.prefix + ':(.+)$'
        ret = re.search(reg_str, id)
        if ret:
            return ret.group(1)
        else:
            return id

    def convert_tree(self, element1, element2=None):
        '''convert_tree

        High-level api: Convert cxml tree to an internal schema tree. This
        method is recursive.

        Parameters
        ----------

        element1 : `Element`
            The node to be converted.

        element2 : `Element`
            A new node being constructed.

        Returns
        -------

        Element
            This is element2 after convertion.
        '''

        if element2 is None:
            attributes = deepcopy(element1.attrib)
            tag = attributes['name']
            del attributes['name']
            element2 = etree.Element(tag, attributes)
        for e1 in element1.findall('node'):
            attributes = deepcopy(e1.attrib)
            tag = self.prefix_to_url(attributes['name'])
            del attributes['name']
            e2 = etree.SubElement(element2, tag, attributes)
            self.convert_tree(e1, e2)
        return element2

class DownloadWorker(Thread):

    def __init__(self, downloader):
        Thread.__init__(self)
        self.downloader = downloader

    def run(self):
        while not self.downloader.download_queue.empty():
            try:
                module = self.downloader.download_queue.get(timeout=0.01)
            except queue.Empty:
                pass
            else:
                self.downloader.download(module)
                self.downloader.download_queue.task_done()
        logger.debug('Thread {} exits'.format(current_thread().name))

class ContextWorker(Thread):

    def __init__(self, context):
        Thread.__init__(self)
        self.context = context

    def run(self):
        varnames = Context.add_module.__code__.co_varnames
        while not self.context.modulefile_queue.empty():
            try:
                modulefile = self.context.modulefile_queue.get(timeout=0.01)
            except queue.Empty:
                pass
            else:
                with open(modulefile, 'r', encoding='utf-8') as f:
                    text = f.read()
                kwargs = {
                    'ref': modulefile,
                    'text': text,
                }
                if 'primary_module' in varnames:
                    kwargs['primary_module'] = True
                if 'format' in varnames:
                    kwargs['format'] = 'yang'
                if 'in_format' in varnames:
                    kwargs['in_format'] = 'yang'
                module_statement = self.context.add_module(**kwargs)
                self.context.update_dependencies(module_statement)
                self.context.modulefile_queue.task_done()
        logger.debug('Thread {} exits'.format(current_thread().name))

class CompilerContext(Context):

    def __init__(self, repository):
        Context.__init__(self, repository)
        self.dependencies = None
        self.modulefile_queue = None
        if 'prune' in dir(statements.Statement):
            self.num_threads = 2
        else:
            self.num_threads = 1

    def _get_latest_revision(self, modulename):
        latest = None
        for module_name, module_revision in self.modules:
            if module_name == modulename and (
                latest is None or module_revision > latest
            ):
                latest = module_revision
        return latest

    def get_statement(self, modulename, xpath=None):
        revision = self._get_latest_revision(modulename)
        if revision is None:
            return None
        if xpath is None:
            return self.modules[(modulename, revision)]

        # in order to follow the Xpath, the module is required to be validated
        node_statement = self.modules[(modulename, revision)]
        if node_statement.i_is_validated is not True:
            return None

        # xpath is given, so find the node statement
        xpath_list = xpath.split('/')

        # only absolute Xpaths are supported
        if len(xpath_list) < 2:
            return None
        if (
            xpath_list[0] == '' and xpath_list[1] == '' or
            xpath_list[0] != ''
        ):
            return None

        # find the node statement
        root_prefix = node_statement.i_prefix
        for n in xpath_list[1:]:
            node_statement = self.get_child(root_prefix, node_statement, n)
            if node_statement is None:
                return None
        return node_statement

    def get_child(self, root_prefix, parent, child_id):
        child_id_list = child_id.split(':')
        if len(child_id_list) > 1:
            children = [
                c for c in parent.i_children
                if c.arg == child_id_list[1] and
                c.i_module.i_prefix == child_id_list[0]
            ]
        elif len(child_id_list) == 1:
            children = [
                c for c in parent.i_children
                if c.arg == child_id_list[0] and
                c.i_module.i_prefix == root_prefix
            ]
        return children[0] if children else None

    def update_dependencies(self, module_statement):
        if self.dependencies is None:
            self.dependencies = etree.Element('modules')
        for m in [
            m for m in self.dependencies
            if m.attrib.get('id') == module_statement.arg
        ]:
            self.dependencies.remove(m)
        module_node = etree.SubElement(self.dependencies, 'module')
        module_node.set('id', module_statement.arg)
        module_node.set('type', module_statement.keyword)
        if module_statement.keyword == 'module':
            statement = module_statement.search_one('prefix')
            if statement is not None:
                module_node.set('prefix', statement.arg)
            statement = module_statement.search_one("namespace")
            if statement is not None:
                namespace = etree.SubElement(module_node, 'namespace')
                namespace.text = statement.arg
        if module_statement.keyword == 'submodule':
            statement = module_statement.search_one("belongs-to")
            if statement is not None:
                belongs_to = etree.SubElement(module_node, 'belongs-to')
                belongs_to.set('module', statement.arg)

        dependencies = set()
        for parent_node_name, child_node_name, attr_name in [
            ('includes', 'include', 'module'),
            ('imports', 'import', 'module'),
            ('revisions', 'revision', 'date'),
        ]:
            parent = etree.SubElement(module_node, parent_node_name)
            statements = module_statement.search(child_node_name)
            if statements:
                for statement in statements:
                    child = etree.SubElement(parent, child_node_name)
                    child.set(attr_name, statement.arg)
                    if child_node_name in ['include', 'import']:
                        dependencies.add(statement.arg)
        return dependencies

    def write_dependencies(self):
        dependencies_file = os.path.join(
            self.repository.dirs[0],
            'dependencies.xml',
        )
        write_xml(dependencies_file, self.dependencies)

    def read_dependencies(self):
        dependencies_file = os.path.join(
            self.repository.dirs[0],
            'dependencies.xml',
        )
        self.dependencies = read_xml(dependencies_file)

    def load_context(self):
        self.modulefile_queue = queue.Queue()
        for filename in os.listdir(self.repository.dirs[0]):
            if filename.lower().endswith('.yang'):
                filepath = os.path.join(self.repository.dirs[0], filename)
                self.modulefile_queue.put(filepath)
        for x in range(self.num_threads):
            worker = ContextWorker(self)
            worker.daemon = True
            worker.name = 'context_worker_{}'.format(x)
            worker.start()
        self.modulefile_queue.join()
        self.write_dependencies()

    def validate_context(self):
        revisions = {}
        for mudule_name, module_revision in self.modules:
            if mudule_name not in revisions or (
                mudule_name in revisions and
                revisions[mudule_name] < module_revision
            ):
                revisions[mudule_name] = module_revision
        self.validate()
        if 'prune' in dir(statements.Statement):
            for mudule_name, module_revision in revisions.items():
                self.modules[(mudule_name, module_revision)].prune()

    def internal_reset(self):
        self.modules = {}
        self.revs = {}
        self.errors = []
        for mod, rev, handle in self.repository.get_modules_and_revisions(
                self):
            if mod not in self.revs:
                self.revs[mod] = []
            revs = self.revs[mod]
            revs.append((rev, handle))


class ModelDownloader(object):
    '''ModelDownloader

    Abstraction of a Netconf schema downloader.

    Attributes
    ----------
    device : `ModelDevice`
        Model name.

    pyang_plugins : `str`
        Path to pyang plugins.

    dir_yang : `str`
        Path to yang files.

    yang_capabilities : `str`
        Path to capabilities.txt file in the folder of yang files.

    need_download : `bool`
        True if the content of capabilities.txt file disagrees with device
        capabilities exchange. False otherwise.
    '''

    def __init__(self, nc_device, folder):
        '''
        __init__ instantiates a ModelDownloader instance.
        '''

        self.device = nc_device
        self.pyang_plugins = os.path.dirname(__file__) + '/plugins'
        self.dir_yang = os.path.abspath(folder)
        if not os.path.isdir(self.dir_yang):
            os.makedirs(self.dir_yang)
        self.yang_capabilities = self.dir_yang + '/capabilities.txt'
        repo = FileRepository(path=self.dir_yang)
        self.context = CompilerContext(repository=repo)
        self.download_queue = queue.Queue()
        self.num_threads = 2

    @property
    def need_download(self):
        if os.path.isfile(self.yang_capabilities):
            with open(self.yang_capabilities, 'r') as f:
                c = f.read()
            if c == '\n'.join(sorted(list(self.device.server_capabilities))):
                return False
        return True

    def download_all(self, check_before_download=True):
        '''download_all

        High-level api: Convert cxml tree to an internal schema tree. This
        method is recursive.

        Parameters
        ----------

        check_before_download : `bool`
            True if checking capabilities.txt file is required.

        Returns
        -------

        None
            Nothing returns.
        '''

        # check the content of self.yang_capabilities
        if check_before_download:
            if not self.need_download:
                logger.info('Skip downloading as the content of {} matches ' \
                            'device hello message' \
                            .format(self.yang_capabilities))
                return

        # clean up folder self.dir_yang
        for root, dirs, files in os.walk(self.dir_yang):
            for f in files:
                os.remove(os.path.join(root, f))

        # download all
        self.to_be_downloaded = set(self.device.models_loadable)
        self.downloaded = set()
        while self.to_be_downloaded:
            self.download(self.to_be_downloaded.pop())

        # write self.yang_capabilities
        with open(self.yang_capabilities, 'w') as f:
            f.write('\n'.join(sorted(list(self.device.server_capabilities))))

    def download(self, module):
        '''download

        High-level api: Download a module schema.

        Parameters
        ----------

        module : `str`
            Module name that will be downloaded.

        Returns
        -------

        None
            Nothing returns.
        '''

        import_r = '^[ |\t]+import[ |\t]+([a-zA-Z0-9-]+)[ |\t]+[;{][ |\t]*$'
        include_r = '^[ |\t]+include[ |\t]+([a-zA-Z0-9-]+)[ |\t]*[;{][ |\t]*$'

        logger.debug('Downloading {}.yang...'.format(module))
        try:
            from .device import ModelDevice
            reply = super(ModelDevice, self.device) \
                    .execute(operations.retrieve.GetSchema, module)
        except operations.rpc.RPCError:
            logger.warning("Module or submodule '{}' cannot be downloaded" \
                           .format(module))
            return
        if reply.ok:
            fname = self.dir_yang + '/' + module + '.yang'
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(reply.data)
            self.downloaded.add(module)
            imports = set()
            includes = set()
            for line in reply.data.splitlines():
                match = re.search(import_r, line)
                if match:
                    imports.add(match.group(1).strip())
                    continue
                match = re.search(include_r, line)
                if match:
                    includes.add(match.group(1).strip())
                    continue
            s = (imports | includes) - self.downloaded - self.to_be_downloaded
            if s:
                logger.info('{} requires submodules: {}' \
                            .format(module, ', '.join(s)))
                self.to_be_downloaded.update(s)
        else:
            logger.warning("module or submodule '{}' cannot be downloaded:\n{}" \
                           .format(module, reply._raw))


class ModelCompiler(object):
    '''ModelCompiler

    Abstraction of a YANG file compiler.

    Attributes
    ----------
    pyang_plugins : `str`
        Path to pyang plugins.

    dir_yang : `str`
        Path to yang files.

    dependencies : `Element`
        Dependency infomation stored in an Element object.
    '''

    def __init__(self, folder):
        '''
        __init__ instantiates a ModelCompiler instance.
        '''

        self.pyang_plugins = os.path.dirname(__file__) + '/plugins'
        self.dir_yang = os.path.abspath(folder)
        self.build_dependencies()

    def _xml_from_cache(self, name):
        try:
            cached_name = os.path.join(self.dir_yang, f"{name}.xml")
            if os.path.exists(cached_name):
                with(open(cached_name, "r", encoding="utf-8")) as fh:
                    parser = etree.XMLParser(remove_blank_text=True)
                    tree = etree.XML(fh.read(), parser)
                    return tree
        except Exception:
            # make the cache safe: any failure will just bypass the cache
            logger.info(f"Unexpected failure during cache read of {name}, refreshing cache", exc_info=True)
        return None

    def _to_cache(self, name, value):
        cached_name = os.path.join(self.dir_yang, f"{name}.xml")
        with open(cached_name, "wb") as fh:
            fh.write(value)

    def build_dependencies(self):
        '''build_dependencies

        High-level api: Briefly compile all yang files and find out dependency
        infomation of all modules.

        Returns
        -------

        None
            Nothing returns.
        '''

        from_cache = self._xml_from_cache("$dependencies")
        if from_cache is not None:
            self.dependencies = from_cache
            return

        cmd_list = ['pyang', '--plugindir', self.pyang_plugins]
        cmd_list += ['-p', self.dir_yang]
        cmd_list += ['-f', 'pyimport']
        cmd_list += [self.dir_yang + '/*.yang']
        logger.info('Building dependencies: {}'.format(' '.join(cmd_list)))
        p = Popen(' '.join(cmd_list), shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        logger.info('pyang return code is {}'.format(p.returncode))
        logger.debug(stderr.decode())
        parser = etree.XMLParser(remove_blank_text=True)

        self._to_cache("$dependencies",stdout)

        self.dependencies = etree.XML(stdout.decode(), parser)

    def get_dependencies(self, module):
        '''get_dependencies

        High-level api: Get dependency infomationa of a module.

        Parameters
        ----------

        module : `str`
            Module name that is inquired about.

        Returns
        -------

        tuple
            A tuple with two elements: a set of imports and a set of depends.
        '''

        imports = set()
        for m in list(filter(lambda i: i.get('id') == module,
                             self.dependencies.findall('./module'))):
            imports.update(set(i.get('module')
                               for i in m.findall('./imports/import')))
        depends = set()
        for m in self.dependencies.getchildren():
            if list(filter(lambda i: i.get('module') == module,
                           m.findall('./imports/import'))):
                depends.add(m.get('id'))
            if list(filter(lambda i: i.get('module') == module,
                           m.findall('./includes/include'))):
                depends.add(m.get('id'))
        return (imports, depends)

    def compile(self, module):
        '''compile

        High-level api: Compile a module.

        Parameters
        ----------

        module : `str`
            Module name that is inquired about.

        Returns
        -------

        Model
            A Model object.
        '''
        cached_tree = self._xml_from_cache(module)

        if cached_tree is not None:
            m = Model(cached_tree)
            return m

        imports, depends = self.get_dependencies(module)
        file_list = list(imports | depends) + [module]
        cmd_list = ['pyang', '-f', 'cxml', '--plugindir', self.pyang_plugins]
        cmd_list += ['-p', self.dir_yang]
        cmd_list += [self.dir_yang + '/' + f + '.yang' for f in file_list]
        logger.info('Compiling {}.yang: {}'.format(module,
                                                   ' '.join(cmd_list)))
        p = Popen(' '.join(cmd_list), shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        logger.info('pyang return code is {}'.format(p.returncode))
        if p.returncode == 0:
            logger.debug(stderr.decode())
        else:
            logger.error(stderr.decode())
        parser = etree.XMLParser(remove_blank_text=True)

        self._to_cache(module, stdout)

        out = stdout.decode()
        tree = etree.XML(out, parser)
        return Model(tree)


class ModelDiff(object):
    '''ModelDiff

    Abstraction of differences between two Model instances. It supports str()
    which returns a string illustrating the differences between model1 and
    model2.

    Attributes
    ----------
    model1 : `Model`
        First Model instance.

    model2 : `Model`
        Second Model instance.

    tree : `Element`
        The model difference tree as an Element object.

    width : `dict`
        This is used to facilitate pretty print of a model. Dictionary keys are
        nodes in the model tree, and values are indents.
    '''

    __str__ = Model.__str__
    get_width = Model.get_width

    def __init__(self, model1, model2):
        '''
        __init__ instantiates a Model instance.
        '''

        self.model1 = model1
        self.model2 = model2
        self.width = {}
        if model1.tree.tag == model2.tree.tag:
            self.tree = etree.Element(model1.tree.tag)
            if id(self.model1) != id(self.model2):
                self.compare_nodes(model1.tree, model2.tree, self.tree)
        else:
            raise ValueError("cannot generate diff of different modules: " \
                             "'{}' vs '{}'" \
                             .format(model1.tree.tag, model2.tree.tag))

    def __bool__(self):
        if self.tree.getchildren():
            return True
        else:
            return False

    def emit_children(self, type='other'):
        '''emit_children

        High-level api: Emit a string presentation of the model.

        Parameters
        ----------

        type : `str`
            Type of model content required. Its value can be 'other', 'rpc', or
            'notification'.

        Returns
        -------

        str
            A string presentation of the model that is very similar to the
            output of 'pyang -f tree'
        '''

        def is_type(element, type):
            type_info = element.get('type')
            if type == type_info:
                return True
            if type == 'rpc' or type == 'notification':
                return False
            if type_info == 'rpc' or type_info == 'notification':
                return False
            return True

        ret = []
        for root in [i for i in self.tree.getchildren() if is_type(i, type)]:
            for i in root.iter():
                line = Model.get_depth_str(i, type=type)
                name_str = self.get_name_str(i)
                room_consumed = len(name_str)
                line += name_str
                if i.get('diff') is not None:
                    line += self.get_diff_str(i, room_consumed)
                ret.append(line)
        return ret

    def get_name_str(self, element):
        '''get_name_str

        High-level api: Produce a string that represents the name of a node.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        Returns
        -------

        str
            A string that represents the name of a node.
        '''

        if element.get('diff') == 'added':
            return self.model2.get_name_str(element)
        else:
            return self.model1.get_name_str(element)

    def get_diff_str(self, element, length):
        '''get_diff_str

        High-level api: Produce a string that indicates the difference between
        two models.

        Parameters
        ----------

        element : `Element`
            A node in model tree.

        length : `int`
            String length that has been consumed.

        Returns
        -------

        str
            A string that indicates the difference between two models.
        '''

        spaces = ' '*(self.get_width(element) - length)
        return spaces + element.get('diff')

    @staticmethod
    def compare_nodes(node1, node2, ret):
        '''compare_nodes

        High-level api: Compare node1 and node2 and put the result in ret.

        Parameters
        ----------

        node1 : `Element`
            A node in a model tree.

        node2 : `Element`
            A node in another model tree.

        ret : `Element`
            A node in self.tree.

        Returns
        -------

        None
            Nothing returns.
        '''

        for child in node2.getchildren():
            peer = ModelDiff.get_peer(child.tag, node1)
            if peer is None:
                ModelDiff.copy_subtree(ret, child, 'added')
            else:
                if ModelDiff.node_equal(peer, child):
                    continue
                else:
                    if child.attrib['type'] in ['leaf-list', 'leaf']:
                        ModelDiff.copy_node(ret, child, 'modified')
                    else:
                        ret_child = ModelDiff.copy_node(ret, child, '')
                        ModelDiff.compare_nodes(peer, child, ret_child)
        for child in node1.getchildren():
            peer = ModelDiff.get_peer(child.tag, node2)
            if peer is None:
                ModelDiff.copy_subtree(ret, child, 'deleted')

    @staticmethod
    def copy_subtree(ret, element, msg):
        '''copy_subtree

        High-level api: Copy element as a subtree and put it as a child of ret.

        Parameters
        ----------

        element : `Element`
            A node in a model tree.

        msg : `str`
            Message to be added.

        ret : `Element`
            A node in self.tree.

        Returns
        -------

        None
            Nothing returns.
        '''

        sub_element = ModelDiff.process_attrib(deepcopy(element), msg)
        ret.append(sub_element)
        return sub_element

    @staticmethod
    def copy_node(ret, element, msg):
        '''copy_node

        High-level api: Copy element as a node without its children and put it
        as a child of ret.

        Parameters
        ----------

        element : `Element`
            A node in a model tree.

        msg : `str`
            Message to be added.

        ret : `Element`
            A node in self.tree.

        Returns
        -------

        None
            Nothing returns.
        '''
        sub_element = etree.SubElement(ret, element.tag, attrib=element.attrib)
        ModelDiff.process_attrib(sub_element, msg)
        return sub_element

    @staticmethod
    def process_attrib(element, msg):
        '''process_attrib

        High-level api: Delete four attributes from an ElementTree node if they
        exist: operation, insert, value and key. Then a new attribute 'diff' is
        added.

        Parameters
        ----------

        element : `Element`
            A node needs to be looked at.

        msg : `str`
            Message to be added in attribute 'diff'.

        Returns
        -------

        Element
            Argument 'element' is returned after processing.
        '''

        attrib_required = ['type', 'access', 'mandatory']
        for node in element.iter():
            for attrib in node.attrib.keys():
                if attrib not in attrib_required:
                    del node.attrib[attrib]
            if msg:
                node.attrib['diff'] = msg
        return element

    @staticmethod
    def get_peer(tag, node):
        '''get_peer

        High-level api: Find all children under the node with the tag.

        Parameters
        ----------

        tag : `str`
            A tag in `{namespace}tagname` notaion.

        node : `Element`
            A node to be looked at.

        Returns
        -------

        Element or None
            None if not found. An Element object when found.
        '''

        peers = node.findall(tag)
        if len(peers) < 1:
            return None
        elif len(peers) > 1:
            raise ModelError("not unique tag '{}'".format(tag))
        else:
            return peers[0]

    @staticmethod
    def node_equal(node1, node2):
        '''node_equal

        High-level api: Evaluate whether two nodes are equal.

        Parameters
        ----------

        node1 : `Element`
            A node in a model tree.

        node2 : `Element`
            A node in another model tree.

        Returns
        -------

        bool
            True if node1 and node2 are equal.
        '''

        if ModelDiff.node_less(node1, node2) and \
           ModelDiff.node_less(node2, node1):
            return True
        else:
            return False

    @staticmethod
    def node_less(node1, node2):
        '''node_less

        Low-level api: Return True if all descendants of node1 exist in node2.
        Otherwise False. This is a recursive method.

        Parameters
        ----------

        node1 : `Element`
            A node in a model tree.

        node2 : `Element`
            A node in another model tree.

        Returns
        -------

        bool
            True if all descendants of node1 exist in node2, otherwise False.
        '''

        for x in ['tag', 'text', 'tail']:
            if node1.__getattribute__(x) != node2.__getattribute__(x):
                return False
        for a in node1.attrib:
            if a not in node2.attrib or \
               node1.attrib[a] != node2.attrib[a]:
                return False
        for child in node1.getchildren():
            peers = node2.findall(child.tag)
            if len(peers) < 1:
                return False
            elif len(peers) > 1:
                raise ModelError("not unique peer '{}'".format(child.tag))
            else:
                if not ModelDiff.node_less(child, peers[0]):
                    return False
        return True
