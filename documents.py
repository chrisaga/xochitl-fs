"""Classes for reading and creating reMarkable documents. The main entry point
to this module is the DocumentRoot class.

The original module from remarkable-fs needed a sftp connection.
This one use a local backup of the reMarkable documents.

Minimal example:

>>> from documents import DocumentRoot
>>>
>>> root = DocumentRoot("<path where xotchil files are>")
>>> for s in root.children:
...     n=root.get(s)
...     print(n.metadata["visibleName"] + " ", n.size)
...     print(n.metadata)
... 
"""

import fnmatch
import json
import time
import os.path
import itertools
import traceback
from tempfile import NamedTemporaryFile
from uuid import uuid4
#from lazy import lazy
from progress.bar import Bar
from io import BytesIO
"""import remarkable_fs.rM2svg"""
import logging
logger = logging.getLogger("xochitl")


try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

class Node(object):
    """A document or collection on the reMarkable.

    Most of the properties below are read-write, but to persist any changes to
    the reMarkable, you must call save()."""

    def __init__(self, root, id, metadata):
        """Create a new Node object. Unless you are hacking on this module, you
        do not want to do this. Instead, you can get existing documents by
        indexing into the DocumentRoot, or create new ones with
        Collection.new_document or Collection.new_collection.

        For those hacking on this module, creating a node object requires the
        following steps:
        * The correct class must be chosen for the node (either Collection,
          Document or NewDocument).
        * An object of that class is created, passing in the DocumentRoot and
          the node's id and metadata (which is stored as a dict).
          A new id can be created using new_id().
          Metadata can be read using DocumentRoot.read_metadata,
          or created using initial_metadata.
        * The node is registered using DocumentRoot.register_node().
        * The node is added to the directory hierarchy by calling link().
          This can only be called if the parent node has been created,
          which is why it is not done automatically.
        The easiest way to create a node is to write the metadata to the
        reMarkable, and then call DocumentRoot.load_node() to load it.
        That is what Collection.new_collection() does, for example."""

        self.root = root
        self.id = id
        self.metadata = metadata
        self.modified = False
        self.file = None
        if metadata is not None:
            self.file_name = self.name

    def __repr__(self):
        return "%s(%s, %s)" % \
            (type(self).__name__,
             self.id,
             self.name)

    def link(self):
        """Add a node to the directory hierarchy. May only be called after the
        parent node has been loaded. Unless you are hacking on this module, you
        do not want this function."""

        self.parent = self.root.find_node(self.metadata["parent"])
        if self.parent is not None:
            self.parent.add_child(self)

    def _rw(name, doc):
        """Creates a property which references a metadata field. On update, the
        metadata is marked as being modified."""

        def get(self):
            return self.metadata[name]
        def set(self, val):
            self.metadata["synced"] = False
            self.metadata["metadatamodified"] = True
            self.metadata["version"] += 1
            self.metadata[name] = val
            self.modified = True
        return property(fget=get, fset=set, doc=doc)
    
    name = _rw("visibleName", "The document name.")
    deleted = _rw("deleted", "True if the document has been deleted.")
    data_modified = _rw("modified", "True if the data in the document has been modified.")
    pinned = _rw("pinned", "True if the document is bookmarked.")

    @property
    def metadata_modified(self):
        """True if the metadata of the document has been modified."""
        return self.metadata["metadatamodified"]

    @property
    def size(self):
        """The approximate size of the document in bytes."""
        return 0

    @property
    def mtime(self):
        """The modification time of the document."""
        if self.metadata is None:
            return time.time()
        else:
            return int(int(self.metadata["lastModified"])/1000)

    def save(self):
        """Write the document to the reMarkable if it has been changed."""
        if self.modified:
            self.root.write_metadata(self.id, self.metadata)
            self.modified = False

    def rename(self, parent, file_name):
        """Rename the document. Arguments are the parent node and the new filename."""

        self.parent.remove_child(self)
        self.name = strip_extension(file_name)
        self.file_name = file_name
        self.metadata["parent"] = parent.id
        self.parent = parent
        self.parent.add_child(self)
        self.save()
    
    def delete(self):
        """Delete the document."""
        self.parent.remove_child(self)
        self.deleted = True
        self.save()

