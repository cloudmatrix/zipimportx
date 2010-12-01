#  Copyright (c) 2009-2010, Cloud Matrix Pty. Ltd.
#  All rights reserved; available under the terms of the BSD License.
"""

zipimportx:  faster zipfile imports for frozen python apps
==========================================================


This package aims to speed up imports from zipfiles for frozen python apps (and
other scenarios where the zipfile is assumed not to change) by taking several
shortcuts that aren't available to the standard zipimport module.

It exports a single useful name, "zipimporter", which is a drop-in replacement
for the standard zipimporter class. To replace the builtin zipimport mechanism
with zipimportx, do the following::

    import zipimportx
    zipimportx.zipimporter.install()

With no additional work you may already find a small speedup when importing 
from a zipfile.  Since zipimportx assumes that the zipfile will not change or
go missing, it does fewer stat() calls and integrity checks than the standard
zipimport implementation.


To further speed up the loading of a zipfile, you can pre-compute the zipimport
"directory information" dictionary and store it in a separate index file. This
will reduce the time spent parsing information out of the zipfile.  Create an
index file like this::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index()

This will create the file "mylib.zip.idx" containing the pre-parsed zipfile
directory information.  Specifically, it will contain a marshalled dictionary
object with the same structure as those in zipimport._zip_directory_cache.

In my tests, use of these indexes speeds up the initial loading of a zipfile by 
about a factor of 3 on Linux, and a factor of 5 on Windows.


To further speed up the loading of a collection of modules, you can "preload"
the actual module data by including it directly in the index.  This allows the
data for several modules to be loaded in a single sequential read rather than
requiring a separate read for each module.  Preload module data like this::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index(preload=["mymod*","mypkg*"])

Each entry in the "preload" list is a filename pattern.  Files from the zipfile
that match any of these patterns will be preloaded when the zipfile is first
accessed for import.  You may want to remove them from the actual zipfile in
order to save space.


Finally, it's possible to convert a zipfile into inline python code and include
that code directly in your frozen application.  This can simulate the effect
of having that zipfile on sys.path, while avoiding any fie IO during the import
process.  To get the necessary sourcecode, do the following::

    from zipimportx import zipimporter
    code = zipimporter("mylib.zip").get_inline_code()


Finally, it's worth re-iterating the big assumption made by this module: the
zipfile must never change or go missing.  If the data in the index does not
reflect the actual contents of the zipfile, imports will break in unspecified
and probably disasterous ways.

Note also that this package uses nothing but builtin modules.  To bootstrap
zipfile imports for a frozen application, you can inline this module's code
directly into your application's startup script.  Simply do something like
this in your build process::

    import zipimportx
    import inspect

    SCRIPT = '''
    %s
    zipimporter.install()
    import myapp
    myapp.main()
    ''' % (inspect.getsource(zipimportx),)

    freeze_this_script_somehow(SCRIPT)
    zipimportx.zipimporter("path/to/frozen/library.zip").write_index()

"""

__ver_major__ = 0
__ver_minor__ = 3
__ver_patch__ = 1
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__,__ver_minor__,__ver_patch__,__ver_sub__)
__version__ = "%d.%d.%d%s" % __ver_tuple__



import sys
import imp
import zlib
import marshal
import zipimport

if "time" in sys.builtin_module_names:
    import time
else:
    time = None

if "zlib" in sys.builtin_module_names:
    import zlib
else:
    zlib = None


archive_index = ".idx"
if sys.platform == "win32":
    SEP = "\\"
    BADSEP = "/"
else:
    SEP = "/"
    BADSEP = "\\"

ZipImportError = zipimport.ZipImportError
_zip_directory_cache = zipimport._zip_directory_cache
_zip_directory_preload = {}


