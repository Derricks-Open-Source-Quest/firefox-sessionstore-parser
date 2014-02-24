
import unittest

import StringIO

import sessionstoreparser as p

class TestTryMain(unittest.TestCase):

  def test_noerror(self):
    report = []
    class FakeMain(object):
      def handleargv(self, argv):
        report.append(('handleargv', argv))
        return 'filename'
      def getsessionstore(self, filename):
        report.append(('getsessionstore', filename))
        return 'sessionstore'
      def geturlgenerator(self):
        report.append(('geturlgenerator', ))
        return 'urlgenerator'
      def geturls(self, urlgenerator, sessionstore):
        report.append(('geturls', urlgenerator, sessionstore))
        return 'urls'
      def writeurls(self, urls):
        report.append(('writeurls', urls))
    fakemain = FakeMain()
    argv = ['wat']
    p.Main.trymain.__func__(fakemain, argv)
    self.assertEqual(report, [
          ('handleargv', ['wat']),
          ('getsessionstore', 'filename'),
          ('geturlgenerator', ),
          ('geturls', 'urlgenerator', 'sessionstore'),
          ('writeurls', 'urls')])

class TestMain(unittest.TestCase):

  def test_noerror(self):
    report = []
    class FakeMain(object):
      def trymain(self, argv):
        report.append(('trymain', argv))
    fakemain = FakeMain()
    argv = ['wat']
    exitstatus, errormessage = p.Main.main.__func__(fakemain, argv)
    self.assertEqual(errormessage, None)
    self.assertEqual(exitstatus, 0)
    self.assertEqual(report, [
          ('trymain', ['wat'])])

  def test_error(self):
    report = []
    class FakeMain(object):
      def trymain(self, argv):
        report.append(('trymain', argv))
        raise p.MainError('silly error')
    fakemain = FakeMain()
    argv = ['wat']
    exitstatus, errormessage = p.Main.main.__func__(fakemain, argv)
    self.assertEqual(errormessage, 'silly error')
    self.assertEqual(exitstatus, 1)
    self.assertEqual(report, [
          ('trymain', ['wat'])])
