

zipimportx:  faster zip imports using pre-processed index files
===============================================================


This package aims to speed up imports from zipfiles, by pre-computing the
"directory information" dictionary and storing in a separate index file.
This reduces the time spent parsing information out of the zipfile.

It exports a single useful name, zipimporter, which is a drop-in replacement
for the standard zipimporter class.

To create an index for a given zipfile, do the following::

    from zipimportx import zipimporter
    zipimporter("mylib.zip").write_index()

This will create two files, "mylib.zip.win32.idx" and "mylib.zip.posix.idx",
containing the zipfile directory information pre-parsed and formatted to 
different path-naming conventions.  (Specifically, they contain a marshalled
dictionary similar to those found in zipimport._zip_directory_cache.)

To enable use of these index files, simply replace the builtin zipimport
mechanism with zipimportx by doing the following::

    import zipimportx
    zipimportx.zipimporter.install()

In my tests, use of these indexes speeds up the loading of a zipfile by about
a factor of 3 on Linux, and a factor of 5 on Windows.

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

