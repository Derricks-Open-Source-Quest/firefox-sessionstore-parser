#! /usr/bin/env python

import getopt
import json

class Error(Exception):
  pass

class ArgvParser(object):
  def __init__(self, getoptfunc, optionsdata, argumentsdata):
    self.getoptfunc = getoptfunc
    self.optionsdata = optionsdata
    self.argumentsdata = argumentsdata

  def prepareoptstring(self, opt, argcount, argmod):
    strippedopt = opt.lstrip('-')
    if argcount == 0:
      optstring = strippedopt
    else:
      optstring = strippedopt + argmod
    return optstring

  def prepareopt(self, opt, argcount):
    shortoptslist = []
    longopts = []
    if opt.startswith('--'):
      optstring = self.prepareoptstring(opt, argcount, '=')
      longopts.append(optstring)
    else:
      optstring = self.prepareoptstring(opt, argcount, ':')
      shortoptslist.append(optstring)
    return shortoptslist, longopts

  def prepareoptiondata(self, optiondata):
    shortoptslist = []
    longopts = []
    optnames = {}
    name, opts, argcount = optiondata
    for opt in opts:
      shorts, longs = self.prepareopt(opt, argcount)
      shortoptslist.extend(shorts)
      longopts.extend(longs)
      optnames[opt] = name
    return shortoptslist, longopts, optnames

  def prepareoptionsdata(self, optionsdata):
    # no error checking
    # let's assume everyone is sane
    shortoptslist = []
    longopts = []
    optnames = {}
    for optiondata in optionsdata:
      shorts, longs, names = self.prepareoptiondata(optiondata)
      shortoptslist.extend(shorts)
      longopts.extend(longs)
      optnames.update(names)
    shortopts = ''.join(shortoptslist)
    return shortopts, longopts, optnames

  def dictifyopts(self, opts, optnames):
    optsdict = {}
    for opt, val in opts:
      name = optnames[opt]
      optsdict[name] = val
    return optsdict

  def splitopts(self, argv):
    shortopts, longopts, optnames = self.prepareoptionsdata(self.optionsdata)
    opts, args = self.getoptfunc(argv, shortopts, longopts)
    optsdict = self.dictifyopts(opts, optnames)
    return optsdict, args

  def splitargs(self, args):
    argsdict = {}
    restargv = args
    for name in self.argumentsdata:
      if len(restargv) > 0:
        arg = restargv[0]
        restargv = restargv[1:]
        argsdict[name] = arg
      else:
        break
    return argsdict, restargv

  def combine(self, optsdict, argsdict):
    parsedargv = {}
    parsedargv.update(optsdict)
    parsedargv.update(argsdict)
    return parsedargv

  def tryparse(self, argv):
    optsdict, args = self.splitopts(argv)
    argsdict, restargv = self.splitargs(args)
    parsedargv = self.combine(optsdict, argsdict)
    return parsedargv, restargv

  def parse(self, argv):
    try:
      parsedargv, restargv = self.tryparse(argv)
    except getopt.GetoptError as err:
      parsedargv = {}
      unknownoption = str(err).split()[1]
      restargv = [unknownoption]
    return parsedargv, restargv

class HelpPrinter(object):
  def __init__(self, stream, message, exitstatus):
    self.stream = stream
    self.message = message
    self.exitstatus = exitstatus

  def work(self):
    self.stream.write(self.message + '\n')
    return self.exitstatus

class JsonReaderError(Error):
  pass

class JsonReader(object):
  def __init__(self, openfunc, jsonloadfunc):
    self.openfunc = openfunc
    self.jsonloadfunc = jsonloadfunc

  def openfile(self, filename):
    try:
      fileob = self.openfunc(filename)
      return fileob
    except IOError:
      raise JsonReaderError('error: cannot open file %s.' % filename)

  def jsonload(self, fileob, filename):
    try:
      sessionstore = self.jsonloadfunc(fileob)
      return sessionstore
    except ValueError:
      raise JsonReaderError(
            'error: cannot read session store from file %s.' % filename)

  def read(self, filename):
    with self.openfile(filename) as fileob:
      sessionstore = self.jsonload(fileob, filename)
    return sessionstore

