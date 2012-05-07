import tempfile

class CacheClass(object):
    def __init__(self): 
        """ Initializes Cache Class """
        self._cacheMap = {}
        self._openCounts = {}
        self._dirty = {}

    def CheckOpen(self, filename):
        """ Check if a cache file exists for this filename """
        return filename in self._cacheMap

    def Size(self, filename): 
        f = self._cacheMap[filename]
        curpos = f.tell()
        f.seek(0,2) 
        total = f.tell()
        f.seek(curpos,0)
        return int(total)
    
    def isWritten(self, filename):
        return self._dirty[filename]

    def OpenCache(self, filename, buf):
        """ Opens a cache file the data buffer contained in buf written to it """
        if filename == None:
            print "Passed invalid filename to OpenCache"
            return False
        if filename in self._cacheMap:
            self._openCounts[filename] += 1        
        else:
            self._cacheMap[filename] =  tempfile.TemporaryFile()
            if self._cacheMap[filename] == None:
                print "Error creating tempfile for cache"
                return False
            self._openCounts[filename] = 1
            self._dirty[filename] = False

        #TODO: Need some policy to govern this
        self._cacheMap[filename].write(buf)
        return True

    def Write(self, filename, buf, offset):
        """ Write this buffer to the offset specified in a temporary file """

        if filename not in self._cacheMap:
            return False
        f = self._cacheMap[filename]
        f.seek(offset, 0)
        f.write(buf)
        self._dirty[filename] = True
        return True
          
    
    def Read(self, filename, offset, length):
        """ Read a cached file """
        if filename not in self._cacheMap:
            return None

        f = self._cacheMap[filename]
        f.seek(offset, 0)
        data = f.read(length)
        return data 

    def Truncate(self, filename, size):
        if filename not in self._cacheMap:
            return False
        self._cacheMap[filename].truncate(size)
        self._dirty[filename] = True
        return True

    def Close(self, filename):
        """ read the data from the tempfile, close the tempfile, return the data
            returns None if the data has not been changed or an error occurs """

        if filename not in self._cacheMap:
            return None
        
        ret_data = None
        
        f =  self._cacheMap[filename]
        if self._dirty[filename] == True:
            f.seek(0,0)
            ret_data = f.read()
        if self._openCounts[filename] == 1:
            f.close()
            del self._cacheMap[filename]
            del self._openCounts[filename]
            del self._dirty[filename]
        else:
            self._openCounts[filename] = self._openCounts[filename] - 1
        return ret_data
        
