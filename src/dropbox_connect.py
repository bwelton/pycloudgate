import os, stat, errno
from dropbox import client, rest, session
import time

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


class StoredSession(session.DropboxSession):
    """a wrapper around DropboxSession that stores a token to a file on disk"""

    TOKEN_FILE = 'token_store.txt'

    def __init__(self, filename, *args, **kw):
        TOKEN_FILE = filename
        session.DropboxSession.__init__(self, *args, **kw)

    def load_creds(self):
        try:
            stored_creds = open(self.TOKEN_FILE).read()
            self.set_token(*stored_creds.split('|'))
            print "[loaded access token]"
        except IOError:
            pass # don't worry if it's not there

    def write_creds(self, token):
        f = open(self.TOKEN_FILE, 'w')
        f.write("|".join([token.key, token.secret]))
        f.close()

    def delete_creds(self):
        os.unlink(self.TOKEN_FILE)

    def link(self):
        request_token = self.obtain_request_token()
        url = self.build_authorize_url(request_token)
        print "url:", url
        print "Please authorize in the browser. After you're done, press enter."
        raw_input()

        self.obtain_access_token(request_token)
        self.write_creds(self.token)

    def unlink(self):
        self.delete_creds()
        session.DropboxSession.unlink(self)



	

class DropboxLowLevel:
    def __init__(self, filename, *args, **kw):
        APP_KEY = 'c7da4t1qo908jfq'
        APP_SECRET = 'zkzrhtuw2i6e20p'
        ACCESS_TYPE = 'app_folder' 

        self.sess = StoredSession(filename, APP_KEY, APP_SECRET,  access_type=ACCESS_TYPE)
        self.sess.load_creds()
        while not self.sess.is_linked():
            try:
                self.sess.link()
            except rest.ErrorResponse, e:
                pass

        self.api_client = client.DropboxClient(self.sess)

        """ Build cache for all files' metadata requests in a depth first search manner"""
        self.cache = {}
        self.BuildIndex("/")
                 
    def BuildIndex(self, currentPath):
        """ Build cache for metadata request for fold/file at currentPath,
            build for child tree recursively
        """
       
        self.cache[currentPath] = self.api_client.metadata(currentPath)
        directory = self.readdir(currentPath, 0)
        for entry in directory:
            if not entry == "." and not entry == "..":
                self.BuildIndex(currentPath + "/" + entry) 
 


    def getattr(self, path):
        st = MyStat() 
        try:
            if path in self.cache:
                resp = self.cache[path]
            else:
                resp = self.api_client.metadata(path)
                self.cache[path] = resp
          

            if 'is_deleted' in resp and resp['is_deleted']:
                return -errno.ENOENT
            
           
            timeStruct = time.strptime(resp["client_mtime"], "%a, %d %b %Y %H:%M:%S +0000")
            st.st_mtime = int(time.mktime(timeStruct))

                
            st.st_size = resp['bytes']
            if resp["is_dir"]:
	        st.st_mode = stat.S_IFDIR | 0755
                st.st_nlink = 2
            else:
                st.st_mode = stat.S_IFREG | 0755
                st.st_nlink = 1
            self.cache[path] = st
            return st
        except rest.ErrorResponse:
            return -errno.ENOENT
       

    def readdir(self, path, mode):
        dirs = [".", ".."]
        try:
            if path in self.cache:
                resp = self.cache[path]
            else:
                resp = self.api_client.metadata(path)
                self.cache[path] = resp         
        except rest.ErrorResponse as detail:
            return dirs;
       
        if 'contents' in resp:
            for r in  resp['contents']:
                if r['is_dir']:
                    dirs.append((os.path.basename(r['path'])))
        else:
            print path, "is a file!"
 
        return dirs

    def access(self, path, offset):
        try:
            if path in self.cache:
                resp = self.cache[path]
            else:
                resp = self.api_client.metadata(path)
                self.cache[path] = resp         

            if 'is_deleted' in resp and resp['is_deleted']:
               return -errno.EACCES
        except rest.ErrorResponse:
            return -errno.EACCES
        
    def open(self, path, flags):
#        if path != hello_path:
#            return -errno.ENOENT
#        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
#        if (flags & accmode) != os.O_RDONLY:
#            return -errno.EACCES
        pass
    def read(self, path, size, offset):
        try:
            resp = self.api_client.get_file(path)
        except rest.ErrorResponse:
            return -errno.EACCES
        f = resp.read()
        slen = len(f)
        if offset < slen:
            if offset + size > slen:
                size = slen - offset
            buf = f[offset:offset+size]
        else:
            buf = ''
        return buf
    
    def write(self, path, buf, offset):
        try:
            resp = self.api_client.get_file(path)
            f = resp.read()
        except rest.ErrorResponse:
            f = ""
            
        flen = len(f)
        blen = len(buf)
        pad = offset + blen - flen
        if pad > 0:
            f = f + ' ' * pad
        f = f[:offset] + buf + f[offset+blen:]

        try:
            self.cache[path] = self.api_client.put_file(path, f, True)
        except rest.ErrorResponse:
            return -errno.EACCES
        return blen

    def mknod(self, path, mode, dev):
        try:
	    self.cache[path] = self.api_client.put_file(path, " ") 
        except rest.ErrorResponse:
            return -errno.EACCES

    def flush(self, path):
        pass
    
    def setattr(self, *arg):
        pass       

    def unlink(self, path):
        try:
            self.cache[path] = self.api_client.file_delete(path)
        except rest.ErrorResponse:
            return -errno.EACCES

    def rename(self, old, new):
        try:
            self.cache[new] = self.api_client.file_move(old, new)
            del self.cache[old]
        except rest.ErrorResponse:
            return -errno.EACCES

    def mkdir(self, path, mode):
        try:
            self.cache[path] = self.api_client.file_create_folder(path)
        except rest.ErrorResponse:
            return -errno.EACCES

    def ftruncate(self, path, pos):
        try:
            resp = self.api_client.get_file(path)
            f = resp.read()
        except rest.ErrorResponse:
            f = ""
            
        flen = len(f)
        pad = pos - flen
        if pad > 0:
            f = f + ' ' * pad
        f = f[:pos]

        try:
            self.cache[path] = self.api_client.put_file(path, f)
        except rest.ErrorResponse:
            return -errno.EACCES


