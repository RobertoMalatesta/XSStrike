#!/usr/bin/env python3

from __future__ import print_function

# Let's import whatever we need from standard lib
import argparse

# ... and from core lib
import core.config
from core.colors import end, info, red, run, white, bad
from core.config import blindPayload
from core.encoders import base64
from core.photon import photon
from core.prompt import prompt
from core.updater import updater
from core.utils import extractHeaders, verboseOutput

from modes.bruteforcer import bruteforcer
from modes.crawl import crawl
from modes.scan import scan
from modes.singleFuzz import singleFuzz

# Just a fancy ass banner
print('''%s
\tXSStrike %sv3.0.5
%s''' % (red, white, end))

try:
    import concurrent.futures
    from urllib.parse import urlparse
except ImportError:  # throws error in python2
    print('%s XSStrike isn\'t compatible with python2.\n Use python > 3.4 to run XSStrike.' % bad)
    quit()


# Processing command line arguments, where dest var names will be mapped to local vars with the same name
parser = argparse.ArgumentParser()
parser.add_argument('-u', '--url', help='url', dest='target')
parser.add_argument('--data', help='post data', dest='paramData')
parser.add_argument('-e', '--encode', help='encode payloads', dest='encode')
parser.add_argument('--fuzzer', help='fuzzer',
                    dest='fuzz', action='store_true')
parser.add_argument('--update', help='update',
                    dest='update', action='store_true')
parser.add_argument('--timeout', help='timeout',
                    dest='timeout', type=int, default=core.config.timeout)
parser.add_argument('--proxy', help='use prox(y|ies)',
                    dest='proxy', action='store_true')
parser.add_argument('--params', help='find params',
                    dest='find', action='store_true')
parser.add_argument('--crawl', help='crawl',
                    dest='recursive', action='store_true')
parser.add_argument(
    '--seeds', help='load crawling seeds from a file', dest='args_seeds')
parser.add_argument(
    '-f', '--file', help='load payloads from a file', dest='args_file')
parser.add_argument('-l', '--level', help='level of crawling',
                    dest='level', type=int, default=2)
parser.add_argument('--headers', help='add headers',
                    dest='add_headers', action='store_true')
parser.add_argument('-t', '--threads', help='number of threads',
                    dest='threadCount', type=int, default=core.config.threadCount)
parser.add_argument('-d', '--delay', help='delay between requests',
                    dest='delay', type=int, default=core.config.delay)
parser.add_argument('--skip', help='don\'t ask to continue',
                    dest='skip', action='store_true')
parser.add_argument('--skip-dom', help='skip dom checking',
                    dest='skipDOM', action='store_true')
parser.add_argument('-v', '--vectors', help='verbose output',
                    dest='verbose', action='store_true')
parser.add_argument('--blind', help='inject blind XSS payload while crawling',
                    dest='blindXSS', action='store_true')
args = parser.parse_args()

if args.add_headers:
    headers = extractHeaders(prompt())
else:
    from core.config import headers

# Pull all parameter values of dict from argparse namespace into local variables of name == key
# The following works, but the static checkers are too static ;-) locals().update(vars(args))
target = args.target
paramData = args.paramData
encode = args.encode
fuzz = args.fuzz
update = args.update
timeout = args.timeout
proxy = args.proxy
find = args.find
recursive = args.recursive
args_file = args.args_file
args_seeds = args.args_seeds
level = args.level
add_headers = args.add_headers
threadCount = args.threadCount
delay = args.delay
skip = args.skip
skipDOM = args.skipDOM
verbose = args.verbose
blindXSS = args.blindXSS

if args_file:
    if args_file == 'default':
        payloadList = core.config.payloads
    else:
        payloadList = []
        with open(args_file, 'r') as f:
            for line in f:
                payloadList.append(line.strip(
                    '\n').encode('utf-8').decode('utf-8'))
        payloadList = list(filter(None, payloadList))

seedList = []
if args_seeds:
    with open(args_seeds, 'r') as f:
        for line in f:
            seedList.append(line.strip(
                '\n').encode('utf-8').decode('utf-8'))
    seedList = list(filter(None, seedList))

encoding = base64 if encode and encode == 'base64' else False

if not proxy:
    core.config.proxies = {}

if update:  # if the user has supplied --update argument
    updater()
    quit()  # quitting because files have been changed

if not target and not args_seeds:  # if the user hasn't supplied a url
    print('\n' + parser.format_help().lower())
    quit()

if fuzz:
    singleFuzz(target, paramData, verbose, encoding, headers, delay, timeout)
elif not recursive and not args_seeds:
    if args_file:
        bruteforcer(target, paramData, payloadList, verbose, encoding, headers, delay, timeout)
    else:
        scan(target, paramData, verbose, encoding, headers, delay, timeout, skipDOM, find, skip)
else:
    if target:
        seedList.append(target)
    for target in seedList:
        print('%s Crawling the target' % run)
        scheme = urlparse(target).scheme
        verboseOutput(scheme, 'scheme', verbose)
        host = urlparse(target).netloc
        main_url = scheme + '://' + host
        crawlingResult = photon(target, headers, level,
                                threadCount, delay, timeout)
        forms = crawlingResult[0]
        domURLs = list(crawlingResult[1])
        difference = abs(len(domURLs) - len(forms))
        if len(domURLs) > len(forms):
            for i in range(difference):
                forms.append(0)
        elif len(forms) > len(domURLs):
            for i in range(difference):
                domURLs.append(0)
        threadpool = concurrent.futures.ThreadPoolExecutor(max_workers=threadCount)
        futures = (threadpool.submit(crawl, scheme, host, main_url, form, domURL, verbose,
                                     blindXSS, blindPayload, headers, delay, timeout, skipDOM, encoding) for form, domURL in zip(forms, domURLs))
        for i, _ in enumerate(concurrent.futures.as_completed(futures)):
            if i + 1 == len(forms) or (i + 1) % threadCount == 0:
                print('%s Progress: %i/%i' % (info, i + 1, len(forms)), end='\r')
        print()
