
# this file is named sessionstoreparsertest to avoid name conflict

import unittest

import sessionstoreparser as p

class TestSessionStoreParse(unittest.TestCase):

  def test_noerror(self):
    report = []
    class FakeSessionStoreProducer(object):
      def produce(self):
        report.append(('produce', ))
        return {'json': 'object'}
    class FakeUrlProducer(object):
      def produce(self, sessionstore):
        report.append(('produce', sessionstore))
        return ['urls']
    class FakeUrlFilter(object):
      def filter(self, urls):
        report.append(('filter', urls))
        return ['filtered', 'urls']
    class FakeUrlConsumer(object):
      def consume(self, urls):
        report.append(('consume', urls))
    parser = p.SessionStoreParser(
          FakeSessionStoreProducer(), FakeUrlProducer(),
          FakeUrlFilter(), FakeUrlConsumer())
    parser.parse()
    self.assertEqual(report, [
          ('produce', ),
          ('produce', {'json': 'object'}),
          ('filter', ['urls']),
          ('consume', ['filtered', 'urls'])])
