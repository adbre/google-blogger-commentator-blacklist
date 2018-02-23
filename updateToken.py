# http://updateToken.py 
#!/usr/bin/python
from googleapiclient import sample_tools
import sys

def main(argv):
    service, flags = sample_tools.init(
        argv, 'blogger', 'v3', __doc__, __file__,
        scope='https://www.googleapis.com/auth/blogger ')

if __name__ == '__main__':
    main(sys.argv)
