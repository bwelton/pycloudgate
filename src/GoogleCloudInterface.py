# Google storage imports
import StringIO
import os
import shutil
import tempfile
import time
from oauth2_plugin import oauth2_plugin
import boto

# my imports
import re
import time
import datetime
import pickle
from function_template import ServiceObject
import sys
import stat
import errno

GOOGLE_STORAGE = 'gs'
LOCAL_FILES = 'file'

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


class GoogleCloudService(ServiceObject):
    def __init__(self, default_bucket, filename=None):
        """ Setup's parameters for connection to service. Does other initialization

            Takes in a filename (string) returns nothing
        """
        self.root = '/'
        self.perm_file = "/.goog_perms"
        
        # Set up our filesystem!

        # build dictionary of buckets

        self.default_bucket = str(default_bucket)
        self.bdata = dict()
        self.add_local_bucket()
        self.build_dir_index(self.default_bucket)


    #### Helper functions
    
    # Expects name to be a str
    def add_local_bucket(self):
        self.bdata['dir_index'] = dict()
        self.bdata['dir_index_built'] = False

    def iso8601time2unix(self, time_str):
        time_split = str(time_str).split('.')
        #print "time_split: " + str(time_split)
        ptime = datetime.datetime.strptime(time_split[0], "%Y-%m-%dT%H:%M:%S")
        return time.mktime(ptime.timetuple())

    def build_dir_index(self, bucket_name):
        #print "building directory index..."
        uri = boto.storage_uri(bucket_name, GOOGLE_STORAGE)
        tmp_dict = self.bdata['dir_index']
        poss_folders = dict()

        ## Can't get_bucket return error?? I don't know...
        for obj in uri.get_bucket():
            path_parts = str(obj.name).split("/")
            folder = str(obj.name).split("/"+path_parts[-1])
            #print "folder: " + folder[0]

            st = MyStat()
            st.st_mode = stat.S_IFREG
            st.st_nlink = 1

            # get metadata
            st.st_size = int(obj.size)
            st.st_mtime = self.iso8601time2unix(obj.last_modified)

            obj_dict = dict()
            obj_dict['stat'] = st
            obj_dict['obj'] = obj
            tmp_dict[str(obj.name)] = obj_dict
            #print "Adding " + str(obj.name) + " to the index AS OBJ"
            
            ret = tmp_dict.get(folder[0],None)
            if ret == None:
                ret = poss_folders.get(folder[0],None)
                if ret == None or ret.st_mtime < st.st_mtime:
                    poss_folders[folder[0]] = st

        # Add the folders we have found to the index
        for pf in poss_folders.keys():
            st = MyStat()
            st.st_mode = stat.S_IFDIR
            st.st_nlink = 2
            st.st_mtime = poss_folders[pf].st_mtime
            obj_dict = dict()
            obj_dict['stat'] = st
            obj_dict['obj'] = None
            tmp_dict[pf] = obj_dict
            #print "Adding " + pf + " to the index AS DIR"
        
        self.bdata['dir_index_built'] = True
        #print "...Done!"

    def googlify_path(self,path):
        spath = str(path)
        if spath[0] == '/':
            return spath[1:len(path)]

        return spath

    def GetTLD (self):
        """ Gets the top level directory/file information. 

            returns a hash table: 
                ret = { }
            where every directory/file has a key with the following
            output:
                ret["somedirname"] = self
                ret["status"] = True or False
                self =  this class
        """
        ret = {}
        ret["status"] = False
        rd_ret = {}
        if self.bdata['dir_index_built'] == False:
            self.build_dir_index(self.default_bucket)
        
        rd_ret = self.Readdir('/')
        if rd_ret["status"] == False:
            return ret
        for fn in rd_ret["filenames"]:
            ret[fn] = self

        ret["status"] = True
        return ret

    def Read (self, pathname, offset, size): 
        """ similar to fuse. returns data as a string 
        
            returns a dictionary with the following keys

                ret["status"] = True for completed, False for failed
                ret["data"] = data read from the file
        """
        ret = {}
        ret["status"] = False
        ret["data"] = None
        ret["errno"] = 0
        #print "read path: " + str(pathname)
        #print "read size: " + str(size)
        #print "read offset: " + str(offset)

        obj_name = self.googlify_path(pathname)
        cur_objdict = self.bdata['dir_index'].get(obj_name, None)

        if cur_objdict == None:
            ret["errno"] = -errno.EBADF
            return ret

        if (cur_objdict['stat'].st_mode & stat.S_IFDIR) == stat.S_IFDIR:
            ret["errno"] = -errno.EISDIR
            return ret

        out_str = None

        try:
            out_str = cur_objdict['obj'].get_contents_as_string()
        except boto.exception.GSResponseError,e:
            ret["errno"] = -errno.EINVAL
            return ret
        
        file_len = cur_objdict['stat'].st_size
        if size == -1:
            size = file_len
        
        if len(out_str) != file_len:
            ret["errno"] = -errno.EINVAL
            return ret

        out_buf = ''

        if offset < file_len:
            if offset + size > file_len:
                size = file_len - offset
            out_buf = out_str[offset:offset+size]

        ret["data"] = out_buf
        ret["status"] = True
            
        return ret

    def Write(self, pathname, data):
        """ Write data out to the file specified.

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        ret["status"] = False

        obj_name = self.googlify_path(pathname)

        tmp_nod = self.bdata['dir_index'].get(obj_name, None)

        if tmp_nod == None:
            mk_ret = self.Mknode(pathname)
            if mk_ret["status"] == True:
                tmp_nod = self.bdata['dir_index'].get(obj_name, None)
                if tmp_nod == None:
                    return ret
            else:
                return ret

        if (tmp_nod['stat'].st_mode & stat.S_IFDIR) == stat.S_IFDIR:
            return ret

        #TODO: Time needs to be Google provided
        #TODO: Update modified times of all? parent directories
        tmp_nod['stat'].st_mtime = int(time.time())
        tmp_nod['stat'].st_size = len(data)

        tmp_nod['obj'].set_contents_from_string(data)

        #TODO: Check for errors
        ret["status"] = True

        return ret

    def Mknode (self, pathname): 
        """ Make a new file in the pathname specified. 

            pathname = string
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        ret["status"] = False
        ret["errno"] = 0

        obj_name = self.googlify_path(pathname)

        # Return error if file already exists
        if obj_name in self.bdata['dir_index']:
            ret["errno"] = -errno.EEXIST
            return ret

        # Create object
        uri = None
        uri = boto.storage_uri(self.default_bucket + "/" + obj_name,GOOGLE_STORAGE)
        if uri == None or uri == "":
            ret["errno"] = -errno.EFAULT
            return ret

        new_obj = None
        try:
            new_obj = uri.new_key()
        except boto.exception.BotoServerError,e:
            return ret

        if new_obj == None or new_obj == "":
            ret["errno"] = -errno.EINVAL
            return ret

        new_obj.set_contents_from_string('')

        st = MyStat()
        st.st_mode = stat.S_IFREG
        st.st_nlink = 1

        # set metadata (should be in setattr??)
        st.st_size = 0
        #TODO: Make this google provided
        mtime = int(time.time())
        st.st_mtime = mtime

        nod_dict = dict()
        nod_dict['stat'] = st
        nod_dict['obj'] = new_obj
        self.bdata['dir_index'][str(obj_name)] = nod_dict
        ret["status"] = True

        # Create any directories that didn't already exist and are a part of
        # this path
        path_list = obj_name.split("/")
        cur_folder = ""
        for i in path_list:
            cur_folder = cur_folder + i
            #print "cur_folder: " + cur_folder
            tmp = self.bdata['dir_index'].get(cur_folder,None)
            if tmp == None:
                new_dir = dict()
                dir_st = MyStat()
                dir_st.st_mode = stat.S_IFDIR
                dir_st.st_nlink = 2
                dir_st.st_size = 0
                dir_st.st_mtime = mtime

                new_dir['stat'] = dir_st
                new_dir['obj'] = None
                self.bdata['dir_index'][cur_folder] = new_dir

            # Traverse one directory down
            cur_folder = cur_folder + "/"

        return ret

    def Unlink (self, pathname):
        """ Deletes a file from the service

            pathname = string

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        ret["status"] = False

        obj_name = self.googlify_path(pathname)
        nod_dict = self.bdata['dir_index'].get(str(obj_name), None)
        if (nod_dict['stat'].st_mode & stat.S_IFDIR) == stat.S_IFDIR:
            # set errno to -errno.EISDIR
            return ret
        elif (nod_dict['stat'].st_mode & stat.S_IFREG) == stat.S_IFREG:
            if nod_dict['obj'].delete_marker == False:
                #TODO: Check for delete error...checking delete_marker
                # creates false negatives
                nod_dict['obj'].delete()

                # Now remove file from index
                del self.bdata['dir_index'][obj_name]
                ret["status"] = True
        else:
            print "UNRECOGNIZED FILE MODE!!!"

        return ret

    def GetPermissionFile (self):
        """ Gets the data inside of the permission file stored on the service
        
            returns a dictionary with the following keys:
                   
                ret["status"] = True for completed, False for failed
                ret["data"] = Permission file data (hash table: hash["pathname"] = permissions).
                              Permissions are as follows [UID,GID,MODE (777 - octet format)]
        """
        ret = {}
        ret["status"] = False
        ret["data"] = None

        rd_ret = self.Read(self.perm_file, 0, -1)
        if rd_ret["status"] == True:
            if rd_ret["data"] != "":
                ret["status"] = True
                ret["data"] = pickle.loads(rd_ret["data"])

        return ret

    def WritePermissions (self, hashtable):
        """ Writes the permissions data to the permission file.

            hashtable - hash table of same format as GetPermissionFile()

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        ret["status"] = False
        
        wr_ret = self.Write(self.perm_file, pickle.dumps(hashtable))

        ret["status"] = wr_ret["status"]

        return ret

    def Truncate(self, filename, pos):
        """ Truncates a file to the position specified 

            filename - string
            pos - integer showing what position to truncate the file too

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        ret["status"] = False
        rd_ret = {}
        wr_ret = {}
        rd_ret = self.Read(filename, 0, pos)
        if rd_ret["status"] == False:
            return ret

        wr_ret = self.Write(filename, rd_ret["data"])
        if wr_ret["status"] == False:
            return ret

        ret["status"] = True
        return ret

    def Mkdir (self, pathname):
        """ Makes the directory specified 

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        print "path is " + pathname

        # Create either a bucket if at top-level, else an object
        print "Creating an object directory"
        obj_name = self.googlify_path(pathname)

        st = MyStat()
        st.st_mode = stat.S_IFDIR
        st.st_size = 0
        #TODO: Switch to google provided time
        st.st_mtime = int(time.time())
        st.st_nlink = 2

        nod_dict = dict()
        nod_dict['stat'] = st
        nod_dict['obj'] = None
        self.bdata['dir_index'][obj_name] = nod_dict

        ret["status"] = True
        return ret

    # I think we need to actually return a full list of the objects in the
    # directory and not care about offset, so that the higher level can yield
    # a generator.
    def Readdir (self, path):
        """ Return a directory listing for the given directory at offset
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
                ret["filenames"] =  filename for file at offset in directory
        """
        ret = {}
        ret["status"] = False
        ret["filenames"] = None
        ret["errno"] = 0
        dirent_list = []
        dir_name = self.googlify_path(path)
        path_list = dir_name.split("/")
        #print "path_list: " + str(path_list)
        #print "READDIR PATH NAME: " + path + "(" + str(len(path_list)) + ")"
        #print "READDIR DIR NAME: " + dir_name

        # If dir_name is empty, then we are reading the top-level dir
        if dir_name != '':
            # Check if dir exists
            tmp_key = self.bdata['dir_index'].get(dir_name, None)
            if tmp_key == None:
                ret["errno"] = -errno.ENOENT
                return ret

            # Check if what was found is a dir
            if (tmp_key['stat'].st_mode & stat.S_IFDIR) != stat.S_IFDIR:
                ret["errno"] = -errno.ENOTDIR
                return ret
        
        # else list objects (in the same 'directory')
        if dir_name == '':
            for obj in self.bdata['dir_index'].keys():
                sobj = str(obj)
                if sobj.find('/') == -1:
                    dirent_list.append(sobj)
        else:
            r = re.compile(dir_name+'\/*')
            f_contents = filter(r.match, self.bdata['dir_index'].keys())
            #print f_contents 
            for f in f_contents:
                filter_list = f.split("/")
                # all the files one level deeper and matching our regex
                # should be listed
                if len(filter_list) == (len(path_list) + 1):
                    dirent_list.append(filter_list[-1])

        ret["filenames"] = dirent_list
        ret["status"] = True
        return ret

    def GetAttr (self, path):
        """ Returns the attributes for the file (stat structure)

            returns a dictionary with the following keys:
                ret["status"] = True for completed, False for Failed
                ret["st_size"] = size (bytes) of the file
                ret["st_mtime"] = datetime class with last modification
                ret["st_mode"] = type of file and permissions
                ret["errno"] = error number of failure

        """

        # Set up return hash
        ret = {}
        ret["status"] = False
        ret["st_size"] = 0
        ret["st_mtime"] = 0
        ret["st_mode"] = 0
        ret["errno"] = 0

        st = MyStat()
        #print "path: " + path
        # If this is a request for slash.. just return a generic stat
        if(path == self.root):
            # Don't return permissions, top-level takes care of that
            st.st_mode = stat.S_IFDIR
            st.st_nlink = 2
            ret["status"] = True
            ret["st_mode"] = st.st_mode
            ret["errno"] = 0
            return ret

        # Lookup whether this file exists
        goog_obj_name = self.googlify_path(path)

        go_ret = self.bdata['dir_index'].get(goog_obj_name, None)

        if go_ret == None:
            ret["errno"] = -errno.ENOENT
        else:
            st = go_ret['stat']
            ret["status"] = True
            ret["st_size"] = st.st_size
            ret["st_mtime"] = st.st_mtime
            ret["st_mode"] = st.st_mode

        return ret
                
