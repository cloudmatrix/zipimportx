

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

