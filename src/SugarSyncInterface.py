from pysugarsync import SugarSync
import ConfigParser
import datetime
import time
import stat
class SugarSyncWrapper(object):
    def __init__(self, filename=None):
        """ Setup's parameters for connection to service. Does other initialization

            Takes in a filename (string) returns nothing
        """
        self._cache = {}   # Directory Referece Cacheing
        conf = ConfigParser.RawConfigParser()
        conf.read(filename)
        self._sync = SugarSync(conf=conf)
        self._tldChanged = True
        self._created = {}

        self._folders = {}
        self._GenCache()
        print self._cache

    def _GenCache (self):
        ## Generate the Cache
        tlds = self.GetTLD()
        for x in tlds.keys():
            if x == "status": 
                continue
            else:
                self._RecursiveCache(self._cache[x], "")

    def _RecursiveCache (self, folder, basepath):
        fpath = basepath + folder.GetName()
        basepath = basepath + folder.GetName() + "/"
        dirs = self._sync.GetFolders(folder)
        self._folders[fpath] = [ ]
        for x in dirs:
            self._cache[basepath + x.GetName()] = x
            self._folders[fpath].append(x)
            self._RecursiveCache(x, basepath)

        files = self._sync.ListFiles(folder)
        for x in files:
            self._folders[fpath].append(x)
            self._cache[basepath + x.GetName()] = x

        return

    def _PrepPath(self, path):
        if path[0] == "/":
            return path[1:]
        return path

    def GetTLD (self):
        """ Gets the top level directory/file information. 

            returns a hash table: 
                ret = { }
            where every directory/file has a key with the following
            output:
                ret["somedirname"] = self
                self =  this class
        """
        ret = {}
        tmp = self._sync.ListSyncFolders()
        for x in tmp:
            ret[x.GetName()] = self
            self._cache[x.GetName()] = x
        ret["status"] = True
        self._tldChanged = False
        return ret

    def _RecursiveLookup (self, prev, name, fullpath, path):
        local = None
        loc = fullpath.index(name)
        pathname = "/".join(fullpath[:loc]) + "/" + name

        if pathname not in self._cache:
            subpath = "/".join(fullpath[:loc])
            dirs = self._sync.GetFolders(prev)
            for x in dirs:
                self._cache[subpath + "/" + x.GetName()] = x

            files = self._sync.ListFiles(prev)
            for x in files:
                self._cache[subpath + "/" + x.GetName()] = x

            if pathname not in self._cache:
                return None

        local = self._cache[pathname]
        
        if len(path) == 0:
            return local
        if len(path) >= 2:
            return self._RecursiveLookup(local, path[0], fullpath, path[1:])        
        else:
            return self._RecursiveLookup(local, path[0], fullpath, [])

    def _LookupPathname (self, pathname):
        """ Performs pathname lookup to find SyncFile class
            
            Returns a syncfile class for the path specified (None if does not exist)
        """
        if pathname not in self._cache:
            return None
        else:
            return self._cache[pathname]

    def Read (self, pathname, offset, size): 
        """ similar to fuse. returns data as a string 
        
            returns a dictionary with the following keys

                ret["status"] = True for completed, False for failed
                ret["data"] = data read from the file
        """
        ret = {}
        pathname = self._PrepPath(pathname)

        if pathname in self._created:
            ret["status"] = True
            ret["data"] = ""
            return  ret

        fileID = self._LookupPathname(pathname)
        data = self._sync.GetFile(fileID)
        ret["status"] = True
        if offset + size < len(data[1]) and size != -1:
            ret["data"] = data[1][offset:offset+size]
        else:
            ret["data"] = data[1][offset:]
        print "READ DATA: " + str(len(ret["data"]))
        return ret

    def Write(self, pathname, data):
        """ Write data out to the file specified.

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        pathname = self._PrepPath(pathname)
        if pathname in self._created:
            del self._created[pathname]

        fileID = self._LookupPathname(pathname)
        ret["status"] = self._sync.WriteFile(fileID, data)
        return ret
       
    def Mknode (self, pathname): 
        """ Make a new file in the pathname specified. 

            pathname = string
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        pathname = self._PrepPath(pathname)
        folderpath = "/".join(pathname.split("/")[:-1])
        folderID = self._LookupPathname(folderpath)
        ret["status"] = self._sync.CreateFile(folderID, pathname.split("/")[-1])
        dirs = self._sync.ListFiles(folderID)
        for x in dirs:
            if pathname.split("/")[-1] == x.GetName():
                self._cache[pathname] = x
                break

        self._folders[folderpath].append(self._cache[pathname])

        print "SUGERSYNC STATUS - " + str(ret["status"])
        self._created[pathname] = "yes"
        return ret

    def Unlink (self, pathname):
        """ Deletes a file from the service

            pathname = string

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        pathname = self._PrepPath(pathname)
        fileID = self._LookupPathname(pathname)
        ret["status"] = self._sync.DeleteFile(fileID)
        if ret["status"] == True:
            if self._cache[pathname].GetType() == "SyncFile": 
                folderpath = "/".join(pathname.split("/")[:-1])
                self._folders[folderpath].remove(self._cache[pathname])
            else:
                del self._folders[pathname]
            del self._cache[pathname]
            
        return ret

    def GetPermissionFile (self):
        """ Gets the data inside of the permission file stored on the service
        
            returns a dictionary with the following keys:
                   
                ret["status"] = True for completed, False for failed
                ret["data"] = Permission file data (hash table: hash["pathname"] = permissions).
                              Permissions are as follows [UID,GID,MODE (777 - octet format)]
        """
        ret = {}
        permissionFile = "Magic Briefcase/pycloudgate/permissions.txt"
        if self._LookupPathname("Magic Briefcase/pycloudgate") == None:
            self.Mkdir("Magic Briefcase/pycloudgate")
            self._tldChanged = True
        if self._LookupPathname(permissionFile) == None:
            self.Mknode(permissionFile)
            self.Write(permissionFile, "novalue,000,000,10000\n")

        data = self.Read(permissionFile, 0, -1)
        tmpme = {}
        for x in data["data"].split("\n"):
            if "novalue,000,000,10000" == x or "" == x:
                continue
            tmp =  x.split(",")
            tmpme[tmp[0]] = [int(tmp[1],10), int(tmp[2],10), int(tmp[3],10)]

        ret["status"] = True
        ret["data"] = tmpme
        return ret

    def WritePermissions (self, hashtable):
        """ Writes the permissions data to the permission file.

            hashtable - hash table of same format as GetPermissionsFile()

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        permissionFile = "Magic Briefcase/pycloudgate/permissions.txt"
        data = ""
        for x in hashtable:
            data += x + "," + str(hashtable[x][0]) + "," + str(hashtable[x][1]) + "," + str(hashtable[x][2]) + "\n"
        ret = self.Write(permissionFile, data)
        return ret

    def Truncate(self, filename, pos):
        """ Truncates a file to the position specified 

            filename - string
            pos - integer showing what position to truncate the file too

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        filename = self._PrepPath(filename)
        data =  self.Read(filename, 0, pos)
        ret = self.Write(filename, data["data"])
        return ret

    def Mkdir (self, pathname):
        """ Makes the directory specified 

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        pathname = self._PrepPath(pathname)
        path =  pathname.split("/")
        dir = self._LookupPathname("/".join(path[:-1]))
        ret["status"] = self._sync.CreateFolder(dir, path[-1])
        self._folders[pathname] = [] 
        return ret

    def Readdir (self, path):
        """ Return a directory listing for the given directory at offset
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
                ret["list"] = Directory list
        """
        ret = {}
        path = self._PrepPath(path)
        
        dir = self._LookupPathname(path)

        pathlist = self._folders[path] 
        ret["filenames"] = []
        for x in pathlist:
            ret["filenames"].append(x.GetName())
        ret["status"] = True

        return ret

    def GetAttr (self, path):
        """ Returns the attributes for the file (stat structure)

            returns a dictionary with the following keys:
                ret["status"] = True for completed, False for Failed
                ret["st_size"] = size (bytes) of the file
                ret["st_mtime"] = datetime class with last modification

        """
        ret = {}
        path = self._PrepPath(path)
        if path in self._cache:
            
            ret["status"] = True
            if self._cache[path].GetType() == "SyncFile":
                if int(self._cache[path].GetSize()) < 0:
                    ret["st_size"] = 0
                else: 
                    ret["st_size"] = int(self._cache[path].GetSize())
                ret["st_mtime"] = int(time.mktime(self._cache[path].GetModified().timetuple()))
                ret["st_mode"] = stat.S_IFREG
            else:
                ret["st_size"] = 0
                ret["st_mtime"] = int(time.mktime(datetime.datetime.now().timetuple()))
                ret["st_mode"]  = stat.S_IFDIR
        else:
            file =  self._LookupPathname(path)
            if file != None:
                ret["status"] = True
            else:
                ret["status"] = False
                return ret

            if self._cache[path].GetType() == "SyncFile":
                if int(self._cache[path].GetSize()) < 0:
                    ret["st_size"] = 0
                else: 
                    ret["st_size"] = int(self._cache[path].GetSize())

                ret["st_mtime"] = int(time.mktime(self._cache[path].GetModified().timetuple()))
                ret["st_mode"] = stat.S_IFREG
            else:
                ret["st_size"] = 0
                ret["st_mtime"] = int(time.mktime(datetime.datetime.now().timetuple()))
                ret["st_mode"] = stat.S_IFDIR
        return ret

