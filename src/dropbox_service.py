import os,stat,errno
from function_template import ServiceObject
import dropbox_connect 
from dropbox import client, rest, session

class DropboxService(ServiceObject):
    def __init__(self, filename="dropbox_token_store.txt"):
        self.service = dropbox_connect.DropboxLowLevel(filename)
        
    
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
        for direntry in self.service.readdir('/',0):
            if not direntry == "." and not direntry == "..":
                ret[direntry] = self
        return ret

    def Read (self, pathname, offset, size): 
        """ similar to fuse. returns data as a string 
        
            returns a dictionary with the following keys

                ret["status"] = True for completed, False for failed
                ret["data"] = data read from the file
        """
        ret = {}    
    
        retValue = self.service.read(pathname, size, offset) 
	if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True
            ret["data"] = retValue
       
        return ret

    def Write(self, pathname, data):
        """ Write data out to the file specified.

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}

        retValue = self.service.write(pathname, data, 0) 
	if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True

        return ret
       
    def Mknode (self, pathname): 
        """ Make a new file in the pathname specified. 

            pathname = string
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        retValue = self.service.mknod(pathname, 0, 0)
        if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True
        
        return ret

    def Unlink (self, pathname):
        """ Deletes a file from the service

            pathname = string

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        retValue = self.service.unlink(pathname)
        if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True
        return ret

    def GetPermissionFile (self):
        """ Gets the data inside of the permission file stored on the service
        
            returns a dictionary with the following keys:
                   
                ret["status"] = True for completed, False for failed
                ret["data"] = Permission file data (hash table: hash["pathname"] = permissions).
                              Permissions are as follows [UID,GID,MODE (777 - octet format)]
        """
        ret = {}
        table = {}
        permit = self.service.read('/.permission', 1024 * 1024, 0)
        if permit == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True
            for entry in permit.split("\n"):
                filename,uid,gid,mode=entry.split()
                table[filename] = [int(uid), int(gid), int(mode)]
            ret["data"] = table
        return ret

    def WritePermissions (self, hashtable):
        """ Writes the permissions data to the permission file.

            hashtable - hash table of same format as GetPermissionsFile()

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}

        f = ""
        for filename in hashtable.keys():
            f = f + filename + " " + str(hashtable[filename][0]) + " " + str(hashtable[filename][1]) + " " + str(hashtable[filename][2])

        retValue = self.service.write("/.permission", f, 0)
        if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True
        return ret

    def Truncate(self, filename, pos):
        """ Truncates a file to the position specified 

            filename - string
            pos - integer showing what position to truncate the file too

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}

        retValue = self.service.ftruncate(filename, pos)        
        if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True

        return ret

    def Mkdir (self, pathname):
        """ Makes the directory specified 

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        retValue = self.service.mkdir(pathname, 0)        
        if retValue == -errno.EACCES:
            ret["status"] = False
        else:
            ret["status"] = True

        return ret

    def Readdir (self, path, offset):
        """ Return a directory listing for the given directory at offset
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
                ret["filename"] =  filename for file at offset in directory
        """
        ret = {}
        retValue = self.service.readdir(path, 0)
        if len(retValue) < offset + 1:
            ret["status"] = False
        else:
            ret["status"] = True
            ret["filename"] = retValue[offset]

        return ret

    def GetAttr (self, path):
        """ Returns the attributes for the file (stat structure)

            returns a dictionary with the following keys:
                ret["status"] = True for completed, False for Failed
                ret["st_size"] = size (bytes) of the file
                ret["st_mtime"] = datetime class with last modification

        """
        ret = {}

        retValue = self.service.getattr(path)

        if retValue == -errno.ENOENT:
            ret["status"] = False
        else:
            ret["status"] = True
            ret["st_size"] = retValue.st_size
            ret["st_mtime"] = retValue.st_mtime
            ret["st_mode"] = retValue.st_mode

        return ret

                
## Minor Testing            
if __name__ == "__main__":
    # init
    t_class = DropboxService()

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

    ret = t_class.Read(filedir, 0, 1024)
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
    print permfile
    if permfile["status"] == True:
        if permfile["data"]["testperm"] == [int("1000",10), int("2000",10), int("777",10)]:
            print "Permission retrieved Correctly"
        else:
            print "Permission did not save correctly"
    else:
        print "Could not open permission file"
          