class SessionStoreProducer(object):
  def __init__(self, jsonreader, filename):
    self.jsonreader = jsonreader
    self.filename = filename

  def produce(self):
    return self.jsonreader.read(self.filename)

class UrlProducer(object):
  def __init__(self):
    pass

  def handleentry(self, entry):
    plainurl = entry['url']
    url = {'url': plainurl}
    yield url

  def handletab(self, tab):
    openindex = tab['index'] - 1
    entries = tab['entries']
    for index, entry in enumerate(entries):
      for url in self.handleentry(entry):
        if index < openindex:
          url['entry'] = 'back'
        elif index > openindex:
          url['entry'] = 'forward'
        else: # index == openindex:
          url['entry'] = 'selected'
        yield url

  def handlewindow(self, window):
    for tab in window['tabs']:
      for url in self.handletab(tab):
        url['tab'] = 'open'
        yield url
    for tab in window['_closedTabs']:
      for url in self.handletab(tab['state']):
        url['tab'] = 'closed'
        yield url

  def handlesessionstore(self, sessionstore):
    for window in sessionstore['windows']:
      for url in self.handlewindow(window):
        url['window'] = 'open'
        yield url
    for window in sessionstore['_closedWindows']:
      for url in self.handlewindow(window):
        url['window'] = 'closed'
        yield url

  def generate(self, sessionstore):
    for url in self.handlesessionstore(sessionstore):
      yield url

  def produce(self, sessionstore):
    return self.generate(sessionstore)

class AndPredicate(object):
  def __init__(self, predicates):
    self.predicates = predicates

  def true(self, url):
    for predicate in self.predicates:
      if not predicate.true(url):
        return False
    return True

class UrlAttributePredicate(object):
  def __init__(self, key, value):
    self.key = key
    self.value = value

  def true(self, url):
    return url[self.key] == self.value

class UrlFilter(object):
  def __init__(self, predicate):
    self.predicate = predicate

  def filter(self, urls):
    for url in urls:
      if self.predicate.true(url):
        yield url

class UrlWriter(object):
  def __init__(self, stdout):
    self.stdout = stdout

  def write(self, urls):
    for url in urls:
      self.stdout.write(url['url'] + '\n')

  def consume(self, urls):
    self.write(urls)

class SessionStoreParser(object):
  def __init__(self,
        sessionstoreproducer, urlproducer, urlfilter, urlconsumer):
    self.sessionstoreproducer = sessionstoreproducer
    self.urlproducer = urlproducer
    self.urlfilter = urlfilter
    self.urlconsumer = urlconsumer

  def parse(self):
    sessionstore = self.sessionstoreproducer.produce()
    urls = self.urlproducer.produce(sessionstore)
    filteredurls = self.urlfilter.filter(urls)
    self.urlconsumer.consume(filteredurls)

  def work(self):
    self.parse()
    return 0

class HelpPrinterFactory(object):
  def __init__(self, helpprinterclass, stderr):
    self.helpprinterclass = helpprinterclass
    self.stderr = stderr

  def make(self, message):
    worker = self.helpprinterclass(self.stderr, message, 2)
    return worker

class SessionStoreProducerFactory(object):
  def __init__(self, jsonreaderclass, sessionstoreproducerclass, openfunc):
    self.jsonreaderclass = jsonreaderclass
    self.sessionstoreproducerclass = sessionstoreproducerclass
    self.openfunc = openfunc

  def make(self, parsedargv):
    try:
      filename = parsedargv['filename']
    except KeyError:
      raise Error('missing argument: filename')
    jsonreader = self.jsonreaderclass(self.openfunc, json.load)
    sessionstoreproducer = self.sessionstoreproducerclass(jsonreader, filename)
    return sessionstoreproducer

