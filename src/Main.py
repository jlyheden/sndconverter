#!/usr/bin/python
'''

    sndconverter - Python wrapper for converting folders of sound files to another format (hardcoded to MP3)
    Copyright (C) 2010  Johan Lyheden

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''
import os
import re
import sys
import time
import Queue
import threading

from subprocess import *

OSPath = { "Darwin": "/opt/local/bin", "Linux": "/usr/bin" }
VERBOSE=False

"""
    Exceptions
"""
class NoSuchCodecException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class NoSoundFilesFoundException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class NoSupportedOSException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

"""
    Classes (one for each codec)
"""
class OGG(object):
    _decode_opts = "-b 16 -o -"
    _encode_opts = ""
    _executable_decoder = "oggdec"
    _executable_analyzer = "ogginfo"
    def __init__(self):
        if os.uname()[0] in OSPath:
            self._executable_path = OSPath[os.uname()[0]]
        else:
            raise NoSupportedOSException, "Your OS is not supported"
        if not os.path.isfile(os.path.join(self._executable_path,self._executable_decoder)):
            raise NoSuchCodecException, "You don't have OGG support installed, please install vorbis-tools"
    def __analyze(self, file):
        tmpdict = {}
        fd = Popen([os.path.join(self._executable_path,self._executable_analyzer), file],stdin=PIPE,stdout=PIPE,stderr=PIPE)
        pattern = re.compile("^\s+\w+=")
        for row in fd.communicate(input=None)[0].splitlines():
            if pattern.search(row):
                record = re.sub("^\s+","",row)
                (key,value) = re.split("=",record)
                tmpdict[key.lower()] = value
        return tmpdict
    def encode(self, file, id3dict):
        pass
    def decode(self, file):
        retdict = self.__analyze(file)
        retdict["executable"] = os.path.join(self._executable_path,self._executable_decoder) + " " + self._decode_opts + " \"" + file + "\""
        return retdict
    def isfile(self, file):
        pass
    
class FLAC(object):
    _decode_opts = "-dc"
    _encode_opts = ""
    _executable_decoder = "flac"
    _executable_analyzer = "metaflac"
    def __init__(self):
        if os.uname()[0] in OSPath:
            self._executable_path = OSPath[os.uname()[0]]
        else:
            raise NoSupportedOSException, "Your OS is not supported"
        if not os.path.isfile(os.path.join(self._executable_path,self._executable_decoder)):
            raise NoSuchCodecException, "You don't have FLAC support installed"
    def __analyze(self, file):
        tmpdict = {}
        fd = Popen([os.path.join(self._executable_path, self._executable_analyzer),"--list","--block-type=VORBIS_COMMENT",file],stdin=PIPE,stdout=PIPE,stderr=PIPE)
        pattern = re.compile(r"^\s+comment\[\d+\]:")
        for row in fd.communicate(input=None)[0].splitlines():
            if pattern.search(row):
                record = re.sub("^\s+comment\[\d+\]:\s","",row)
                (key,value) = re.split("=",record)
                tmpdict[key.lower()] = value
        return tmpdict
    def encode(self, file, id3dict):
        pass
    def decode(self, file):
        retdict = self.__analyze(file)
        retdict["executable"] = os.path.join(self._executable_path,self._executable_decoder) + " " + self._decode_opts + " \"" + file + "\""
        return retdict
    def isfile(self, file):
        pass
    
class MP3(object):
    _decode_opts = ""
    _encode_opts = " -h -V 0 "
    _executable_encoder = "lame"
    _executable_analyzer = "mp3info"
    def __init__(self):
        if os.uname()[0] in OSPath:
            self._executable_path = OSPath[os.uname()[0]]
        else:
            raise NoSupportedOSException, "Your OS is not supported"
        if not os.path.isfile(os.path.join(self._executable_path,self._executable_encoder)):
            raise NoSuchCodecException, "You don't have mp3 support installed, please install Lame"
    def encode(self, file, id3dict):
        newfilename = re.sub(r"(?i)\.(wav|flac|ogg)$",".mp3", file)
        return os.path.join(self._executable_path,self._executable_encoder) + self._encode_opts + " ".join(self.__returnid3list(id3dict)) + " - " + "\"" + newfilename + "\""
    def decode(self, file):
        pass
    def __returnid3list(self,id3dict):
        id3list = []
        if "artist" in id3dict:
            id3list.append("--ta \"" + id3dict["artist"] + "\"")
        if "album" in id3dict:
            id3list.append("--tl \"" + id3dict["album"] + "\"")
        if "year" in id3dict:
            id3list.append("--ty \"" + str(id3dict["year"]) + "\"")
        elif "date" in id3dict:
            id3list.append("--ty \"" + str(id3dict["date"]) + "\"")
        if "track" in id3dict:
            id3list.append("--tn \"" + str(id3dict["track"]) + "\"")
        elif "tracknumber" in id3dict:
            id3list.append("--tn \"" + str(id3dict["tracknumber"]) + "\"")
        if "title" in id3dict:
            id3list.append("--tt \"" + id3dict["title"] + "\"")
        #if "genre" in id3dict:
        #    id3list.append("--tg \"" + id3dict["genre"] + "\"")
        return id3list
    def __analyze(self, file):
        pass
    def isfile(self, file):
        return os.path.isfile(re.sub(r"(?i)\.(flac|ogg)$",".mp3", file))

"""
    Threading
"""

class SoundConvert(threading.Thread):
    def __init__(self,i,n,q):
        threading.Thread.__init__(self)
        self.name = n
        self.id = i
        self.queue = q
    def run(self):
        file = ""
        if VERBOSE is True: 
            print "Thread %s started" % (self.name)
        while not self.queue.empty():
            try:
                file = self.queue.get()
            except:
                print "%s: Couldn't get item from queue" % (self.name)
            else:
                s = self.__returnsourceobject(file)
                s_srcdict = s.decode(file)
                d = MP3() # Should be dynamic
                if s.__class__.__name__ == d.__class__.__name__:
                    print "%s: Source and destination is same, won't perform pointless conversion." % (self.name)
                else:
                    if not d.isfile(file):
                        if VERBOSE is True:
                            print "%s: Starting conversion of %s" % (self.name,file)
                        convertprocess = Popen([s_srcdict["executable"] + " | " + d.encode(file, s_srcdict)],shell=True,stdin=PIPE,stdout=PIPE,stderr=PIPE)
                        convertprocess.communicate(input=None)
                        convertprocess.wait()
                        if convertprocess.returncode == 0:
                            print "%s: File %s successfully converted to filetype %s " % (self.name,file,d.__class__.__name__)
                        else:
                            print "%s: File conversion failed" % (self.name)
                    else:
                        print "%s: Destination file already exists, skipping" % (self.name)
            self.queue.task_done()
            time.sleep(1)
        if VERBOSE is True:
            print "Thread %s stopped" % (self.name)
    def __returnsourceobject(self, file):
        if file.lower().endswith(".mp3"):
            return MP3()
        elif file.lower().endswith(".flac"):
            return FLAC()
        elif file.lower().endswith(".ogg"):
            return OGG()
                
if __name__ == '__main__':
    try:
        sys.argv[1]
    except:
        print "Usage: %s <directory to convert>" % (sys.argv[0])
    else:
        try:
            starttime = time.time()
            poolsize = 2
            clientpool = Queue.Queue(0) #infinite
            sourcedir = sys.argv[1]
            pattern = re.compile(r"(?i)\.(mp3|flac|ogg)$")
            for f in os.listdir(sourcedir):
                if pattern.search(f.lower()):
                    clientpool.put(os.path.join(sourcedir,f))
                    if VERBOSE is True:
                        print "Adding %s to queue" % os.path.join(sourcedir,f)
            for x in xrange ( poolsize ):
                SoundConvert(x, "converter-thread-%s" % (x), clientpool).start()
            clientpool.join()
            print "Total time: %s seconds" % (time.time() - starttime)
        except OSError, ex:
            print "File not found error: %s" % (ex)
        except:
            print "Unhandled error."
