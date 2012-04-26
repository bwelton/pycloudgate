class ServiceObject(object):
    def __init__(self, filename=None):
        """ Setup's parameters for connection to service. Does other initialization

            Takes in a filename (string) returns nothing
        """
        pass

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
        return ret

    def Read (self, pathname, offset, size): 
        """ similar to fuse. returns data as a string 
        
            returns a dictionary with the following keys

                ret["status"] = True for completed, False for failed
                ret["data"] = data read from the file
        """
        ret = {}
        return ret

    def Write(self, pathname, data):
        """ Write data out to the file specified.

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret
       
    def Mknode (self, pathname): 
        """ Make a new file in the pathname specified. 

            pathname = string
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret

    def Unlink (self, pathname):
        """ Deletes a file from the service

            pathname = string

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret

    def GetPermissionFile (self):
        """ Gets the data inside of the permission file stored on the service
        
            returns a dictionary with the following keys:
                   
                ret["status"] = True for completed, False for failed
                ret["data"] = Permission file data (hash table: hash["pathname"] = permissions).
                              Permissions are as follows [UID,GID,MODE (777 - octet format)]
        """
        ret = {}
        return ret

    def WritePermissions (self, hashtable):
        """ Writes the permissions data to the permission file.

            hashtable - hash table of same format as GetPermissionsFile()

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret

    def Truncate(self, filename, pos):
        """ Truncates a file to the position specified 

            filename - string
            pos - integer showing what position to truncate the file too

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret

    def Mkdir (self, pathname):
        """ Makes the directory specified 

            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
        """
        ret = {}
        return ret

    def Readdir (self, path, offset):
        """ Return a directory listing for the given directory at offset
            
            returns a dictionary with the following keys:

                ret["status"] = True for completed, False for failed
                ret["filename"] =  filename for file at offset in directory
        """
        ret = {}
        return ret

    def GetAttr (self, path):
        """ Returns the attributes for the file (stat structure)

            returns a dictionary with the following keys:
                ret["status"] = True for completed, False for Failed
                ret["st_size"] = size (bytes) of the file
                ret["st_mtime"] = datetime class with last modification

        """
        ret = {}
        return ret

                
           