## Minor Testing            
if __name__ == "__main__":
    # init
    t_class = GoogleCloudService("cs699wisc_samanas")

    # Test GetTLD()
    tlds = t_class.GetTLD()
    print "printing tld list: "
    for x in tlds:
        print x

    # Test Mknode
    filedir = "testfile.png"
    status = t_class.Mknode(filedir)
    if status["status"] == True:
        print "File created correctly"
    else:
        print "File not created correctly"

    # Test Write
    data = "It's not a pyramid scheme, it's a triangle of opportunity."
    ret = t_class.Write(filedir, data)
    if ret["status"] == True:
        print "File correctly written"
    else:
        print "File incorrectly written"

    ret = t_class.Read(filedir, 0, -1)
    if ret["status"] ==  True:
        if ret["data"] == data:
            print "Data Read Correctly"
        else:
            print "Data does not match"
            print "data: " + str(ret["data"])
    else:
        print "Could not read data!"
    
    print "Reading file6"
    ret = t_class.Read("nfs/file6", 0, -1)
    if ret["status"] ==  True:
        if ret["data"] == "file6wr":
            print "Data Read Correctly"
        else:
            print "Data does not match"
            print "data: " + str(ret["data"])
    else:
        print "Could not read data!"
    
    status = t_class.Readdir("Mobile Photos")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("Mobile Photos/a")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("Mobile Photos/b")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("Mobile Photos/a/b/c/d")
    print status["filenames"]
    print status["status"]

    ret = t_class.Truncate(filedir, 26)
    if ret["status"] ==  True:
        print "Truncate returned successfully"
    else:
        print "Could not truncate data!"

    ret = t_class.Read(filedir, 0, -1)
    if ret["status"] ==  True:
        if ret["data"] == data[0:26]:
            print "Data Read Correctly"
        else:
            print "Data does not match"
        print "data: " + str(ret["data"])
        print "data2: " + str(data[0:26])
    else:
        print "Could not read data!"
    
    status =  t_class.Unlink(filedir)
    if status["status"] == True:
        print "File Successfully Deleted"
    else:
        print "File failed to delete"

    permfile = t_class.GetPermissionFile()
    if permfile["status"] == False:
        print "Could not get permission file"
    else:
        print "Permissions found!"

    fakePermissions = {"testperm": [1000, 2000, int("777",10)]}
    status = t_class.WritePermissions(fakePermissions)
    if status["status"] == False:
        print "Did not write out permission file correctly"
    else:
        print "Permission file written correctly"

    permfile = t_class.GetPermissionFile()
    if permfile["status"] == True:
        if permfile["data"]["testperm"] == [int("1000",10), int("2000",10), int("777",10)]:
            print "Permission retrieved Correctly"
        else:
            print "Permission did not save correctly"
    else:
        print "Could not open permission file"

    status = t_class.Readdir("/")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("/nfs")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("nfs")
    print status["filenames"]
    print status["status"]
    status = t_class.Readdir("nfs/file2")
    print status["filenames"]
    print status["status"]

    status = t_class.Readdir("nfs/doooood")
    print status["filenames"]
    print status["status"]
