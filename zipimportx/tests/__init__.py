
import os
import unittest
import timeit
import zipimport
import zipfile

import zipimportx

#  I don't actually use these, I just add them to a zipfile.
#  There here so I can grab __file__ off them.
import distutils
import logging
import email
import sqlite3
import ctypes

LIBHOME = os.path.dirname(unittest.__file__)


class TestZipImportX(unittest.TestCase):

    def setUp(self):
        lib = "libsmall.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if not os.path.exists(lib):
            zf = zipfile.PyZipFile(lib,"w")
            zf.writepy(os.path.dirname(zipimportx.__file__))
            zf.writepy(os.path.dirname(distutils.__file__))
            zf.writepy(os.path.dirname(logging.__file__))
            zf.writepy(os.path.dirname(email.__file__))
            zf.writepy(os.path.dirname(sqlite3.__file__))
            zf.writepy(os.path.dirname(ctypes.__file__))
            zf.close()
        lib = "libmedium.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if not os.path.exists(lib):
            zf = zipfile.PyZipFile(lib,"w")
            zf.writepy(LIBHOME)
            zf.close()
        lib = "liblarge.zip"
        lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
        if not os.path.exists(lib):
            zf = zipfile.PyZipFile(lib,"w")
            zf.writepy(LIBHOME)
            for (dirnm,subdirs,files) in os.walk(LIBHOME):
                if "__init__.pyc" in files:
                    del subdirs[:]
                    zf.writepy(dirnm)
            zf.close()

    def test_performance_increase(self):
        ratios = {
            "libsmall.zip": 2.5,
            "libmedium.zip": 3,
            "liblarge.zip": 3.5,
        }
        for libnm in ratios:
            lib = os.path.abspath(os.path.join(os.path.dirname(__file__),libnm))
            (zt,xt) = self._do_timeit_compare(lib)
            self.assertTrue(zt/xt > ratios[libnm])

    def test_space_overhead(self):
        for lib in ("libsmall.zip","libmedium.zip","liblarge.zip"):
            lib = os.path.abspath(os.path.join(os.path.dirname(__file__),lib))
            zipimportx.zipimporter(lib).write_index()
            z_size = os.stat(lib).st_size
            x_size_p = os.stat(lib+".posix.idx").st_size
            x_size_w = os.stat(lib+".win32.idx").st_size
            self.assertEquals(x_size_p,x_size_w)
            self.assertTrue(z_size / x_size_p > 40)

    def _do_timeit_compare(self,lib):
        """Return a pair (ztime,xtime) giving unindexed and indexed times."""
        z_setupcode = "import zipimport"
        z_testcode = "zipimport._zip_directory_cache.clear(); " \
                     "zipimport.zipimporter(%r)" % (lib,)
        z_timer = timeit.Timer(z_testcode,z_setupcode)
        z_time = min(self._do_timeit3(z_timer))
        x_setupcode = "import zipimport; import zipimportx; " \
                      "zipimportx.zipimporter(%r).write_index()" % (lib,)
        x_testcode = "zipimport._zip_directory_cache.clear(); " \
                     "zipimportx.zipimporter(%r)" % (lib,)
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

