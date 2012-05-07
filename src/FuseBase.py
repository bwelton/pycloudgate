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
        #self._servobjs["SugarSync"] = SugarSyncWrapper("conf.cfg")
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
                    # Can write any hash to permission file
                    pass
            

        Fuse.__init__(self, *args, **kw)
        self._root = "/"

    ## shortlist
    ##
    ## Get creation of permissions if not there working
    ## get file[1,2,3,etc.] working, for now we skip duplicates
    def getattr(self, path):
        print "LOOKING UP: " + path
        # Special case for the root
        if path == self._root:
            st = MyStat()
            #TODO: For now, just assuming that if you mounted this, you have
            # permission to do stuff with it
            st.st_mode = stat.S_IFDIR | 0700
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
            if not self._cache.CheckOpen(path):
                st.st_size = ga_ret["st_size"]
            else:
                st.st_size = self._cache.Size(path)
            st.st_mtime = ga_ret["st_mtime"]
            st.st_mode = ga_ret["st_mode"]
            # Handle permissions
            perm_list = self._perms.get(path, None)
            if perm_list != None:
                st.st_uid = perm_list[0]
                st.st_gid = perm_list[1]
                st.st_mode = st.st_mode | perm_list[2]
            # No permissions found, set user/group to current user
            else:
                st.st_uid = os.getuid()
                st.st_gid = os.getgid()
                st.st_mode = st.st_mode | stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC 
            st.print_stat()
            return st
        else:
            return -errno.ENOENT
    
    def readdir(self, path, offset):
        # Special case for top-level directory
        if path == self._root:
            for tld in self._directory:
                yield fuse.Direntry(tld)
        else:
            path_parts = path.split("/")
            tld = path_parts[1]
            if tld in self._directory:
                rd_ret = self._directory[tld].Readdir(path)
                if rd_ret["status"] == True:
                    for name in rd_ret["filenames"]:
                        yield fuse.Direntry(name)

    def _FindTLD (self, path):
        """ Find the top level directory mapping for the path specified

            returns the class to call operation on (or None if not availible)
        """
        print self._directory
        tmp = path[1:]
        tmp = tmp.split("/")
        if tmp[0] in self._directory:
            return self._directory[tmp[0]]
        return None

    def _PickService(self):
        #TODO: If we are making a file in the TLD, use policy to choose which
        # service to place it in. 
        serv_list = self._servobjs.keys()
        if len(serv_list) < 1:
            return None
        # just put it in the first one for now
        return self._servobjs[serv_list[0]]

    def readlink (self, path):
        """ Do nothing here, we dont use symlinks """
        return path

    def unlink(self, path):
        p = self._FindTLD(path)
        uf_path = unfusify_path(path)
        if p != None:
            ret = p.Unlink(path)
            if ret["status"] == False:
                return -errno.ENOENT
            path_parts = uf_path.split("/")
            if len(path_parts) == 1:
                del self._directory[uf_path]
        else:
            return -errno.ENOENT

        
    def rmdir(self, path):
        ## Calls unlink() since in our case they both do the same thing
        return self.unlink(path)

 
    def symlink(self, path, path1):
        ## We do not support symlinks
        return -errno.ENOENT     

     
    def read(self, path, length, offset):
        if self._cache.CheckOpen(path):
            print "FB: read cache hit"
            return self._cache.Read(path, offset, length)
        else:
            print "FB: read cache miss"
            p = self._FindTLD(path)
            if p != None:
                a = p.GetAttr(path)
                ## Read the entire current file if size < 10 MB
                if a["st_size"] < 10000000:
                    
                    r = p.Read(path, 0, a["st_size"])
                    if r["status"] == False:
                        return -errno.EINVAL
                    data = r["data"]
                    self._cache.OpenCache(path, data)
                    if len(data) >= offset + length:
                        return data[offset:offset+length]
                    elif len(data) >= offset:
                        return data[offset:]
                    else:
                        return -errno.ENOENT
                else:
                    data = p.Read(path, offset, length)
                    if data["status"] == False:
                        return -errno.EINVAL
                    else:
                        return data["data"]
            else:
                return -errno.ENOENT
        
    def write(self, path, buf, offset):
        print "FB: write " + path
        print "write buf: " + str(buf)
        print "write offset: " + str(offset)
        if self._cache.CheckOpen(path):
            print "FB: write cache hit"
            self._cache.Write(path, buf, offset)
        else:
            print "FB: write cache miss"
            p = self._FindTLD(path)
            if p != None:
                a = p.GetAttr(path)
                r = p.Read(path, 0, a["st_size"])
                if r["status"] == False:
                    return -errno.EINVAL
                data = r["data"]
                self._cache.OpenCache(path, data)
                if not self._cache.Write(path, buf, offset):
                    return -errno.ENOENT
            else:
                return -errno.ENOENT

    def chmod(self, path, mode):
        pass ## Stub                
    
    def utime(self, path, times):
        pass ## Stub

    def chown(self, path, times):
        pass ## Stub
    
    def truncate(self, path, len):
        print "FB: truncate " + path
        if self._cache.CheckOpen(path):
            print "FB: Truncate hit in cache"
            self._cache.Truncate(path, len)
        else:
            print "FB: Truncate missed in cache"
            p = self._FindTLD(path)
            if p != None:
                status = p.Truncate(path, len) 
                if status["status"] != True:
                    return -errno.ENOENT
            else:
                return -errno.ENOENT

    def getxattr(self, path, name, size):
        pass #stub

    def release(self, path, flags):
        data = self._cache.Close(path)
        if data == None:
            return 0
        p = self._FindTLD(path)
        if p != None:
            status = p.Write(path, data)
            if status["status"] == False:
                return -errno.ENOENT
        else:
            return -errno.ENOENT               
    
    def mknod(self, path, mode, dev):
        print "mknod path: " + str(path)
        print "mknod mode: " + str(mode)
        print "mknod dev: " + str(dev)
        
        # Make sure mode is S_IFREG, otherwise we don't support mknod for it
        if (mode & stat.S_IFREG) != stat.S_IFREG:
            return -errno.EINVAL


        path_parts = unfusify_path(path).split("/")
        p = None
        if len(path_parts) > 1:
            p = self._FindTLD(path)
        else:
            # Check if file exists...only need to do this for TLD
            if path_parts[0] in self._directory:
                return -errno.EEXIST
            
            # Pick what service this file will go to
            p = self._PickService()

            if p == None:
                return -errno.BADF

        mk_ret = p.Mknode(path)
        if mk_ret["status"] == False:
            return mk_ret["errno"]

        if len(path_parts) == 1:
            # Add to TLD. Needs to be after Mknode to make sure it was successful
            self._directory[path_parts[0]] = p

        # Add to permissions
        self._perms[path] = [os.getuid(), os.getgid(), stat.S_IMODE(mode)]

        return 0

    def mkdir(self, path, mode):
        p = self._FindTLD(path)
        uf_path = unfusify_path(path)
        path_parts = uf_path.split("/")
        if p == None:
            
            # Check if we're trying to write to the TLD
            if len(path_parts) == 1:
                p = self._PickService()
                if p == None:
                    return -errno.EINVAL ## Replace with appropriate error
        ret = p.Mkdir(path) 
        if ret["status"] == False:
            return -errno.EINVAL ## Replace with appropriate error
        if len(path_parts) == 1:
            self._directory[uf_path] = p
        self._perms[path] = [os.getuid(), os.getgid(), stat.S_IMODE(mode)]

        return 0
            

    def flush(self, filename):
        if self._cache.CheckOpen(filename) == False:
            return ## We have nothing to flush 

        p = self._FindTLD(filename)
        if p != None:
            total_size = self._cache.Size(filename)
            if self._cache.isWritten(filename): 
                data = self._cache.Read(filename, 0, total_size)
                return self.write(filename, data, 0)
        else:
            return -errno.EINVAL
        
    def fsync(self, filename, isfilesync):
        ## isfilesync doesnt matter to us
        return self.flush(filename)
            
"""
    def readlink(self, path):
        return os.readlink("." + path)

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
