#!/usr/bin/env python

#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#    Copyright (C) 2006  Csaba Henk  <csaba.henk@creo.hu>
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
logger = logging.getLogger(__name__)
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
        if path == "/":
            return os.lstat("." + path)
        else:
            # get rid of the first /
            if path[0] == "/":
                node = self.doc_root.get(path[1:])
            else:
                node = self.doc_root.get(path)

            if node == None:
                return -errno.ENOENT
        
            #st.st_mode = stat.S_IRUSR + stat.S_IRGRP + stat.S_IROTH
            st.st_uid = os.getuid()
            st.st_gid = os.getgid()
            if isinstance(node, Collection):
                st.st_mode = stat.S_IFDIR | 0o755
                #st.st_mode += stat.S_IFDIR + stat.S_IXUSR + stat.S_IXGRP + stat.S_IXOTH
                st.st_nlink = 2
            else:
                st.st_mode = stat.S_IFREG | 0o444
                #st.st_mode += stat.S_IFREG
                st.st_nlink = 1
                st.st_size = 10
            #mtime = node.metadata["lastModified"]
            #st.st_atime = mtime
            #st.st_mtime = mtime
            #st.st_ctime = mtime
        
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

    def readlink(self, path):
        logger.debug("readlink '" + path +"'")
        return os.readlink("." + path)

    def readdir(self, path, offset):
        logger.debug("readdir '" + path +"'")
        if path == "/":
            node=self.doc_root
            yield fuse.Direntry(".")
            yield fuse.Direntry("..") 
            for file in node:
                logger.debug(file)
                yield fuse.Direntry(file)
        else:
            raise FuseOSError(ENOTDIR)

        #for e in os.listdir("." + path):
        #    yield fuse.Direntry(e)
        

    def unlink(self, path):
        logger.debug("unlink '" + path +"'")
        os.unlink("." + path)

    def rmdir(self, path):
        logger.debug("rmddir" + path)
        os.rmdir("." + path)

    def symlink(self, path, path1):
        logger.debug("symlink '" + path +"'")
        os.symlink(path, "." + path1)

    def rename(self, path, path1):
        logger.debug("rename '" + path +"'")
        os.rename("." + path, "." + path1)

    def link(self, path, path1):
        logger.debug("link '" + path +"'")
        os.link("." + path, "." + path1)

    def chmod(self, path, mode):
        logger.debug("chmod '" + path +"'")
        os.chmod("." + path, mode)

    def chown(self, path, user, group):
        logger.debug("chown '" + path +"'")
        os.chown("." + path, user, group)

    def truncate(self, path, len):
        logger.debug("truncate '" + path +"'")
        f = open("." + path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        logger.debug("mknod" + path)
        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        logger.debug("mkdir" + path)
        os.mkdir("." + path, mode)

    def utime(self, path, times):
        logger.debug("utime" + path)
        os.utime("." + path, times)

#    The following utimens method would do the same as the above utime method.
#    We can't make it better though as the Python stdlib doesn't know of
#    sub-second preciseness in access/modify times.
#
#    def utimens(self, path, ts_acc, ts_mod):
#      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

    def access(self, path, mode):
        logger.debug("access" + path)
        if not os.access("." + path, mode):
            return -EACCES

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
        return os.statvfs(".")

    def fsinit(self):
        logger.info("initializing DocumentRoot")
        logger.debug("fsinit '" + self.root +"'")
        self.doc_root = DocumentRoot(self.root)
        os.chdir(self.root)

    class XochitlFile(object):

        def __init__(self, path, flags, *mode):
            logger.debug("init File '" + path +"'")
            self.file = os.fdopen(os.open("." + path, flags, *mode),
                                  flag2mode(flags))
            self.fd = self.file.fileno()
            if hasattr(os, 'pread'):
                self.iolock = None
            else:
                self.iolock = Lock()

        def read(self, length, offset):
            logger.debug("read '" + self.file.name + "'")
            if self.iolock:
                self.iolock.acquire()
                try:
                    self.file.seek(offset)
                    return self.file.read(length)
                finally:
                    self.iolock.release()
            else:
                return os.pread(self.fd, length, offset)

        def write(self, buf, offset):
            logger.debug("write '" + self.file.name + "'")
            if self.iolock:
                self.iolock.acquire()
                try:
                    self.file.seek(offset)
                    self.file.write(buf)
                    return len(buf)
                finally:
                    self.iolock.release()
            else:
                return os.pwrite(self.fd, buf, offset)

        def release(self, flags):
            logger.debug("release '" + self.file.name + "'")
            self.file.close()

        def _fflush(self):
            logger.debug("_flush '" + self.file.name + "'")
            if 'w' in self.file.mode or 'a' in self.file.mode:
                self.file.flush()

        def fsync(self, isfsyncfile):
            logger.debug("fsync '" + self.file.name + "'")
            self._fflush()
            if isfsyncfile and hasattr(os, 'fdatasync'):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            logger.debug("flush '" + self.file.name + "'")
            self._fflush()
            # cf. xmp_flush() in fusexmp_fh.c
            os.close(os.dup(self.fd))

        def fgetattr(self):
            logger.debug("fgetattr '" + self.file.name + "'")
            return os.fstat(self.fd)

        def ftruncate(self, len):
            logger.debug("ftruncate '" + self.file.name + "'")
            self.file.truncate(len)

        def lock(self, cmd, owner, **kw):
            logger.debug("lock '" + self.file.name + "'")
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
            op = { fcntl.F_UNLCK : fcntl.LOCK_UN,
                   fcntl.F_RDLCK : fcntl.LOCK_SH,
                   fcntl.F_WRLCK : fcntl.LOCK_EX }[kw['l_type']]
            if cmd == fcntl.F_GETLK:
                return -EOPNOTSUPP
            elif cmd == fcntl.F_SETLK:
                if op != fcntl.LOCK_UN:
                    op |= fcntl.LOCK_NB
            elif cmd == fcntl.F_SETLKW:
                pass
            else:
                return -EINVAL

            fcntl.lockf(self.fd, op, kw['l_start'], kw['l_len'])


    def main(self, *a, **kw):
        """ Starting the server """
        self.file_class = self.XochitlFile

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