class Collection(Node):
    """A reMarkable collection.

    You can index into a Collection as if it was a dict. The keys are filenames
    and the values are nodes."""

    def __init__(self, root, id, metadata):
        super(Collection, self).__init__(root, id, metadata)
        self.children = {}
        self.children_pathnames = {}

    def new_collection(self, name):
        """Create a new collection. Returns the created node."""

        id = new_id()
        metadata = initial_metadata(Collection.node_type(), name, self.id)
        self.root.write_metadata(id, metadata)
        self.root.write_content(id, {})
        return self.root.load_node(id)

    def new_document(self, name):
        """Create a new document. Returns the created node.

        The document will not be written to the reMarkable until the node's
        save() method is called."""

        id = new_id()
        metadata = initial_metadata(Document.node_type(), strip_extension(name), self.id)
        node = NewDocument(self.root, id, metadata, name)
        self.root.register_node(node)
        node.link()
        return node

    def add_child(self, child):
        """Add a node to this collection. Called by link().
        Unless you are hacking on this module, you do not want this function."""

        # Remove invalid chars
        name = child.file_name.replace("/", "-")

        # Disambiguate duplicate names e.g. Foo/bar, Foo-bar
        if name in self.children:
            for n in itertools.count(2):
                x = "%s (%d)" % (name, n)
                if x not in self.children:
                    name = x
                    break

        self.children[name] = child
        self.children_pathnames[child] = name

    def remove_child(self, child):
        """Remove a node from this collection. Called by rename() and delete().
        Unless you are hacking on this module, you do not want this function."""

        name = self.children_pathnames[child]
        del self.children[name]
        del self.children_pathnames[child]

    def get(self, file):
        """Look up a file in the collection. Returns a node, or None if not found."""
        return self.children.get(file)

    def items(self):
        """Find all nodes in the collection."""
        return self.children.items()

    def __repr__(self):
        return "%s(%s, %s, %s)" % \
            (type(self).__name__,
             self.id,
             self.name,
             self.children)

    def __getitem__(self, key):
        return self.children[key]

    def __iter__(self):
        return iter(self.children)

    def __contains__(self, item):
        return item in self.children

    @staticmethod
    def node_type():
        return "CollectionType"