class UrlProducerFactory(object):
  def __init__(self, urlproducerclass):
    self.urlproducerclass = urlproducerclass

  def make(self, parsedargv):
    urlproducer = self.urlproducerclass()
    return urlproducer

class UrlFilterFactory(object):
  def __init__(self, urlfilterclass):
    self.urlfilterclass = urlfilterclass

  def getstates(self, parsedargv):
    windowstate = 'open'
    tabstate = 'open'
    entrystate = 'selected'
    if 'all' in parsedargv:
      windowstate = 'all'
      tabstate = 'all'
      entrystate = 'selected'
    if 'allwithhistory' in parsedargv:
      windowstate = 'all'
      tabstate = 'all'
      entrystate = 'all'
    if 'window' in parsedargv:
      windowstate = parsedargv['window']
    if 'tab' in parsedargv:
      tabstate = parsedargv['tab']
    if 'entry' in parsedargv:
      entrystate = parsedargv['entry']
    return windowstate, tabstate, entrystate

  def getpredicate(self, windowstate, tabstate, entrystate):
    predicatelist = []
    if windowstate != 'all':
      windowpredicate = UrlAttributePredicate('window', windowstate)
      predicatelist.append(windowpredicate)
    if tabstate != 'all':
      tabpredicate = UrlAttributePredicate('tab', tabstate)
      predicatelist.append(tabpredicate)
    if entrystate != 'all':
      entrypredicate = UrlAttributePredicate('entry', entrystate)
      predicatelist.append(entrypredicate)
    predicate = AndPredicate(predicatelist)
    return predicate

  def make(self, parsedargv):
    windowstate, tabstate, entrystate = self.getstates(parsedargv)
    predicate = self.getpredicate(windowstate, tabstate, entrystate)
    urlfilter = self.urlfilterclass(predicate)
    return urlfilter

class UrlConsumerFactory(object):
  def __init__(self, urlconsumerclass, stdout):
    self.urlconsumerclass = urlconsumerclass
    self.stdout = stdout

  def make(self, parsedargv):
    urlconsumer = self.urlconsumerclass(self.stdout)
    return urlconsumer

class SessionStoreParserFactory(object):
  def __init__(self,
        sessionstoreproducerfactory,
        urlproducerfactory,
        urlfilterfactory,
        urlconsumerfactory,
        sessionstoreparserclass):
    self.sessionstoreproducerfactory = sessionstoreproducerfactory
    self.urlproducerfactory = urlproducerfactory
    self.urlfilterfactory = urlfilterfactory
    self.urlconsumerfactory = urlconsumerfactory
    self.sessionstoreparserclass = sessionstoreparserclass

  def make(self, parsedargv):
    sessionstoreproducer = self.sessionstoreproducerfactory.make(parsedargv)
    urlproducer = self.urlproducerfactory.make(parsedargv)
    urlfilter = self.urlfilterfactory.make(parsedargv)
    urlconsumer = self.urlconsumerfactory.make(parsedargv)
    sessionstoreparser = self.sessionstoreparserclass(
          sessionstoreproducer, urlproducer, urlfilter, urlconsumer)
    return sessionstoreparser

class WorkerFactory(object):
  def __init__(self, helpprinterfactory, sessionstoreparserfactory):
    self.helpprinterfactory = helpprinterfactory
    self.sessionstoreparserfactory = sessionstoreparserfactory

  def make(self, parsedargv, restargv):
    if len(restargv) != 0:
      unknownoption = restargv[0]
      message = 'unknown option: %s' % (unknownoption)
      worker = self.helpprinterfactory.make(message)
    else:
      try:
        worker = self.sessionstoreparserfactory.make(parsedargv)
      except Error as err:
        message = str(err)
        worker = self.helpprinterfactory.make(message)
    return worker

class Application(object):

  def __init__(self, argvparser, workerfactory, stderr):
    self.argvparser = argvparser
    self.workerfactory = workerfactory
    self.stderr = stderr

  def tryrun(self, argv):
    parsedargv, restargv = self.argvparser.parse(argv[1:])
    worker = self.workerfactory.make(parsedargv, restargv)
    exitstatus = worker.work()
    return exitstatus

  def run(self, argv):
    try:
      exitstatus = self.tryrun(argv)
      return exitstatus
    except Error as err:
      self.stderr.write(str(err) + '\n')
      return 1

