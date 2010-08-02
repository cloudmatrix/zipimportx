#  Copyright (c) 2009-2010, Cloud Matrix Pty. Ltd.
#  All rights reserved; available under the terms of the BSD License.
"""

zipimportx:  faster zip imports using pre-processed index files
===============================================================


This package aims to speed up imports from zipfiles, by pre-computing the
"directory information" dictionary and storing it in a separate index file.
This reduces the time spent parsing information out of the zipfile.

It exports a single useful name, zipimporter, which is a drop-in replacement
for the standard zipimporter class.

To create an index for a given zipfile, do the following::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index()

Depending on your platform, this will create either "mylib.zip.win32.idx" or 
"mylib.zip.posix.idx" containing the pre-parsed zipfile directory information.
(Specifically, it will contain a marshalled dictionary similar to those found
in zipimport._zip_directory_cache.)

To enable use of these index files, simply replace the builtin zipimport
mechanism with zipimportx by doing the following::

    import zipimportx
    zipimportx.zipimporter.install()

In my tests, use of these indexes speeds up the initial loading of a zipfile by 
about a factor of 3 on Linux, and a factor of 5 on Windows.

Note that this package uses nothing but builtin modules.  To bootstrap zipfile
imports for a frozen application, you can inline the module's code directly
into your application's startup script.  Do this somewhere in your build::

    import zipimportx
    import inspect

    SCRIPT = '''
    %s
    zipimporter.install()
    import myapp
    myapp.main()
    ''' % (inspect.getsource(zipimportx),)

    freeze_this_script_somehow(SCRIPT)
    zipimportx.zipimporter("path/to/frozen/library.zip").write_indexes()

Note also that imports will almost certainly *break* if the index does not
reflect the actual contents of the zipfile.  This module is therefore most
useful for frozen apps and other situations where the zipfile is not expected
to change.

"""

__ver_major__ = 0
__ver_minor__ = 2
__ver_patch__ = 0
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__,__ver_minor__,__ver_patch__,__ver_sub__)
__version__ = "%d.%d.%d%s" % __ver_tuple__


import sys
import marshal
import zipimport


if sys.platform == "win32":
    SEP = "\\"
    archive_index = ".win32.idx"
else:
    SEP = "/"
    archive_index = ".posix.idx"


class zipimporter(zipimport.zipimporter):
    """A zipimporter that can use pre-processed index files.

    This is a simple wrapper around the builtin "zipimport" functionality
    that can use pre-processed index files to speed up initial loading of
    the file.

    When you open a zipfile for import by doing this::

        loader = zipimportx.zipimporter("mylib.zip")

    It will first check for a file "mylib.zip.win32.idx" (or ".posix.idx" on
    posix platforms) that is assumed to contain the directory information for
    the zipfile, pre-precessed in a form that python can load very quickly.
    It such a file is found, the pre-processed directory information is used
    instead of parsing it out of the zipfile.
    """

    def __init__(self,archivepath):
        if archivepath not in zipimport._zip_directory_cache:
            #  Pre-populate the zip directory cache using the index file.
            #  Note that this will raise EnvironmentError if we're given
            #  a path inside the zipfile.  Since that's usually only done if
            #  the zipfile has already been parsed, we don't bother trying
            #  to detect that case.
            try:
                with open(archivepath + archive_index,"rb") as f:
                    index = marshal.load(f)
                zipimport._zip_directory_cache[archivepath] = index
            except EnvironmentError:
                pass
        zipimport.zipimporter.__init__(self,archivepath)

    def load_module(self,fullname):
        """load_module(fullname) -> module.
    
        Load the module specified by 'fullname'. 'fullname' must be the
        fully qualified (dotted) module name. It returns the imported
        module, or raises ZipImportError if it wasn't found.
        """
        self._fix_filename(fullname)
        return zipimport.zipimporter.load_module(self,fullname)

    def get_code(self,fullname):
        """get_code(fullname) -> code object.
    
        Return the code object for the specified module. Raise ZipImportError
        if the module couldn't be found.
        """
        self._fix_filename(fullname)
        return zipimport.zipimporter.get_code(self,fullname)

    def _get_filename(self,fullname):
        """_get_filename(fullname) -> filename string.
    
        Return the filename for the specified module.
        """
        self._fix_filename(fullname)
        return zipimport.zipimporter._get_filename(self,fullname)

    def _fix_filename(self,fullname):
        """Fix the __file__ entry in the TOC for the given module.

        Since the pre-processed index doesn't store filename information,
        this must be added back into the TOC when it's needed.  Fortunately
        it's trivial to calculate.
        """
        modpath = self.prefix
        if modpath and not modpath.endswith(SEP):
            modpath += SEP
        modpath += fullname.replace(".",SEP)
        for suffix in (".py",".pyc",".pyo"):
            for extra in ("",SEP+"__init__"):
                path = modpath + extra + suffix
                try:
                    info = self._files[path]
                    if info[0] != "":
                        return  # already fixed
                    info = (self.archive + SEP + path,) + info[1:]
                    self._files[path] = info
                except KeyError:
                    pass

    def write_index(self,platform=None):
        """Create pre-processed index files for this zipimport archive.

        This method creates files <archive>.posix.idx and <archive>.win32.idx
        containing a pre-processes index of the zipfile contents found in the
        file <archive>.  This index can then be used to speed up loading of
        the zipfile.

        By default the index is formatted for the path conventions of the
        current platform; pass platform="win32" or platform="posix" to make
        an index for a specific platform.
        """
        index = zipimport._zip_directory_cache[self.archive].copy()
        #  Don't store the __file__ field, it won't be correct.
        #  Besides, we can re-create it as needed.
        for (key,info) in index.iteritems():
            index[key] = ("",) + info[1:]
        #  Correct for path separators on the requested platform.
        fileext = archive_index
        if platform is not None:
            if sys.platform == "win32" and platform != "win32":
                fileext = ".posix.idx"
                win32_index = index
                index = {}
                for (key,info) in win32_index.iteritems():
                    index[key.replace("\\","/")] = info
            elif sys.platform != "win32" and platform == "win32":
                fileext = ".win32.idx"
                posix_index = index
                index = {}
                for (key,info) in posix_index.iteritems():
                    index[key.replace("/","\\")] = info
        #  Write out to the appropriately-named index file.
        with open(self.archive+fileext,"wb") as f:
            marshal.dump(index,f)

    @classmethod
    def install(cls):
        """Install this class into the import machinery.

        This class method installs the custom zipimporter class into the import
        machinery of the running process, relacing any of its superclasses
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