class DocumentRoot(Collection):
    """A collection representing the root of the reMarkable directory tree.

    Creating one of these will read in all metadata and construct the directory hierarchy.

    You can index into a DocumentRoot as if it was a dict. The keys are
    filenames and the values are nodes. You can also use find_node() to look up
    a node by id."""

    def __init__(self, rootpath):
        """rootpath - the path of the document root."""

        super(DocumentRoot, self).__init__(self, "", None)
        self.nodes = {"": self}
        """ HK - Documents are on a local filesystem """
        os.chdir(rootpath)
        self.rootpath = rootpath
        self.templates = {}

        """ HK - Documents are on a local filesystem """
        paths = fnmatch.filter(os.listdir(rootpath), '*.metadata')
        bar = Bar("Reading document information", max=len(paths))
        for path in paths:
            id, _ = os.path.splitext(path)
            self.load_node_without_linking(id)
            bar.next()

        for node in self.nodes.values():
            node.link()

        bar.finish()

    def find_node(self, id):
        """Find a node by id. Returns None if not found."""
        return self.nodes.get(id)

    @property
    def name(self):
        return "ROOT"

    def link(self):
        pass

    def load_node(self, id):
        """Read a node from the reMarkable and link it into the tree.
        Unless you are hacking on this module, you do not want this function."""

        node = self.load_node_without_linking(id)
        if node is not None: node.link()
        logger.debug("node /id = '" + node.id + "' name = '" + node.name +"'/ loaded")
        return node

    def load_node_without_linking(self, id):
        """Read a node from the reMarkable, without linking it into the tree.
        Unless you are hacking on this module, you do not want this function."""

        classes = [Document, Collection]
        classes_dict = {cls.node_type(): cls for cls in classes}

        metadata = json.loads(self.read_file(id + ".metadata").decode("utf-8"))
        try:
            cls = classes_dict[metadata["type"]]
        except KeyError:
            cls = Node
          
        try:
            node = cls(self, id, metadata)
            if not node.deleted:
                self.register_node(node)
                return node
        except NoContents:
            pass
        except (IOError, JSONDecodeError):
            traceback.print_exc()

    def register_node(self, node):
        """Register a node object. Unless you are hacking on this module, you do
        not want this function."""
        self.nodes[node.id] = node

    def read_file(self, file):
        """HK - Read a file from local filesystem."""
        return open(file, "rb").read()

    def write_file(self, file, data):
        """HK - Write a file from local filesystem."""
        f = open(file, "wb")
        """ HK - this was used withsftp
        f.set_pipelined()"""
        f.write(memoryview(data))

    def read_json(self, file):
        """Read a JSON file from SFTP and convert to a dict."""
        return json.loads(self.read_file(file).decode("utf-8"))
        
    def write_json(self, file, value):
        """Write a JSON file from SFTP, given as a dict."""
        self.write_file(file, json.dumps(value).encode("utf-8"))

    def read_metadata(self, id):
        """Read the metadata for a given id and convert to a dict."""
        return self.read_json(id + ".metadata")

    def write_metadata(self, id, metadata):
        """Write the metadata for a given id, given as a dict."""
        self.write_json(id + ".metadata", metadata)

    def read_content(self, id):
        """Read the .content file for a given id and convert to a dict."""
        return self.read_json(id + ".content")

    def write_content(self, id, content):
        """Write the .content file for a given id, given as a dict."""
        self.write_json(id + ".content", content)

    def read_template(self, name):
        """Read a particular template file. Returns a local filename."""
        file = self.templates.get(name)
        if file is None:
            data = self.read_file("/usr/share/remarkable/templates/%s.png" % name)
            file = NamedTemporaryFile(suffix = ".png")
            file.write(data)
            file.flush()
            self.templates[name] = file

        return file.name

    # New methods which wer not in the original documents.py

    def get_node_from_path(self, path):
        """Get node object from fuse path"""
        names = path.split('/')
        for entry in names:
            if entry == '':
                node = self
            elif node == None:
                break
            else:
                node = node.get(entry)
        return node


class NoContents(Exception):
    """An exception that indicates that a document only has notes and no PDF or EPUB file."""
    pass

class Document(Node):
    """A single document on the reMarkable."""

    def __init__(self, root, id, metadata):
        super(Document, self).__init__(root, id, metadata)
        self.content = self.root.read_content(id)
        if self.file_type() == "":
            raise NoContents()
        self.file_name = self.name + "." + self.file_type()
        if self.file_type() == "notebook":
            #self._size = self._get_notebook_size()
            self._size = sum(os.path.getsize(os.path.join(self.id, f)) for f in os.listdir(self.id) if os.path.isfile(os.path.join(self.id, f)))
        else:
            self._size = os.stat(self.id + "." + self.file_type()).st_size

    def file_type(self):
        """Return the type of file."""
        return self.content["fileType"]

    #@lazy
    #def file(self):
    #    """A file handle to the file contents itself."""
    #    ext = self.file_type()
    #    """ HK """
    #    return open(self.id + "." + ext, "rb")

    @property
    def size(self):
        return self._size

    def read(self, offset, length):
        """Read length bytes from position offset."""
        self.file.seek(offset)
        return self.file.read(length)
    
    @staticmethod
    def node_type():
        return "DocumentType"

 #   def _get_notebook_size(self):
 #       size = 0
 #       for f in os.listdir(self.id):
 #           #if os.path.isfile(f):
 #           size += os.stat(os.path.join(self.id, f)).st_size
 #       return size

