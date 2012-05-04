import tempfile

class CacheClass(object):
    def __init__(self): 
        """ Initializes Cache Class """
        self._cacheMap = {}
        self._openCounts = {}

    def CheckOpen(self, filename):
        """ Check if a cache file exists for this filename """
        return filename in self._cacheMap

    def OpenCache(self, filename, buf):
        """ Opens a cache file the data buffer contained in buf written to it """
        if filename in self._cacheMap:
            self._openCounts[filename] += 1        
        self._cacheMap[filename] =  tempfile.TemporaryFile()
        self._cacheMap[filename].write(buf)
        self._openCounts[filename] = 1

    def Write(self, filename, buf, offset):
        """ Write this buffer to the offset specified in a temporary file """

        if filename not in self._cacheMap:
            return False

        f = self._cacheMap[filename]
        
        f.seek(offset, 0)
        f.write(buf)
        return True
          
    
    def Read(self, filename, offset, length):
        """ Read a cached file """
        if filename not in self._cacheMap:
            return None

        f = self._cacheMap[filename]
        f.seek(offset, 0)
        data = f.read(length)
        return data 


    def Close(self, filename):
        """ read the data from the tempfile, close the tempfile, return the data"""

        if filename not in self._cacheMap:
            return None
        
        f =  self._cacheMap[filename]
        f.seek(0,0)
        data = f.read()
        if self._openCounts[filename] == 1:
            f.close()
            del self._cacheMap[filename]
            del self._openCounts[filename]
        else:
            self._openCounts[filename] = self._openCounts[filename] - 1
        return data
        