## Minor Testing            
if __name__ == "__main__":
    # init
    t_class = SugarSyncWrapper("conf.ini")

    # Test GetTLD()
    tlds = t_class.GetTLD()
    for x in tlds:
        print x
        

    # Test Mknode
    filedir = "Mobile Photos/testfile.png"
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

    ## Test Truncate
    filedir = "Mobile Photos/testfile.png"
    status = t_class.Mknode(filedir)
    data = "HELLO WORLD!!!!!!"
    status = t_class.Write(filedir, data)
    status = t_class.Truncate(filedir, 5)
    if status["status"] ==  True:
        d = t_class.Read(filedir, 0, -1)
        if d["data"] == "HELLO":
            print "Truncate works correctly"
        else:
            print "NOT VALID DATA FOR TRUNCATE GOT " + str(d["data"])
    else:
        print "Truncate not successful"

    status =  t_class.Unlink(filedir)

    status = t_class.Readdir("Mobile Photos")
    for x in status["list"]:
        print x

    status = t_class.GetAttr("Mobile Photos")
    if status["status"] == True:
        print status["st_size"]
        print status["st_mtime"]
    else:
        print "GETTING ATTR FAILED"
    status = t_class.GetAttr("Magic Briefcase/pycloudgate/permissions.txt")
    if status["status"] == True:
        print status["st_size"]
        print status["st_mtime"]
    else:
        print "GETTING ATTR FAILED"

