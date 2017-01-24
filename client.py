#!/usr/bin/python
from oauth2client import client
from googleapiclient import sample_tools
from datetime import datetime, timedelta
import sys
import re
import json
import os

class Logger:
    def debug(self, message):
        self._log('DEBUG', message)
    def info(self, message):
        self._log('INFO', message)
    def warning(self, message):
        self._log('WARNING', message)
    def error(self, message):
        self._log('ERROR', message)
    def _log(self, level, message):
        print('[%s] %s: %s' % (datetime.now(), level, message))

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

    def __init__(self, log, config, service):
        self._log = log
        self._config = config
        self._service = service
        self._posts = service.posts()
        self._comments = service.comments()
        self._removalMethod = self.getRemovalMethod(self._comments)

    def scanBlog(self, blogId):
        if not re.match('^[0-9]+$', blogId):
            blogId = self._service.blogs().getByUrl(url=blogId).execute()['id']
            self._log.warning('Increase performance by replacing url `blogId` configuration with id %s'%blogId)

        startDate = '%sZ'%(datetime.utcnow()-timedelta(hours=self._config.hours)).isoformat('T')
        request = self._posts.list(blogId=blogId,startDate=startDate)
        while request != None:
            resp = request.execute()
            if 'items' in resp and not (resp['items'] is None):
                for post in resp['items']:
                    self.scanPost(post)
            request = self._posts.list_next(request, resp)

    def scanPost(self, post):
        request = self._comments.list(blogId=post['blog']['id'], postId=post['id'],status='live')
        while request != None:
            resp = request.execute()
            if 'items' in resp and not (resp['items'] is None):
                for comment in resp['items']:
                    self.scanComment(comment)
            request = self._comments.list_next(request, resp)
        self.scannedPosts += 1

    def scanComment(self, comment):
        reason = self.hasReasonToRemove(comment)
        if reason:
            self._log.info('Removing (%s) comment %s in post %s by author %s: %s' % (self._config.removalMethod,comment['id'],comment['post']['id'],comment['author']['id'],reason))
            self._removalMethod(blogId=comment['blog']['id'],postId=comment['post']['id'],commentId=comment['id']).execute()
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

def main(argv):
    log = Logger()
    config = Configuration(__file__)

    service, flags = sample_tools.init(
        argv, 'blogger', 'v3', __doc__, __file__,
        scope='https://www.googleapis.com/auth/blogger')

    bot = CommentBot(log, config, service)

    try:
        bot.scanBlog(config.blogId)
        log.info('%d scanned posts, %d scanned comments, %d removed comments' %(bot.scannedComments, bot.scannedPosts, bot.removedComments))
    except client.AccessTokenRefreshError:
        print('[%s] ERROR: The credentials have been revoked or expired, please re-run the application to re-authorize.'%(now()))

if __name__ == '__main__':
    main(sys.argv)
