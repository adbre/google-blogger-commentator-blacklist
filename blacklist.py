#!/usr/bin/python
import json
import sys
import re
import os

def main(argv):

    if len(argv) < 2:
        print('USAGE: %s AUTHOR_ID|PROFILE_ID'%argv[0])
        sys.exit(1)

    m = re.match('(.*[^0-9])?([0-9]+)$', argv[1])
    if not m:
        print('Could not find author id in string: %s'%argv[1])
        sys.exit(1)

    authorId=m.group(2)

    config_file = os.path.join(os.path.dirname(__file__),'config.json')

    with open(config_file, 'r') as handle:
        config = json.load(handle)

    if not authorId in config['blacklist']:
        config['blacklist'].append(authorId)

        with open(config_file, 'w') as handle:
            json.dump(config, handle, indent=4, sort_keys=True)

        print('Added %s to blacklist'%authorId)
    else:
        print('AuthorId %s already exists in blacklist'%authorId)

if __name__ == '__main__':
    main(sys.argv)
