import tempfile

class CacheClass(object):
    def __init__(self): 
        """ Initializes Cache Class """
        self._cacheMap = {}

    def OpenCache(self, filename, buf):
        """ Opens a cache file the data buffer contained in buf written to it """
        self._cacheMap[filename] =  tempfile.TemporaryFile()
        pass

    def Write(self, filename, buf, offset):
        """ Write this buffer to the offset specified in a temporary file """
        pass

    def Close(self, filename):
        """ read the data from the tempfile, close the tempfile, return the data"""

        pass




        

        


