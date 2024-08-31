#!/usr/bin/env python

#    reMarkable (xochitl) document FUSE wrapper
#
#    This is a work in progress based on the Xmp example provided by python-fuse#    Only a few methods actually work.
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#

from __future__ import print_function

import os, sys, stat, errno
import fcntl
from threading import Lock
# pull in some spaghetti to make this stuff work without fuse-py being installed
try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse

from documents import Collection, Document, NewDocument, DocumentRoot
import logging
logger = logging.getLogger("xochitl")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('/tmp/xochitl.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

if not hasattr(fuse, '__version__'):
    raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")

fuse.fuse_python_api = (0, 2)

fuse.feature_assert('stateful_files', 'has_init')


def flag2mode(flags):
    md = {os.O_RDONLY: 'rb', os.O_WRONLY: 'wb', os.O_RDWR: 'wb+'}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags | os.O_APPEND:
        m = m.replace('w', 'a', 1)

    return m

class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class Xochitl(Fuse):

    def __init__(self, *args, **kw):

        Fuse.__init__(self, *args, **kw)

        # do stuff to set up your filesystem here, if you want
        #import thread
        #thread.start_new_thread(self.mythread, ())
        self.root = '/'
        logger.debug("self.root=" + self.root)

#    def mythread(self):
#
#        """
#        The beauty of the FUSE python implementation is that with the python interp
#        running in foreground, you can have threads
#        """
#        print "mythread: started"
#        while 1:
#            time.sleep(120)
#            print "mythread: ticking"

    def getattr(self, path):
        logger.debug("getattr '" + path +"'")
        st = MyStat()
        node = self.documents.get_node_from_path(path)

        if node == None:
            return -errno.ENOENT
    
        st.st_mode = stat.S_IRUSR + stat.S_IRGRP + stat.S_IROTH
        st.st_uid = os.getuid()
        st.st_gid = os.getgid()
        if isinstance(node, Collection):
            st.st_mode += stat.S_IFDIR + stat.S_IXUSR + stat.S_IXGRP + stat.S_IXOTH
            st.st_nlink = 2
        else:
            st.st_mode += stat.S_IFREG
            st.st_nlink = 1
            st.st_size = node.size
    
        logger.debug(node.metadata)
        mtime = node.mtime
        st.st_atime = mtime
        st.st_mtime = mtime
        st.st_ctime = mtime
    
        logger.debug(st.st_mode)
        logger.debug(st.st_ino)
        logger.debug(st.st_dev)
        logger.debug(st.st_nlink)
        logger.debug(st.st_uid)
        logger.debug(st.st_gid)
        logger.debug(st.st_size)
        logger.debug(st.st_atime)
        logger.debug(st.st_mtime)
        logger.debug(st.st_ctime)
        return st

#   I'm pretty sure symbolic links are not implemented in reMarkable docs
#    def readlink(self, path):
#        logger.debug("readlink '" + path +"'")
#        return os.readlink("." + path)

    def readdir(self, path, offset):
        """Read directory entries"""
        logger.debug("readdir '" + path +"'")
        node = self.documents.get_node_from_path(path)
        if node == None:
            return -errno.ENOENT
        yield fuse.Direntry(".")
        yield fuse.Direntry("..") 
        for file in node:
            logger.debug(file)
            yield fuse.Direntry(file)

    def unlink(self, path):
        """Set a document 'deleted' (data are still there) """
        logger.debug("unlink '" + path +"'")
        node = self.node(path)
        if isinstance(node, Collection):
            return -errno.EISDIR
        node.delete()

    def rmdir(self, path):
        """Remove an empty directory"""
        logger.debug("rmddir" + path)
        node = self.node(path)
        if not isinstance(node, Collection):
            return -errno.ENOTDIR
        if len(node.items()) > 0:
            return -errno.ENOTEMPTY
        node.delete()
        #os.rmdir("." + path)

#   I'm pretty sure symbolic links are not implemented in reMarkable docs
#    def symlink(self, path, path1):
#        logger.debug("symlink '" + path +"'")
#        os.symlink(path, "." + path1)

    def rename(self, old, new):
        """Rename or move"""
        logger.debug("rename '" + old +"' -> '" + new + "'")
        old_node = self.documents.get_node_from_path(old)
        new_node = self.documents.get_node_from_path(new)
        new_parent = self.documents.get_node_from_path(os.path.dirname(new))
        new_file = os.path.basename(new)

        try:
            if new_node is None:
                # It's a move with a filename
                logger.debug("It's a move with a filename")
                old_node.rename(new_parent, new_file)
            elif isinstance(new_node, Collection):
                # It's a move into a directory
                logger.debug("It's a move into a directory")
                old_node.rename(new_node, old_node.name)
            else:
                # It's overwriting a file.
                # Don't allow this because it might be an editor doing
                # a rename to overwrite the file with a new version.
                # This would lose all handwritten notes associated with the file.
                logging.debug("It's overwriting a file.")
                return -errno.EEXIST
        except IOError:
            # File conversion error
            traceback.print_exc()
            return -errno.EIO

#   I'm pretty sure hard links are not implemented in reMarkable docs
#    def link(self, path, path1):
#        logger.debug("link '" + path +"'")
#        os.link("." + path, "." + path1)

#   No such thing as mode
#    def chmod(self, path, mode):
#        logger.debug("chmod '" + path +"'")
#        os.chmod("." + path, mode)

#   No document owner
#    def chown(self, path, user, group):
#        logger.debug("chown '" + path +"'")
#        os.chown("." + path, user, group)

    def truncate(self, path, len):
        """Truncate a file to the specified length"""
        """TODO: investigate and test"""
        logger.debug("truncate '" + path +"'")
        node = self.node(path)
        # Don't allow overwriting existing files
        # (changing this needs more code in documents.py)
        if hasattr(node, "truncate"):
            node.truncate(length)
        else:
            return -errno.EPERM
        #f = open("." + path, "a")
        #f.truncate(len)
        #f.close()

#   Doesn't seem useful in this context
#    def mknod(self, path, mode, dev):
#        logger.debug("mknod" + path)
#        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        """Make an empty directory"""
        logger.debug("mkdir" + path)
        parent, name = self.parent(path)
        if name in parent:
            return -errno.EEXIST
        parent.new_collection(name)
        #os.mkdir("." + path, mode)

#   TODO: was not implemented in original remarkable-fs
#         although it makes sense in the reMarkable context
    def utime(self, path, times):
        """Set the access and modified times of the file specified by path."""
        logger.debug("utime" + path)
        return -errno.ENOSYS
        #os.utime("." + path, times)

#    The following utimens method would do the same as the above utime method.
#    We can't make it better though as the Python stdlib doesn't know of
#    sub-second preciseness in access/modify times.
#
#    def utimens(self, path, ts_acc, ts_mod):
#      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

    def access(self, path, mode):
        """Check access to the node data on disk"""
        logger.debug("access" + path)
        node = self.documents.get_node_from_path(path)
        # asume that if node exist we have access
        # documents.py already accessed it
        if node == None:
            return -errno.EACCES

#    This is how we could add stub extended attribute handlers...
#    (We can't have ones which aptly delegate requests to the underlying fs
#    because Python lacks a standard xattr interface.)
#
#    def getxattr(self, path, name, size):
#        val = name.swapcase() + '@' + path
#        if size == 0:
#            # We are asked for size of the value.
#            return len(val)
#        return val
#
#    def listxattr(self, path, size):
#        # We use the "user" namespace to please XFS utils
#        aa = ["user." + a for a in ("foo", "bar")]
#        if size == 0:
#            # We are asked for size of the attr list, i.e. joint size of attrs
#            # plus null separators.
#            return len("".join(aa)) + len(aa)
#        return aa

    def statfs(self):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (i.e., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
            - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        logger.debug("statfs '" + self.root + "'")
        # Just return the underlying real filesystem
        # remarkable-fs was making arbitrary data
        # maybe there is something smarter to do
        return os.statvfs(".")

    def fsinit(self):
        """Initialize the xochitl filesystem from the data files"""
        logger.info("initializing DocumentRoot")
        logger.debug("fsinit '" + self.root +"'")
        self.documents = DocumentRoot(self.root)
        os.chdir(self.root)

    def node(self, path):
        """Get node object from fuse path"""
        #TODO: see Remarkable.node() in original remarkabe-fs/fs.py
        #      figure-out the FuseOSError from fusepy
        return self.documents.get_node_from_path(path)

    def parent(self, path):
        """Find the parent node of a path in the filesystem. The path does not
        have to exist but its parent directory should. Generally used when
        creating a new file.

        Returns (parent node, basename). Raises ENOENT if the parent directory
        does not exist and EBUSY if the path is the root directory."""
        
        path = os.path.normpath(path)
        dir, file = os.path.split(path)

        if file == '':
            # Root directory - cannot be moved/created/deleted
            #TODO:
            #raise FuseOSError(EBUSY)
            return (None, '')

        return (self.node(dir), file)


    class XochitlFile(object):

        def __init__(self, path, flags, *mode):
            """Initialize a custom file object"""
            logger.debug("__init__ File '" + path +"'")
            logger.debug(flags)
            logger.debug(mode)

            self.node = self.fs.node(path)
            if self.node == None:
                # New Document
                logger.debug("Creating '" + path + "'")
                parent, name = self.fs.parent(path)
                
                # Don't allow overwriting existing files, for paranoia
                if name in parent:
                    raise OSError(errno.EEXIST, os.strerror(errno.EEXIST),
                            path)

                self.node = parent.new_document(name)
                #file_path = "./." + self.node.id
            else:
                # Don't allow overwriting existing files
                # (changing this needs more code in documents.py)
                if flags & os.O_WRONLY or flags & os.O_RDWR:
                    logger.debug(os.strerror(errno.EPERM))
                    raise OSError(errno.EPERM, os.strerror(errno.EPERM), path)

                elif self.node.file_type() != "notebook":
                    #We have an underlying file we can read or write
                    #TODO: how to get file annotations ?
                    #TODO: how do we open and read .notebook files
                    file_path = "./" + self.node.id + "." + self.node.file_type()
                    logger.debug("Open underlying file")
                    logger.debug(file_path)
                    self.node.file = open(file_path, flag2mode(flags))
                    self.fd = self.node.file.fileno()

                #if hasattr(os, 'pread'):
                #    self.iolock = None
                #else:
                #    self.iolock = Lock()

        def open(self, path, flags):
            """Do we have to implement this since it's done in __init__()"""
            logger.debug("open '" + path + "'")
            return self

        def create(self, path, flags):
            """Do we have to implement this since it could be done in __init__()"""
            logger.debug("create '" + path + "'")
            return -errno.EPERM

        def read(self, length, offset):
            #logger.debug("read '" + self.file.name + "'")
            #we don't have a file.name, probably due to fdopen()
            #TODO: investigate
            logger.debug("read '" + self.node.name + "' (" + self.node.file_type() + ")")
            #if self.iolock:
            #    self.iolock.acquire()
            #    try:
            #        self.file.seek(offset)
            #        return self.file.read(length)
            #    finally:
            #        self.iolock.release()
            #else:
            #    return os.pread(self.fd, length, offset)
            if isinstance(self.node, Collection):
                raise OSError(errno.EISDIR, os.strerror(errno.EISDIR),
                            self.node.name)

            if self.node.file_type() == "notebook":
                #We don't know how to read them (yet)
                raise OSError(errno.ENOSYS,
                        os.strerror(errno.ENOSYS) + " (read)",
                        self.node.name)
                
            return self.node.read(offset, length) 

        def write(self, buf, offset):
            """Write in a xochitl node.
               nothing on the underliying filesystem untill node.save()"""
            logger.debug("read '" + self.node.name + "' (" + self.node.file_type() + ")")
            #if self.iolock:
            #    self.iolock.acquire()
            #    try:
            #        self.file.seek(offset)
            #        self.file.write(buf)
            #        return len(buf)
            #    finally:
            #        self.iolock.release()
            #else:
            #    return os.pwrite(self.fd, buf, offset)
            if isinstance(self.node, Collection):
                raise OSError(errno.EISDIR, os.strerror(errno.EIO),
                            self.node.name)
            self.node.write(offset, buf)
        
            if self.node.file_type() == "notebook":
                #We don't know how to write them (yet)
                raise OSError(errno.ENOSYS,
                        os.strerror(errno.ENOSYS) + " (write)",
                        self.node.name)
                
            return len(buf)

        def release(self, flags):
            """File is closed and no more accessible"""
            logger.debug("release")
            if self.node.file != None:
                self.node.file.close()
                self.node.file = None

            if isinstance(self.node, NewDocument):
                # Node is saved now. Let it be a regular node
                nodeid = self.node.id
                self.node.parent.remove_child(self.node)
                self.node = self.fs.documents.load_node(nodeid)

        def _fflush(self):
            logger.debug("_fflush '" + self.node.name + "' " + type(self.node).__name__)
            logger.debug(isinstance(self.node, NewDocument))
            logger.debug(isinstance(self.node, Document))
            #if 'w' in self.node.file.mode or 'a' in self.node.file.mode:
            #    self.node.file.flush()
            try:
                self.node.save()
            except IOError:
                # File conversion error
                traceback.print_exc()
                raise OSError(errno.EIO, os.strerror(errno.EIO),
                        self.node.name)

        def fsync(self, isfsyncfile):
            logger.debug("fsync")
            self._fflush()
            if isfsyncfile and hasattr(os, 'fdatasync'):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            logger.debug("flush")
            self._fflush()
            
            # cf. xmp_flush() in fusexmp_fh.c
            # TODO: something to do with the fdopen
            #os.close(os.dup(self.fd))

        def fgetattr(self):
            logger.debug("fgetattr")
            #return os.fstat(self.fd)
            st = MyStat()

            node = self.node
            if node == None:
                return -errno.ENOENT
        
            st.st_mode = stat.S_IRUSR + stat.S_IRGRP + stat.S_IROTH + stat.S_IFREG
            st.st_uid = os.getuid()
            st.st_gid = os.getgid()
            st.st_nlink = 1
            st.st_size = node.size
        
            mtime = node.mtime
            st.st_atime = mtime
            st.st_mtime = mtime
            st.st_ctime = mtime

            return st


            

        def ftruncate(self, len):
            logger.debug("ftruncate")
            self.node.file.truncate(len)

        #def lock(self, cmd, owner, **kw):
        #    logger.debug("lock")
            # The code here is much rather just a demonstration of the locking
            # API than something which actually was seen to be useful.

            # Advisory file locking is pretty messy in Unix, and the Python
            # interface to this doesn't make it better.
            # We can't do fcntl(2)/F_GETLK from Python in a platfrom independent
            # way. The following implementation *might* work under Linux.
            #
            # if cmd == fcntl.F_GETLK:
            #     import struct
            #
            #     lockdata = struct.pack('hhQQi', kw['l_type'], os.SEEK_SET,
            #                            kw['l_start'], kw['l_len'], kw['l_pid'])
            #     ld2 = fcntl.fcntl(self.fd, fcntl.F_GETLK, lockdata)
            #     flockfields = ('l_type', 'l_whence', 'l_start', 'l_len', 'l_pid')
            #     uld2 = struct.unpack('hhQQi', ld2)
            #     res = {}
            #     for i in xrange(len(uld2)):
            #          res[flockfields[i]] = uld2[i]
            #
            #     return fuse.Flock(**res)

            # Convert fcntl-ish lock parameters to Python's weird
            # lockf(3)/flock(2) medley locking API...
        #    op = { fcntl.F_UNLCK : fcntl.LOCK_UN,
        #           fcntl.F_RDLCK : fcntl.LOCK_SH,
        #           fcntl.F_WRLCK : fcntl.LOCK_EX }[kw['l_type']]
        #    if cmd == fcntl.F_GETLK:
        #        return -EOPNOTSUPP
        #    elif cmd == fcntl.F_SETLK:
        #        if op != fcntl.LOCK_UN:
        #            op |= fcntl.LOCK_NB
        #    elif cmd == fcntl.F_SETLKW:
        #        pass
        #    else:
        #        return -EINVAL

        #    fcntl.lockf(self.fd, op, kw['l_start'], kw['l_len'])


    def main(self, *a, **kw):
        """ Starting the server """
        self.file_class = self.XochitlFile
        self.file_class.fs = self

        return Fuse.main(self, *a, **kw)


def main():

    usage = """
Userspace nullfs-alike: mirror the filesystem tree from some point on.

""" + Fuse.fusage

    server = Xochitl(version="%prog " + fuse.__version__,
                 usage=usage,
                 dash_s_do='setsingle')

    server.parser.add_option(mountopt="root", metavar="PATH", default='/',
                             help="mirror filesystem from under PATH [default: %default]")
    server.parse(values=server, errex=1)

    try:
        if server.fuse_args.mount_expected():
            os.chdir(server.root)
    except OSError:
        print("can't enter root of underlying filesystem", file=sys.stderr)
        sys.exit(1)

    logger.info("server.root=" + server.root)
    logger.info("starting server")
    server.main()


if __name__ == '__main__':
    main()
