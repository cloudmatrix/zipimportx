
import os
import sys
import unittest
import timeit
import zipimport
import zipfile

import zipimportx

#  I don't actually use these, I just add them to a zipfile.
#  They're here so I can grab __file__ off them.
import distutils
import logging
import email
import sqlite3
import ctypes

LIBHOME = os.path.dirname(unittest.__file__)


class TestZipImportX(unittest.TestCase):

    def setUp(self):
        #  Create small zipfile with just a few libraries
        lib = "libsmall.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if os.path.exists(lib):
            os.unlink(lib)
        zf = zipfile.PyZipFile(lib,"w",compression=zipfile.ZIP_DEFLATED)
        zf.writepy(os.path.dirname(zipimportx.__file__))
        zf.writepy(os.path.dirname(distutils.__file__))
        zf.writepy(os.path.dirname(logging.__file__))
        zf.writepy(os.path.dirname(email.__file__))
        zf.writepy(os.path.dirname(sqlite3.__file__))
        zf.writepy(os.path.dirname(ctypes.__file__))
        zf.close()
        #  Create medium zipfile with everything in top-level stdlib
        lib = "libmedium.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if os.path.exists(lib):
            os.unlink(lib)
        zf = zipfile.PyZipFile(lib,"w")
        zf.writepy(os.path.dirname(zipimportx.__file__))
        zf.writepy(LIBHOME)
        zf.close()
        #  Create large zipfile with everything we can find
        lib = "liblarge.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if os.path.exists(lib):
            os.unlink(lib)
        zf = zipfile.PyZipFile(lib,"w")
        zf.writepy(os.path.dirname(zipimportx.__file__))
        zf.writepy(LIBHOME)
        for (dirnm,subdirs,files) in os.walk(LIBHOME):
            if os.path.basename(dirnm) in ("lib-python","test",):
                del subdirs[:]
                continue
            if "__init__.pyc" in files:
                del subdirs[:]
                try:
                    zf.writepy(dirnm)
                except (EnvironmentError,SyntaxError,):
                    pass
        zf.close()

    def test_performance_increase(self):
        ratios = {
            "libsmall.zip": 2.4,
            "libmedium.zip": 3,
            "liblarge.zip": 3.5,
        }
        for libnm in ratios:
            lib = os.path.abspath(os.path.join(os.path.dirname(__file__),libnm))
            (zt,xt) = self._do_timeit_init(lib)
            print libnm, zt, xt, zt/xt
            self.assertTrue(zt/xt > ratios[libnm])
        for libnm in ratios:
            lib = os.path.abspath(os.path.join(os.path.dirname(__file__),libnm))
            (zt,xt) = self._do_timeit_load(lib)
            print libnm, zt, xt, zt/xt
            #  A 50% decrease in loading performance?  Yes, but you have
            #  to remember that the load time is a *very* small number.
            #  The absolute difference is measured in microseconds.
            self.assertTrue(zt/xt > 0.50)

    def test_space_overhead(self):
        for lib in ("libsmall.zip","libmedium.zip","liblarge.zip"):
            lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
            zipimportx.zipimporter(lib).write_index()
            z_size = os.stat(lib).st_size
            x_size = os.stat(lib+".idx").st_size
            self.assertTrue(z_size / x_size > 30)

    def test_import_still_works(self):
        lib = "libsmall.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        i = zipimportx.zipimporter(lib)
        del sys.modules["zipimportx"]
        self.assertTrue(i.find_module("zipimportx") is i)
        self.assertTrue(i.find_module("nonexistent") is None)
        fn = lib + os.sep + os.path.join("zipimportx","__init__.pyc")
        self.assertEquals(i._get_filename("zipimportx"),fn)
        zipimport._zip_directory_cache.clear()
        i = zipimportx.zipimporter(lib)
        zx2 = i.load_module("zipimportx")
        self.assertTrue("zipimporter" in zx2.__dict__)
        self.assertEquals(zx2.__file__,fn)
        #  Also check that importing from a subdir works correctly.
        i2 = zipimportx.zipimporter(lib+os.sep+"zipimportx")
        zxT = i2.load_module("tests")
        self.assertTrue("TestZipImportX" in zxT.__dict__)
        fn = lib + os.sep + os.path.join("zipimportx","tests","__init__.pyc")
        self.assertEquals(zxT.__file__,fn)
        
    def _do_timeit_init(self,lib):
        """Return unindexed and indexed initialisation times."""
        z_setupcode = "import zipimport"
        z_testcode = "".join(("zipimport._zip_directory_cache.clear(); ",
                              "i = zipimport.zipimporter(%r); " % (lib,)))
        z_timer = timeit.Timer(z_testcode,z_setupcode)
        z_time = min(self._do_timeit3(z_timer))
        x_setupcode = "import zipimport; import zipimportx; " \
                      "del sys.modules['zipimportx']; " \
                      "zipimportx.zipimporter(%r).write_index()" % (lib,)
        x_testcode = "".join(("zipimport._zip_directory_cache.clear(); ",
                              "i = zipimportx.zipimporter(%r); " % (lib,)))
        x_timer = timeit.Timer(x_testcode,x_setupcode)
        x_time = min(self._do_timeit3(x_timer))
        return (z_time,x_time)

    def _do_timeit_load(self,lib):
        """Return unindexed and indexed load times."""
        z_setupcode = "import zipimport; " \
                      "zipimport._zip_directory_cache.clear(); " \
                      "i = zipimport.zipimporter(%r)" % (lib,)
        z_testcode = "i.load_module('zipimportx'); del sys.modules['zipimportx']"
        z_timer = timeit.Timer(z_testcode,z_setupcode)
        z_time = min(self._do_timeit3(z_timer))
        x_setupcode = "".join(("import zipimport; import zipimportx; ",
                          "zipimportx.zipimporter(%r).write_index(); " % (lib,),
                          "zipimport._zip_directory_cache.clear(); ",
                          "i = zipimportx.zipimporter(%r)" % (lib,)))
        x_testcode = "i.load_module('zipimportx'); del sys.modules['zipimportx']"
        x_timer = timeit.Timer(x_testcode,x_setupcode)
        x_time = min(self._do_timeit3(x_timer))
        return (z_time,x_time)

    def _do_timeit3(self,t):
        return [self._do_timeit(t) for _ in xrange(3)]

    def _do_timeit(self,t):
        number = 10
        n = t.timeit(number)
        while n < 0.2:
            number = number * 10
            n = t.timeit(number)
        return n / number

    def test_README(self):
        """Ensure that the README is in sync with the docstring.

        This test should always pass; if the README is out of sync it just
        updates it with the contents of zipimportx.__doc__.
        """
        dirname = os.path.dirname
        readme = os.path.join(dirname(dirname(dirname(__file__))),"README.txt")
        if not os.path.isfile(readme):
            f = open(readme,"wb")
            f.write(zipimportx.__doc__.encode())
            f.close()
        else:
            f = open(readme,"rb")
            if f.read() != zipimportx.__doc__:
                f.close()
                f = open(readme,"wb")
                f.write(zipimportx.__doc__.encode())
                f.close()

