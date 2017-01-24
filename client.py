#!/usr/bin/python
from googleapiclient import discovery
from oauth2client import client
from oauth2client import file
from oauth2client import tools
from datetime import datetime, timedelta
from multiprocessing.dummy import Pool as ThreadPool
import sys
import re
import json
import os
import httplib2

class Logger:
    def debug(self, message):
        self._log('DEBUG', message)
    def info(self, message):
        self._log('INFO', message)
    def warn(self, message):
        self._log('WARNING', message)
    def error(self, message):
        self._log('ERROR', message)
    def _log(self, level, message):
        print('[%s] %s: %s' % (datetime.now(), level, message))

class Expando(object):
    pass

class Configuration:
    hours = 10
    blacklist = []
    contentBlacklist = []
    removalMethod = 'markAsSpam'
    blogId = ''

    def __init__(self, directory):
        file = os.path.join(os.path.dirname(directory),'config.json')
        with open(file) as h:
            cfg = json.load(h)
            self.blogId = self._getValue(cfg, 'blogId', self.blogId)
            self.hours = self._getValue(cfg, 'hours', self.hours)
            self.blacklist = self._getValue(cfg, 'blacklist', self.blacklist)
            self.contentBlacklist = self._getValue(cfg, 'contentBlacklist', self.contentBlacklist)
            self.removalMethod = self._getValue(cfg, 'removalMethod', self.removalMethod)

    def _getValue(self, cfg, propertyName, default):
        if propertyName in cfg and not (cfg[propertyName] is None):
            return cfg[propertyName]
        else:
            return default

class CommentBot:
    scannedPosts = 0
    scannedComments = 0
    removedComments = 0
    useThreading = True

    def __init__(self, log, config, directory):
        self._log = log
        self._config = config
        credentials, service = self.initCredentialsAndService('blogger','v3',directory)
        self._credentials = credentials
        self._service = service
        self._posts = service.posts()
        self._comments = service.comments()
        self._removalMethod = self.getRemovalMethod(self._comments)

    def scanBlog(self, blogId):
        if not re.match('^[0-9]+$', blogId):
            blogId = self._service.blogs().getByUrl(url=blogId).execute()['id']
            self._log.warn('Increase performance by replacing url `blogId` configuration with id %s'%blogId)

        startDate = '%sZ'%(datetime.utcnow()-timedelta(hours=self._config.hours)).isoformat('T')
        request = self._posts.list(blogId=blogId,startDate=startDate,maxResults=20)
        while request != None:
            resp = request.execute()
            if 'items' in resp and not (resp['items'] is None):
                if self.useThreading:
                    pool = ThreadPool(8)
                    pool.map(lambda post: self.scanPost(post), resp['items'])
                    pool.close()
                    pool.join()
                else:
                    for post in resp['items']:
                        self.scanPost(post, http = self.buildHttp())
            request = self._posts.list_next(request, resp)

    def scanPost(self, post, http = None):
        if http is None:
            http = self.buildHttp()
        request = self._comments.list(blogId=post['blog']['id'], postId=post['id'],status='live',maxResults=100)
        while request != None:
            resp = request.execute(http = http)
            if 'items' in resp and not (resp['items'] is None):
                for comment in resp['items']:
                    self.scanComment(comment, http = http)
            request = self._comments.list_next(request, resp)
        self.scannedPosts += 1

    def scanComment(self, comment, http = None):
        reason = self.hasReasonToRemove(comment)
        if http is None:
            http = self.buildHttp()
        if reason:
            self._log.info('Removing (%s) comment %s in post %s by author %s: %s' % (self._config.removalMethod,comment['id'],comment['post']['id'],comment['author']['id'],reason))
            self._removalMethod(blogId=comment['blog']['id'],postId=comment['post']['id'],commentId=comment['id']).execute(http=http)
            self.removedComments += 1
        self.scannedComments += 1

    def getRemovalMethod(self,comments):
        try:
            return getattr(comments, self._config.removalMethod)
        except AttributeError:
            print('Check configuration: removalMethod not valid: %s' % self._config.removalMethod)
            sys.exit(1)

    def hasReasonToRemove(self,comment):
        if comment['author']['id'] in self._config.blacklist:
            return 'Author is blacklisted'

        if comment['content']:
            for term in self._config.contentBlacklist:
                if term in comment['content']:
                    return 'Content contains blacklisted term: %s' % term

        return None

    def buildHttp(self, credentials = None):
        if credentials is None:
            credentials = self._credentials
        return credentials.authorize(http=httplib2.Http())

    def initCredentialsAndService(self, name, version, directory, scope = None, discovery_filename = None):
        if scope is None:
            scope = 'https://www.googleapis.com/auth/' + name

        client_secrets = os.path.join(directory, 'client_secrets.json')

        flow = client.flow_from_clientsecrets(client_secrets,
            scope=scope,
            message=tools.message_if_missing(client_secrets))

        storage = file.Storage(name + '.dat')
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            flags = Expando()
            flags.nonoauth_local_webserver = True
            credentials = tools.run_flow(flow, storage, flags)

        http = self.buildHttp(credentials)

        if discovery_filename is None:
            service = discovery.build(name, version, http=http)
        else:
            with open(discovery_filename) as discovery_file:
                service = discovery.build_from_document(
                    discovery_file.read(),
                    base='https://www.googleapis.com/',
                    http=http)

        return (credentials, service)

def main(argv):
    directory = os.path.dirname(__file__)
    log = Logger()
    config = Configuration(os.path.join(directory, 'config.json'))

    try:
        bot = CommentBot(log, config, directory)
        bot.scanBlog(config.blogId)
        log.info('%d scanned posts, %d scanned comments, %d removed comments' %(bot.scannedPosts, bot.scannedComments, bot.removedComments))
    except client.AccessTokenRefreshError:
        print('[%s] ERROR: The credentials have been revoked or expired, please re-run the application to re-authorize.'%(now()))

if __name__ == '__main__':
    main(sys.argv)