class ApplicationFactory(object):
  def __init__(self, stdout, stderr, openfunc):
    self.stdout = stdout
    self.stderr = stderr
    self.openfunc = openfunc

  def getdefaults(self):
    optionsdata = [
          ('all', ['--all'], 0),
          ('allwithhistory', ['--all-with-history'], 0),
          ('window', ['--window'], 1),
          ('tab', ['--tab'], 1),
          ('entry', ['--url'], 1)]
    argumentsdata = [
          'filename']
    defaults = {
          'optionsdata': optionsdata,
          'argumentsdata': argumentsdata,
          'argvparserclass': ArgvParser,
          'helpprinterfactoryclass': HelpPrinterFactory,
          'helpprinterclass': HelpPrinter,
          'jsonreaderclass': JsonReader,
          'sessionstoreproducerfactoryclass': SessionStoreProducerFactory,
          'sessionstoreproducerclass': SessionStoreProducer,
          'urlproducerfactoryclass': UrlProducerFactory,
          'urlproducerclass': UrlProducer,
          'urlfilterfactoryclass': UrlFilterFactory,
          'urlfilterclass': UrlFilter,
          'urlconsumerfactoryclass': UrlConsumerFactory,
          'urlwriterclass': UrlWriter,
          'sessionstoreparserfactoryclass': SessionStoreParserFactory,
          'sessionstoreparserclass': SessionStoreParser,
          'workerfactoryclass': WorkerFactory,
          'applicationclass': Application}
    return defaults

  def make(self, optionsdata, argumentsdata,
        argvparserclass,
        helpprinterfactoryclass,
        helpprinterclass,
        jsonreaderclass,
        sessionstoreproducerfactoryclass,
        sessionstoreproducerclass,
        urlproducerfactoryclass,
        urlproducerclass,
        urlfilterfactoryclass,
        urlfilterclass,
        urlconsumerfactoryclass,
        urlwriterclass,
        sessionstoreparserfactoryclass,
        sessionstoreparserclass,
        workerfactoryclass,
        applicationclass):
    #pylint: disable=too-many-arguments
    #pylint: disable=too-many-locals
    #pylint: disable=invalid-name
    argvparser = argvparserclass(
          getopt.getopt,
          optionsdata,
          argumentsdata)
    helpprinterfactory = helpprinterfactoryclass(
          helpprinterclass,
          self.stderr)
    sessionstoreproducerfactory = sessionstoreproducerfactoryclass(
          jsonreaderclass,
          sessionstoreproducerclass,
          self.openfunc)
    urlproducerfactory = urlproducerfactoryclass(
          urlproducerclass)
    urlfilterfactory = urlfilterfactoryclass(
          urlfilterclass)
    urlconsumerfactory = urlconsumerfactoryclass(
          urlwriterclass,
          self.stdout)
    sessionstoreparserfactory = sessionstoreparserfactoryclass(
          sessionstoreproducerfactory,
          urlproducerfactory,
          urlfilterfactory,
          urlconsumerfactory,
          sessionstoreparserclass)
    workerfactory = workerfactoryclass(
          helpprinterfactory,
          sessionstoreparserfactory)
    app = applicationclass(
          argvparser,
          workerfactory,
          self.stderr)
    return app

  def makedefaults(self):
    defaults = self.getdefaults()
    app = self.make(**defaults)
    return app

def secludedmain(argv, stdout, stderr, openfunc):
  appfactory = ApplicationFactory(stdout, stderr, openfunc)
  app = appfactory.makedefaults()
  exitstatus = app.run(argv)
  return exitstatus

def main(): # pragma: no cover
  import sys
  exitstatus = secludedmain(sys.argv, sys.stdout, sys.stderr, open)
  return exitstatus