class NewDocument(Node):
    """A newly-created document, which (unlike an object of class Document) can
    be both read and written.

    On calling save(), the document is converted to PDF or EPUB (if necessary)
    and written to the remarkable. If the document could not be converted.
    an IOError is thrown.

    File names starting with a dot are not written to the reMarkable
    (they are treated as temporary files)."""

    def __init__(self, root, id, metadata, filename):
        super(NewDocument, self).__init__(root, id, metadata)
        self.modified = True
        self.buf = BytesIO()
        self.file_name = filename

    @property
    def size(self):
        return len(self.buf.getvalue())

    def read(self, offset, length):
        """Read length bytes from position offset."""
        return self.buf.getvalue()[offset:offset+length]

    def write(self, offset, data):
        """Read data to position offset."""
        self.buf.seek(offset)
        self.buf.write(data)

    def truncate(self, length):
        """Truncate the file to a certain length."""
        self.buf.truncate(length)
    
    def save(self):
        logger.debug("save")
        if not self.file_name.startswith(".") and not self.deleted:
            self.really_save()

    def really_save(self):
        logger.debug("really_save '" + self.name + "'")
        logger.debug(self.modified)
        logger.debug(len(self.buf.getvalue()))
        # Don't save zero-size files - Finder creates them
        if self.modified and len(self.buf.getvalue()) > 0:
            try:
                (filetype, data) = convert_document(self.buf.getvalue())
            except IOError:
                self.delete()
                raise
            content = {
                "extraMetadata": {},
                "fileType": filetype,
                "fontName": "",
                "lastOpenedPage": 0,
                "lineHeight": -1,
                "margins": 100,
                "orientation": "portrait",
                "pageCount": 1,
                "textScale": 1,
                "transform": {
                    "m11": 1,
                    "m12": 0,
                    "m13": 0,
                    "m21": 0,
                    "m22": 1,
                    "m23": 0,
                    "m31": 0,
                    "m32": 0,
                    "m33": 1
                }
            }
            logger.debug("write '" + self.id + ".content'")
            self.root.write_content(self.id, content)
            self.root.write_file(self.id + "." + filetype, data)
            logger.debug("write '" + self.id + "." + filetype +"'")
            super(NewDocument, self).save()

    def rename(self, parent, file_name):
        # If this file starts with a dot and now we want to rename it so it
        # doesn't, we can no longer treat it as a temporary file.
        if not file_name.startswith("."):
            self.really_save()
        super(NewDocument, self).rename(parent, file_name)

def new_id():
    """Generate a new document id."""

    return str(uuid4())

def strip_extension(filename):
    """Remove the extension from a filename, if it is a recognised document type."""

    name, ext = os.path.splitext(filename)
    if ext in [".pdf", ".djvu", ".ps", ".epub"]:
        return name
    return filename

def initial_metadata(node_type, name, parent):
    """The .metadata for a newly-created node.

    node_type - value of 'type' field of .metadata file
    name - node name
    parent - parent id (not node object)"""

    return {
        "deleted": False,
        "lastModified": str(int(time.time()*1000)),
        "metadatamodified": True,
        "modified": True,
        "parent": parent,
        "pinned": False,
        "synced": False,
        "type": node_type,
        "version": 1,
        "visibleName": name
    }

def convert_document(data):
    """Convert a document to PDF or EPUB.

    Input is the document contents as a 'bytes'.

    Returns (filetype, converted contents) where filetype is either "pdf" or
    "epub" and converted contents is a 'bytes'.

    Raises IOError if the file could not be converted."""

    logger.debug("convert_document")
    convert = None
    if data.startswith(b"%PDF"):
        filetype = "pdf"
        logger.debug(filetype)
    elif data.startswith(b"AT&TFORM"):
        filetype = "pdf"
        suffix = ".djvu"
        convert = "ddjvu --format=pdf"
        logger.debug(filetype + "/" + suffix + "/" + convert)
    elif data.startswith(b"%!PS-Adobe"):
        filetype = "pdf"
        suffix = ".ps"
        convert = "ps2pdf"
        logger.debug(filetype + "/" + suffix + "/" + convert)
    elif data.startswith(b"PK"):
        filetype = "epub"
        logger.debug(filetype)
    else:
        raise IOError("Only PDF, epub, djvu and ps format files supported")

    if convert is not None:
        infile = NamedTemporaryFile(suffix = suffix)
        outfile = NamedTemporaryFile(suffix = ".pdf")
        logger.debug("infile = " + infile)
        logger.debug("outfile = " + outfile)
        infile.write(data)
        infile.flush()
        res = os.system("%s %s %s" % (convert, infile.name, outfile.name))
        if res != 0:
            raise IOError("Could not run %s" % convert)
        data = outfile.read()

    return (filetype, data)
