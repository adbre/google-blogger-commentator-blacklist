#!/usr/bin/python
from oauth2client import client
from googleapiclient import sample_tools
from datetime import datetime, timedelta
import sys
import re
import json
import os

def now():
    return datetime.now()

def hasReasonToRemove(comment, config):
    if comment['author']['id'] in config['blacklist']:
        return 'Author is blacklisted'

    if 'contentBlacklist' in config and not (config['contentBlacklist'] is None):
        for term in config['contentBlacklist']:
            if term in comment['content']:
                return 'Content contains blacklisted term: %s'%term
    return None

def getRemovalMethod(comments, removalMethod):
    if removalMethod == 'delete':
        return comments.delete
    if removalMethod == 'markAsSpam':
        return comments.markAsSpam
    if removalMethod == 'removeContent':
        return comments.removeContent
    print('Check configuration: removalMethod not valid: %s' % removalMethod)
    sys.exit(1)

def main(argv):
    with open(os.path.join(os.path.dirname(__file__),'config.json')) as handle:
        config = json.load(handle)
        BLOG_ID = config['blogId']
        HOURS = config['hours']
        config['blacklist'] = map(str, config['blacklist'])
        if not 'removalMethod' in config or (config['removalMethod'] is None):
            config['removalMethod'] = 'markAsSpam'

    service, flags = sample_tools.init(
        argv, 'blogger', 'v3', __doc__, __file__,
        scope='https://www.googleapis.com/auth/blogger')

    try:
        blogs = service.blogs()
        posts = service.posts()
        comments = service.comments()

        removalMethod = getRemovalMethod(comments, config['removalMethod'])

        if not re.match('^[0-9]+$', BLOG_ID):
            BLOG_ID = blogs.getByUrl(url=BLOG_ID).execute()['id']

        postsScanned=0
        commentsScanned=0
        removedComments=0
        request = posts.list(blogId=BLOG_ID,startDate='%sZ'%(datetime.utcnow()-timedelta(hours=HOURS)).isoformat('T'))
        while request != None:
            posts_doc = request.execute()
            if 'items' in posts_doc and not (posts_doc['items'] is None):
                for post in posts_doc['items']:
                    request2 = comments.list(blogId=BLOG_ID,postId=post['id'],status='live')
                    while request2 != None:
                        comments_doc = request2.execute()
                        if 'items' in comments_doc and not (comments_doc['items'] is None):
                            for comment in comments_doc['items']:
                                reason = hasReasonToRemove(comment, config)
                                if reason:
                                    print('[%s] INFO: Removing (%s) comment %s in post %s by author %s: %s'%(now(),config['removalMethod'],comment['id'],post['id'],comment['author']['id'],reason))
                                    removalMethod(blogId=BLOG_ID,postId=post['id'],commentId=comment['id']).execute()
                                    removedComments+=1
                                commentsScanned+=1
                        request2 = comments.list_next(request2, comments_doc)
                    postsScanned+=1
            request = posts.list_next(request, posts_doc)

        print('[%s] INFO: %d scanned posts, %d scanned comments, %d removed comments'%(now(),postsScanned,commentsScanned,removedComments))
    except client.AccessTokenRefreshError:
        print('[%s] ERROR: The credentials have been revoked or expired, please re-run the application to re-authorize.'%(now()))

if __name__ == '__main__':
    main(sys.argv)
