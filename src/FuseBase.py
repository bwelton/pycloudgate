#!/usr/bin/env python

# Fuse front-end of pycloudgate

import os, sys
import errno
import stat
import fcntl

import fuse
from fuse import Fuse

from CacheBase import CacheClass
from GoogleCloudInterface import GoogleCloudService
#from SugarSyncInterface import SugarSyncWrapper
#from dropbox_service import DropboxService


if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

fuse.feature_assert('stateful_files', 'has_init')


def flag2mode(flags):
    md = {os.O_RDONLY: 'r', os.O_WRONLY: 'w', os.O_RDWR: 'w+'}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags | os.O_APPEND:
        m = m.replace('w', 'a', 1)

    return m

def fusify_path(path):
    if path[0] != "/":
        return "/" + str(path)
    return str(path)

def unfusify_path(path):
    if path[0] == "/":
        return str(path[1:])
    return str(path)

class MyStat:
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

    def print_stat(self):
        print "size: " + str(self.st_size)
        print "last modified: " + str(self.st_mtime)
        print "mode: " + str(self.st_mode)
        print "uid: " + str(self.st_uid)
        print "gid: " + str(self.st_gid)
        print "nlink: " + str(self.st_nlink)


class PyCloudGate(Fuse):

    def __init__(self, *args, **kw):
        self._cache = CacheClass()
        self._services = ["DropBox", "GoogleCloud", "SugarSync"]  
        self._servobjs = {}
        self._directory = {} # Directory map
        self._perms = {}

        ## Initialize Classes
        #TODO: Handle errors of unauthenticated services
        self._servobjs["GoogleCloud"] = GoogleCloudService("cs699wisc_samanas")
        #self._servobjs["SugarSync"] = SugarSyncWrapper("conf.ini")
        #self._servobjs["DropBox"] = DropBoxService()

        ## loop over all successfully created interfaces
        for s in self._servobjs:
            serv = self._servobjs.get(s, None)
            # If successful...
            if serv != None:
                # get TLDs and add to directory structure
                tmp_tld = serv.GetTLD()
                if tmp_tld["status"] == True:
                    del tmp_tld["status"]
                    for direntry in tmp_tld.keys():
                        tld_key = unfusify_path(direntry)

                        # Handle duplicate file names
                        #TODO: I'm confused about policy, so I'm just
                        # skipping duplicates right now...
                        if tld_key in self._directory:
                            print "Skipping duplicate TLD file name " + tld_key
                            continue
                        # tmp_tld could just be replaced by serv??
                        self._directory[tld_key] = tmp_tld[direntry]
                else:
                    print "Getting top-level directory of "+str(s)+" failed."
                # Get permissions
                tmp_perms = serv.GetPermissionFile()
                if tmp_perms["status"] == True:
                    for fn in tmp_perms["data"].keys():
                        if fn not in self._perms:
                            self._perms[fusify_path(fn)] = tmp_perms["data"][fn]
                        else:
                            pass
                else:
                    pass
            

        Fuse.__init__(self, *args, **kw)
        self._root = "/"

    ## shortlist
    ##
    ## Get creation of permissions if not there working
    ## get file[1,2,3,etc.] working, for now we skip duplicates
    def getattr(self, path):
        # Special case for the root
        if path == self._root:
            st = MyStat()
            #TODO: For now, just assuming that if you mounted this, you have
            # permission to do stuff with it
            st.st_mode = stat.S_IFDIR | 700
            st.st_nlink = 2
            return st

        # retrieve top-level dir name
        path_parts = path.split("/")
        tld = path_parts[1]
        if tld in self._directory:
            # Choose appropriate object to call GetAttr on with tld
            ga_ret = self._directory[tld].GetAttr(path)
            if ga_ret["status"] == False:
                return -errno.ENOENT
            st = MyStat()
            st.st_size = ga_ret["st_size"]
            st.st_mtime = ga_ret["st_mtime"]
            st.st_mode = ga_ret["st_mode"]
            # Handle permissions
            perm_list = self._perms.get(path, None)
            if perm_list != None:
                st.st_uid = perm_list[0]
                st.st_gid = perm_list[1]
                st.st_mode = st.st_mode | perm_list[2]

            st.print_stat()
            return st
        else:
            return -errno.ENOENT

"""
    def readlink(self, path):
        return os.readlink("." + path)

    def readdir(self, path, offset):
        for e in os.listdir("." + path):
            yield fuse.Direntry(e)

    def unlink(self, path):
        os.unlink("." + path)

    def rmdir(self, path):
        os.rmdir("." + path)

    def symlink(self, path, path1):
        os.symlink(path, "." + path1)

    def rename(self, path, path1):
        os.rename("." + path, "." + path1)

    def link(self, path, path1):
        os.link("." + path, "." + path1)

    def chmod(self, path, mode):
        os.chmod("." + path, mode)

    def chown(self, path, user, group):
        os.chown("." + path, user, group)

    def truncate(self, path, len):
        f = open("." + path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        os.mkdir("." + path, mode)

    def utime(self, path, times):
        os.utime("." + path, times)
"""

#    The following utimens method would do the same as the above utime method.
#    We can't make it better though as the Python stdlib doesn't know of
#    subsecond preciseness in acces/modify times.
#  
#    def utimens(self, path, ts_acc, ts_mod):
#      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

"""
    def access(self, path, mode):
        if not os.access("." + path, mode):
            return -EACCES
"""

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
#            # We are asked for size of the attr list, ie. joint size of attrs
#            # plus null separators.
#            return len("".join(aa)) + len(aa)
#        return aa

    #def statfs(self):
        #return os.statvfs(".")

    #def fsinit(self):
        #os.chdir(self.root)


''' NOT USING THIS CLASS '''
"""
    class XmpFile(object):

        def __init__(self, path, flags, *mode):
            self.file = os.fdopen(os.open("." + path, flags, *mode),
                                  flag2mode(flags))
            self.fd = self.file.fileno()

        def read(self, length, offset):
            self.file.seek(offset)
            return self.file.read(length)

        def write(self, buf, offset):
            self.file.seek(offset)
            self.file.write(buf)
            return len(buf)

        def release(self, flags):
            self.file.close()

        def _fflush(self):
            if 'w' in self.file.mode or 'a' in self.file.mode:
                self.file.flush()

        def fsync(self, isfsyncfile):
            self._fflush()
            if isfsyncfile and hasattr(os, 'fdatasync'):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            self._fflush()
            # cf. xmp_flush() in fusexmp_fh.c
            os.close(os.dup(self.fd))

        def fgetattr(self):
            return os.fstat(self.fd)

        def ftruncate(self, len):
            self.file.truncate(len)

        def lock(self, cmd, owner, **kw):
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
"""

def main():

    usage = Fuse.fusage

    server = PyCloudGate(version="%prog " + fuse.__version__,
                 usage=usage,
                 dash_s_do='setsingle')

    server.parse(errex=1)

    server.main()


if __name__ == '__main__':
    main()
