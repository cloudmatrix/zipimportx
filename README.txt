

zipimportx:  faster zip imports using pre-processed index files
===============================================================


This package aims to speed up imports from zipfiles by reducing the overhead
of finding and parsing the zipfile contents.  It exports a single useful name,
zipimporter, which is a drop-in replacement for the standard zipimporter class.

To replace the builtin zipimport mechanism with zipimportx, do the following:

    import zipimportx
    zipimportx.zipimporter.install()

With no additional work you may already find a small speedup when importing 
from a zipfile, since zipimportx does fewer stat() calls than the standard
zipimport implementation.


To further speed up the loading of a zipfile, you can pre-compute the 
"directory information" dictionary and store it in a separate index file.
This will reduce the time spent parsing information out of the zipfile.

To create an index for a given zipfile, do the following::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index()

This will create the file "mylib.zip.idx" containing the pre-parsed zipfile
directory information (specifically, it will contain a marshalled dictionary
similar to those found in zipimport._zip_directory_cache).

In my tests, use of these indexes speeds up the initial loading of a zipfile by 
about a factor of 3 on Linux, and a factor of 5 on Windows.


To further speed up the loading of a collection of modules, you can "preload"
the actual module data by including it in the index.  This allows the data for
several modules to be loaded in a single sequential read rather than requiring
a separate read for each module.  Preload module data like this::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index(preload=["mymod*","mypkg*"])


Note that imports will almost certainly *break* if the index does not reflect
the actual contents of the zipfile.  This module is therefore most useful
for frozen apps and other situations where the zipfile is not expected to
change.


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

