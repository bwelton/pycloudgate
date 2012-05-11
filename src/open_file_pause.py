#!/usr/bin/python

import sys
import time

if len(sys.argv) < 1:
    print "Usage: python %prog <file1> <file2> ...."
    exit(0)

open_t1 = time.time()
cntr = 0
fh_list = []
for file_name in sys.argv[1:]:
    #print "opening " + str(file_name)
    fh_list.append(open(file_name,"rw"))
    cntr += 1
open_t2 = time.time()
print open_t1, open_t2
print "Time to open " + str(cntr) + " files: " + str((open_t2-open_t1)) + " s"
print "Time to open " + str(cntr) + " files: " + str((open_t2-open_t1)*1000.0) + " ms"

fav_num = input("When you want to close the files, enter your favorite number: ")

print "Your favorite number is " + str(fav_num)

for fh in fh_list:
    fh.close()
