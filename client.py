#!/usr/bin/python
from googleapiclient import discovery
from oauth2client import client
from oauth2client import file
from oauth2client import tools
from datetime import datetime, timedelta
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

    _maxResults = 200

    def __init__(self, log, config, directory):
        self._log = log
        self._config = config
        credentials, service = self.initCredentialsAndService('blogger','v3',directory)
        self._credentials = credentials
        self._service = service
        self._posts = service.posts()
        self._comments = service.comments()
        self._removalMethod = self.getRemovalMethod(self._comments)

    def scanBlog(self, blogUrl):
        blogId = self.getBlogId(blogUrl)
        posts = self.getPosts(blogId)
        comments = self.getComments(posts)
        pendingRemoval = self.getCommentsToRemove(comments)
        self.removeComments(pendingRemoval)

        self.scannedPosts = len(posts)
        self.scannedComments = len(comments)

    def getBlogId(self, blogUrl):
        if re.match('^[0-9]+$', blogUrl):
            return blogUrl

        blogId = self._service.blogs().getByUrl(url=blogUrl).execute()['id']
        self._log.warn('Increase performance by replacing url `blogId` configuration with id %s'%blogId)
        return blogId

    def getPosts(self, blogId):
        startDate = '%sZ'%(datetime.utcnow()-timedelta(hours=self._config.hours)).isoformat('T')
        request = self._posts.list(blogId=blogId,startDate=startDate,maxResults=self._maxResults,fields='items(id,blog),nextPageToken')
        posts = []
        while request != None:
            resp = request.execute()
            if 'items' in resp and not (resp['items'] is None):
                posts.extend(resp['items'])
            request = self._posts.list_next(request, resp)
        return posts

    def getComments(self, posts):
        fields = 'items(author/id,blog,content,id,post),nextPageToken'
        comments = []
        current_requests = []
        next_requests = []

        for post in posts:
            next_requests.append(self._comments.list(blogId=post['blog']['id'],postId=post['id'],status='live',maxResults=self._maxResults))

        def on_comments(request_id, response, exception):
            if exception is not None:
                self._log.error(exception)
                return

            request = current_requests[int(request_id)]
            next_request = self._posts.list_next(request, response)
            if next_request != None:
                next_requests.append(next_request)

            if 'items' in response and not (response['items'] is None):
                comments.extend(response['items'])

        batch = self._service.new_batch_http_request(callback=on_comments)
        while batch != None:
            for i,request in enumerate(next_requests):
                batch.add(request, request_id=str(i))
            current_requests = next_requests
            next_requests = []
            batch.execute()
            if len(next_requests) > 0:
                batch = self._service.new_batch_http_request(callback=on_comments)
            else:
                batch = None

        return comments

    def getCommentsToRemove(self, comments):
        toRemove = []
        for comment in comments:
            reason = self.hasReasonToRemove(comment)
            if reason:
                toRemove.append((comment,reason))
        return toRemove

    def removeComments(self, removals):
        def on_removed(request_id, response, exception):
            if exception is not None:
                self._log.error(exception)
                return

            comment,reason = removals[int(request_id)]
            self._log.info('Removed (%s) comment %s in post %s by author %s: %s' % (self._config.removalMethod,comment['id'],comment['post']['id'],comment['author']['id'],reason))
            self.removedComments += 1

        batch = self._service.new_batch_http_request(callback=on_removed)
        for i,removal in enumerate(removals):
            comment,reason=removal
            batch.add(self._removalMethod(
                blogId=comment['blog']['id'],
                postId=comment['post']['id'],
                commentId=comment['id']
            ), request_id=str(i))

        batch.execute()

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

        http = credentials.authorize(http=httplib2.Http())

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
