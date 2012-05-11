#!/usr/bin/python

import sys
import time

if len(sys.argv) != 2:
    print "Usage: python open_file_readbyte.py <file1> "
    exit(0)

file_name = sys.argv[1]
open_t1 = time.time()
cntr = 1
fh = open(file_name,"r")
byte = fh.read(1)
open_t2 = time.time()

print "read " + str(byte)

print "Time to open and read one byte " + str(cntr) + " files: " + str((open_t2-open_t1)) + " s"
print "Time to open and read one byte " + str(cntr) + " files: " + str((open_t2-open_t1)*1000.0) + " ms"

fh.close()