class zipimporter(zipimport.zipimporter):
    """A zipimporter that can use pre-processed index files.

    This is a simple wrapper around the builtin "zipimport" functionality
    that can use pre-processed index files to speed up initial loading of
    the file.

    When you open a zipfile for import by doing this::

        loader = zipimportx.zipimporter("mylib.zip")

    It will first check for a file "mylib.zip.idx" that is assumed to contain
    the directory information for the zipfile, pre-processed in a form that
    python can load very quickly.  If such a file is found, the pre-processed
    directory information isused instead of parsing it out of the zipfile.
    """

    def __init__(self,archivepath):
        cached_files = None
        #  Check if we're given a path in an already-loaded zipfile, and
        #  avoid hitting the filesystem in that case.  The default zipimport
        #  implementation does this by stat()ing each potential parent file;
        #  we do it by looking in the directory cache.
        archive = archivepath; prefix = ""
        while archive:
            cached_files = _zip_directory_cache.get(archive)
            if cached_files is not None:
                archivepath = archive
                break
            parts = archive.rsplit(SEP,1)
            if len(parts) == 1:
                break
            archive = parts[0]
            prefix = parts[1] + SEP + prefix
        #  If archive directory isn't in the cache, we try to pre-populate it
        #  from an index file.  In the unlikely event that we're given a path
        #  pointing inside an uncached zipfile, the check will raise EnvError
        #  and fall back to the default zipimport machinery.
        if cached_files is None:
            prefix = ""
            try:
                with open(archivepath + archive_index,"rb") as f:
                    cached_files = marshal.load(f)
            except EnvironmentError:
                pass
            else:
                for path in cached_files.keys():
                    if SEP in path:
                        break
                    if BADSEP in path:
                        cached_files = None
                        break
                if cached_files is not None:
                    _zip_directory_cache[archivepath] = cached_files
        #  If the archive is in the cache, we bypass the default implementation
        #  since it wants to keep checking the filesystem for things we know
        #  (well, OK, *assume*) are still there.
        #  Unfortunately we can't set the "archive" and "prefix" attributes
        #  down inside the c-level zipimporter, so we have to re-implement a
        #  host of its functionality.
        if cached_files is None:
            zipimport.zipimporter.__init__(self,archivepath)
        else:
            self.__dict__["archive"] = archivepath
            self.__dict__["prefix"] = prefix
            self.__dict__["_files"] = cached_files

    @property
    def archive(self):
        try:
            return self.__dict__["archive"]
        except KeyError:
            return zipimport.zipimporter.archive.__get__(self)

    @property
    def prefix(self):
        try:
            return self.__dict__["prefix"]
        except KeyError:
            return zipimport.zipimporter.prefix.__get__(self)

    @property
    def _files(self):
        try:
            return self.__dict__["_files"]
        except KeyError:
            return zipimport.zipimporter._files.__get__(self)

    def __repr__(self):
        path = self.archive
        if self.prefix:
            path += SEP + self.prefix
        return "<zipimporterx object \"%s\">" % (path,)

    #  Suffixes to search for when importing modules, in order.
    #  Format is (suffix,is_package,is_bytecode)
    _zip_searchorder = [(SEP+"__init__.pyc",True,True),
                        (SEP+"__init__.pyo",True,True),
                        (SEP+"__init__.py",True,False),
                        (".pyc",False,True),
                        (".pyo",False,True),
                        (".py",False,False),]
    if not __debug__:
        _zip_searchorder[0:2] = reversed(_zip_searchorder[0:2])
        _zip_searchorder[3:5] = reversed(_zip_searchorder[3:5])

    #  Helper methods for basic manipulation of the contained files.

    MI_MODULE = 2
    MI_PACKAGE = 3

    def _get_module_type(self,fullname):
        """Helper method to get the type of a module.

        Given the full dotted name of a module, this method returns one of:

            * MI_MODULE:   the module is a normal module
            * MI_PACKAGE:  the module is a package
            * None:        the module was not found

        """
        pathhead = self.prefix + fullname.rsplit(".",1)[-1] 
        for suffix,ispkg,iscode in self._zip_searchorder:
            path = pathhead + suffix
            if path in self._files:
                if ispkg:
                    return self.MI_PACKAGE
                else:
                    return self.MI_MODULE
        return None

    def _get_module_code(self,fullname):
        """Helper method to get the code to execute for a module import.

        This method returns a tuple (code,filepath,ispkg) givig the code for
        the named module, the value for its __file__ attribute, and whether
        it is a normal module or a package.

        If the named module is not found, ZipImportError is raised.
        """
        pathhead = self.prefix + fullname.rsplit(".",1)[-1] 
        for suffix,ispkg,isbytecode in self._zip_searchorder:
            path = pathhead + suffix
            try:
                toc = self._files[path]
            except KeyError:
                pass
            else:
                #  Validate the bytecode, fall back to source if necessary
                if isbytecode:
                    data = self._get_data(path,toc)
                    srcpath = path[:-1] 
                    try:
                        srctoc = self._files[srcpath]
                    except KeyError:
                        srctoc = None
                    if len(data) < 9:
                        isbytecode,path,toc = False,srcpath,srctoc
                    elif data[:4] != imp.get_magic():
                        isbytecode,path,toc = False,srcpath,srctoc
                    else:
                        if not self._check_mtime(data[4:8],srctoc):
                            isbytecode,path,toc = False,srcpath,srctoc
                        else:
                            code = marshal.loads(data[8:])
                #  Compile the source down to bytecode if necessary
                filepath = self.archive + SEP + path
                if toc is None:
                    break
                if not isbytecode:
                    data = self._get_data(path,toc)
                    data = data.replace("\r\n","\n")
                    code = compile(data,filepath,"exec")
                return code,filepath,ispkg
        err = "can't find module '%s'" % (fullname,)
        raise zipimport.ZipImportError(err)

    def _check_mtime(self,mtbytes,srctoc):
        """Helper method to check the mtime of a bytecode file.

        Returns True if the bytecode file is newer than the source file, False
        otherwise.
        """
        #  If there's no time module, we can't do the check
        if time is None:
            return True
        #  If there's no source file, then it must be OK to use the bytecode
        if srctoc is None:
            return True
        #  Convert little-endian bytes to timestamp.
        mt = ord(mtbytes[0])
        mt += ord(mtbytes[1]) << 8
        mt += ord(mtbytes[2]) << 16
        mt += ord(mtbytes[3]) << 32
        #  Convert dos-format time and date to timestamp.
        #  These magic bytes are from zipimport.c.
        srctime = srctoc[5]
        srcdate = srctoc[6]
        st = time.struct_time((srcdate >> 9) & 0x7f, (srcdate >> 5) & 0x0f,
                              srcdate & 0x1f, (srctime >> 11) & 0x1f,
                              (srctime >> 5) & 0x3f,(srctime & 0x1f)*2)
        st = time.mktime(st)
        #  If they differ by more than a second, the bytecode isn't usable.
        diff = mt - st
        if diff < 0:
            diff = -1*diff
        return (diff <= 1)

    def _get_data(self,path,toc=None,raw=False):
        """Helper method to read the data for a given path.

        The path must be relative to the archive root, i.e. be exactly as
        found in the keys of self._files.  If there is no such file, None is
        returned.
        """
        #  Find the toc entry, unless it's already given to us.
        if toc is None:
            toc = self._files.get(path)
            if toc is None:
                return None
        filenm,compress,dsize,fsize,offset,mtime,mdate,crc = toc[:8]
        #  In-memory data may appear as an extra field on the toc tuple.
        #  If not, we have to read it from the zipfile.
        if len(toc) > 8:
            raw_data = toc[8]
        else:
            zf = open(self.archive,"rb")
            try:
                zf.seek(offset)
                # validate local file header
                if zf.read(4) != "PK\x03\x04":
                    err = "bad local file header in %s" % (self.archive,)
                    raise zipimport.ZipImportError(err)
                # skip TOC stuff that we already know
                zf.read(22)
                # read file name length and extras length, then skip over them
                namelen = ord(zf.read(1)) + (ord(zf.read(1)) << 8) 
                extralen = ord(zf.read(1)) + (ord(zf.read(1)) << 8) 
                zf.read(namelen+extralen)
                # now we can read the data
                raw_data = zf.read(dsize)
                if len(raw_data) != dsize:
                    err = "zipimport: can't read data"
                    raise zipimport.ZipImportError(err)
            finally:
                zf.close()
        #  Decompress if necessary, and return the data.
        if raw:
            return raw_data
        if compress:
            global zlib
            if zlib is None:
                import zlib
            return zlib.decompress(raw_data,-15)
        return raw_data

    def find_module(self,fullname,path=None):
        """find_module(fullname, path=None) -> self or None.

        Search for a module specified by 'fullname'. 'fullname' must be the
        fully qualified (dotted) module name. It returns the zipimporter
        instance itself if the module was found, or None if it wasn't.

        The optional 'path' argument is interpreted as required by the importer
        protocol (which means you can put one of these objects in sys.meta_path
        and it will behave appropriately).
        """
        if path is None:
            mi = self._get_module_type(fullname)
            if mi is not None:
                return self
        else:
            if isinstance(path,basestring):
                return None
            for p in path:
                if p == self.archive:
                    return self.find_module(fullname)
                if p.startswith(self.archive + SEP):
                    return self.__class__(p).find_module(fullname)
        return None

    def load_module(self,fullname):
        """load_module(fullname) -> module.
    
        Load the module specified by 'fullname'. 'fullname' must be the
        fully qualified (dotted) module name. It returns the imported
        module, or raises ZipImportError if it wasn't found.
        """
        modnm = fullname.rsplit(".")[-1]
        code,filepath,ispkg = self._get_module_code(fullname)
        created = False
        try:
            mod = sys.modules.get(fullname)
        except NameError:
            #  py2exe sometimes deletes sys from the __main__ namespace
            import sys
            mod = sys.modules.get(fullname)
        if mod is None:
            mod = imp.new_module(fullname)
            sys.modules[fullname] = mod
            created = True
        try:
            mod.__file__ = filepath
            mod.__loader__ = self
            if ispkg:
                mod.__path__ = [filepath.rsplit(SEP,1)[0]]
            exec code in mod.__dict__
        except Exception:
            if created:
                sys.modules.pop(fullname)
            raise
        return mod

    def get_data(self,pathname):
        """get_data(pathname) -> string with file data.
 
        Return the data associated with 'pathname'. Raise IOError if
        the file wasn't found.
        """
        if pathname.startswith(self.archive+SEP):
            pathname = pathname[len(self.archive)+1:]
        data = self._get_data(pathname)
        if data is None:
            raise IOError("not found: %s" % (pathname,))
        return data

    def get_code(self,fullname):
        """get_code(fullname) -> code object.
    
        Return the code object for the specified module. Raise ZipImportError
        if the module couldn't be found.
        """
        return self._get_module_code(fullname)[0]

    def get_source(self,fullname):
        """get_source(fullname) -> source string.
    
        Return the source code for the specified module. Raise ZipImportError
        if the module couldn't be found, return None if the archive contains
        the module but has no source for it.
        """
        mi = self._get_module_type(fullname)
        if mi is None:
            err = "can't find module '%s'" % (fullname,)
            raise zipimport.ZipImportError(err)
        srcpath = self.prefix + fullname.rsplit(".",1)[-1]
        if mi == self.MI_PACKAGE:
            srcpath += "/__init__.py"
        else:
            srcpath += ".py"
        return self._get_data(srcpath)

    def _get_filename(self,fullname):
        """_get_filename(fullname) -> filename string.
    
        Return the filename for the specified module.
        """
        #  Technically this could give an incorrect filename, e.g. if there's
        #  an invalid bytecode file with corresponding source then this will
        #  return the .pyc but the actual module will be given the .py.
        #  We put up with this to avoid reading from disk to get the filename.
        pathhead = self.prefix + fullname.rsplit(".",1)[-1] 
        for suffix,ispkg,iscode in self._zip_searchorder:
            path = pathhead + suffix
            if path in self._files:
                return self.archive + SEP + path
        raise ZipImportError("module not found: '%s'" % fullname,)
    get_filename = _get_filename

    def is_package(self,fullname):
        """is_package(fullname) -> bool.

        Return True if the module specified by fullname is a package.
        Raise ZipImportError is the module couldn't be found.
        """
        mi = self._get_module_type(fullname)
        if mi is None:
            err = "can't find module '%s'" % (fullname,)
            raise zipimport.ZipImportError(err)
        return (mi == self.MI_PACKAGE)

    def write_index(self,platform=None,preload=[]):
        """Create pre-processed index files for this zipimport archive.

        This method creates file <self.archive>.idx containing a pre-processed
        index of the zipfile contents found in the file <self.archive>.  This
        index can then be used to speed up loading of the zipfile.

        By default the index is formatted for the path conventions of the
        current platform; pass platform="win32" or platform="posix" to make
        an index for a specific platform.
        """
        index = _zip_directory_cache[self.archive].copy()
        #  Don't store the __file__ field, it won't be correct.
        #  Besides, we can re-create it as needed.
        for (key,info) in index.iteritems():
            index[key] = ("",) + info[1:]
        #  Correct for path separators on the requested platform.
        if platform is not None:
            if sys.platform == "win32" and platform != "win32":
                win32_index = index
                index = {}
                for (key,info) in win32_index.iteritems():
                    index[key.replace("\\","/")] = info
            elif sys.platform != "win32" and platform == "win32":
                posix_index = index
                index = {}
                for (key,info) in posix_index.iteritems():
                    index[key.replace("/","\\")] = info
        #  Add any preload data to the index
        if preload:
            import fnmatch  # not a builtin, import only as needed
            if isinstance(preload,basestring):
                preload = [preload]
            for (key,info) in index.iteritems():
                for pattern in preload:
                    if fnmatch.fnmatch(key,pattern):
                        data = self._get_data(key,info,raw=True)
                        index[key] = tuple(list(info) + [data])
                        break
        #  Write out to the appropriately-named index file.
        with open(self.archive + archive_index,"wb") as f:
            marshal.dump(index,f)

    def get_inline_code(self,platform=None,bootstrap_zipimportx=True):
        """Get python code for inline loading of the zipfile

        This method returns python sourcecode that, when executed, provides
        in-memory data equivalent to having the zipfile on sys.path.  It's
        similar to the builtin "frozen modules" functionality of the python
        interpreter, but implemented entirely in userspace code.

        If the keyword argument "bootstrap_zipimportx" is False, the returned
        code will not include the necessary definitions to bootstrap the 
        zipimportx module.
        """
        import os
        import inspect
        import zipimportx
        ilid = os.urandom(8).encode("hex")
        name = "<zipimportx-%s>" % (ilid,)
        index = _zip_directory_cache[self.archive].copy()
        #  The only field we need to keep is the "compressed" field
        #  Don't store the __file__ field, it won't be correct.
        #  Besides, we can re-create it as needed.
        for (key,info) in index.iteritems():
            compressed = info[1]
            index[key] = ("",compressed,None,None,None,None,None,None)
        #  Correct for path separators on the requested platform.
        if platform is not None:
            if sys.platform == "win32" and platform != "win32":
                win32_index = index
                index = {}
                for (key,info) in win32_index.iteritems():
                    index[key.replace("\\","/")] = info
            elif sys.platform != "win32" and platform == "win32":
                posix_index = index
                index = {}
                for (key,info) in posix_index.iteritems():
                    index[key.replace("/","\\")] = info
        #  Add the actual data for each file into the index
        for (key,info) in index.iteritems():
            data = self._get_data(key,None,raw=True)
            index[key] = tuple(list(info) + [data])
        #  Construct the necessary code:
        #      * get the zipimporter class
        #      * create sublcass to do path munging
        #      * insert the index into _zip_directory_cache
        #      * create a zipimporter instance and put it in the meta-path
        code = ["import sys\nimport zipimport"]
        code.append("if %r not in zipimport._zip_directory_cache:" % (name,))
        if bootstrap_zipimportx:
            code.append(inspect.getsource(zipimportx).replace("\n","\n  "))
        else:
            code.append("  from zipimportx import zipimporter, SEP")
        #  Unfortunately py2exe (at least) expects to be able to find dylib
        #  files relative to dirname(self.archive).  We pretend that the
        #  inlined archive is relative to sys.prefix.
        supnm = "zipimporter_base_" + ilid
        code.append("  %s = zipimporter" % (supnm,))
        code.append("  class zipimporter_%s(zipimporter):" % (ilid,))
        code.append("    def __init__(self,archivepath):")
        code.append("      idx = archivepath.find(%r)" % (name,))
        code.append("      if idx != -1:")
        code.append("        archivepath = archivepath[idx:]")
        code.append("      %s.__init__(self,archivepath)" % (supnm,))
        code.append("    @property")
        code.append("    def archive(self):")
        code.append("      archive = %s.archive.__get__(self)" % (supnm,))
        code.append("      try:")
        code.append("          return sys.prefix + SEP + archive")
        code.append("      except NameError:")
        code.append("          import sys")
        code.append("          return sys.prefix + SEP + archive")
        code.append("    def find_module(self,fullname,path=None):")
        code.append("      if path is not None:")
        code.append("        path = [self._fix_path(p) for p in path]")
        code.append("      return %s.find_module(self,fullname,path)"%(supnm,))
        code.append("    def get_data(self,pathname):")
        code.append("      pathname = self._fix_path(pathname)")
        code.append("      return %s.get_data(self,pathname)"%(supnm,))
        code.append("    def _fix_path(self,path):")
        code.append("      idx = path.find(%r)" % (name,))
        code.append("      if idx != -1:")
        code.append("        try:")
        code.append("          path = sys.prefix + SEP + path[idx:]")
        code.append("        except NameError:")
        code.append("          import sys")
        code.append("          path = sys.prefix + SEP + path[idx:]")
        code.append("      return path")
        code.append("  zipimport._zip_directory_cache[%r] = %s"%(name,index,))
        code.append("  sys.meta_path.append(zipimporter_%s(%r))"%(ilid,name,))
        return "\n".join(code)

    @classmethod
    def install(cls):
        """Install this class into the import machinery.

        This class method installs the custom zipimporter class into the import
        machinery of the running process, replacing any of its superclasses
        that may be there.
        """
        installed = False
        for i,imp in enumerate(sys.path_hooks):
            try:
                if issubclass(cls,imp):
                    sys.path_hooks[i] = cls
                    installed = True
            except TypeError:
                pass
        if not installed:
            sys.path_hooks.append(cls)
        sys.path_importer_cache.clear()


if __name__ == "__main__":
    if not sys.modules.get("zipimportx"):
        zipimporter.install()
        thismodule = sys.modules.get(__name__)
        if getattr(thismodule,"zipimporter",None) is not zipimporter:
            #  Uh-oh!  We're running as some sort of bizarre script and
            #  not as a module.  Create a fake one.
            thismodule = imp.new_module("zipimportx")
            thismodule.zipimporter = zipimporter
            thismodule.SEP = SEP
            thismodule.BADSEP = BADSEP
            thismodule._zip_directory_cache = _zip_directory_cache
            thismodule.ZipImportError = ZipImportError
        sys.modules["zipimportx"] = thismodule


