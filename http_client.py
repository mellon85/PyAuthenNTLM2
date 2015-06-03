#!/usr/bin/pytho
#
# PyAuthenNTLM2: A mod-python module for Apache that carries out NTLM authentication
#
# http_client.py
#
# Copyright 2012 Legrandin <helderijs@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import time
import getopt
import base64
from PyAuthenNTLM2.ntlm_client import NTLM_Client
import httplib
import urlparse

def print_help():
    print
    print "Perform an authenticated HTTP GET request. Basic Authentication or NTLM can be used."
    print "http_client {-u|--user} usr {-p|--password} pwd [{-d|--domain} DOMAIN] URL"
    print
    print "If the -d option is not provided, use Basic. If it is, use NTLM" 
    sys.exit(-1)


def basic_request(url, user, password, proxy=None):
    headers = {}

    if not url.startswith('http'):
        url = '//' + url
    (scheme, hostport, path, params, query, frag ) = urlparse.urlparse(url)
    connect_hostport = hostport

    if proxy:
        if not url.startswith('http'):
            url = '//' + url
        (proxy_scheme, proxy_hostport, proxy_path, proxy_params,
                proxy_query, proxy_frag ) = urlparse.urlparse(proxy)
        connect_hostport = proxy_hostport

    conn = httplib.HTTPConnection(connect_hostport)

    if 'Connection' in headers:
        del headers['Connection']
    headers['Host'] = hostport

    conn.request('GET',path,None,headers)
    resp = conn.getresponse()
    resp.read()

    if resp.status == 200:
        print "No Authentication Required"
        return False
    if resp.status<400:
        return 'Authorization' in headers

    if resp.status not in (401, 407):
        print "Error in HTTP request", resp.status, resp.reason
        return False
    print "Authentication Required"

    header = 'WWW-Authenticate'
    if proxy:
        header = 'proxy-authenticate'

    if 'basic' not in resp.getheader(header).lower():
        print "Basic Authentication is not supported"
        return False
    conn.close()

    # Process 401/407
    conn = httplib.HTTPConnection(connect_hostport)
    auth = "Basic " + base64.b64encode(user+':'+password)

    auth_header = 'Authorization'
    if proxy:
        auth_header = 'Proxy-Authorization'
    headers = { auth_header : auth }
    headers['Host'] = hostport
    conn.request('GET',path,None,headers)
    resp = conn.getresponse()
    resp.read()
    if not resp.status<400:
        print "Failed authentication for HTTP request", resp.status, resp.reason
        return False
    return True

def ntlm_request(url, user, password, domain, proxy):

    headers = {}

    if not url.startswith('http'):
        url = '//' + url
    (scheme, hostport, path, params, query, frag ) = urlparse.urlparse(url)
    connect_hostport = hostport
    authenticate_header = 'WWW-Authenticate'
    auth_header = 'Authorization'

    if proxy:
        if not url.startswith('http'):
            url = '//' + url
        (proxy_scheme, proxy_hostport, proxy_path, proxy_params,
                proxy_query, proxy_frag ) = urlparse.urlparse(proxy)
        connect_hostport = proxy_hostport
        auth_header = 'Proxy-Authorization'
        authenticate_header = 'proxy-authenticate'

    conn = httplib.HTTPConnection(connect_hostport)

    headers['Host'] = hostport
    conn.request('GET',path,None,headers)
    resp = conn.getresponse()
    resp.read()
    if resp.status<400:
        return 'Authorization' in headers
    elif resp.status not in (401, 407):
        print "Error in HTTP request", resp.status, resp.reason
        return False

    if 'ntlm' not in resp.getheader(authenticate_header).lower():
        print "NTLM Authentication is not supported"
        return False
    conn.close()

    # Process 401/407
    conn = httplib.HTTPConnection(connect_hostport)
    client = NTLM_Client(user, domain, password)

    type1 = client.make_ntlm_negotiate()
    auth = "NTLM " + base64.b64encode(type1)

    headers = {
            auth_header : auth,
            'Host': hostport }
    conn.request('GET',path,None,headers)
    resp = conn.getresponse()
    resp.read()
    if resp.status not in (401, 407):
        print "First round NTLM authentication for HTTP request failed", resp.status, resp.reason
        return False

    # Extract Type2, respond to challenge
    type2 = base64.b64decode(resp.getheader(authenticate_header).split(' ')[1])
    client.parse_ntlm_challenge(type2)
    type3 = client.make_ntlm_authenticate()

    auth = "NTLM " + base64.b64encode(type3)
    headers = { auth_header : auth,
            'Host': hostport }
    conn.request('GET',path,None,headers)
    resp = conn.getresponse()
    resp.read()
    if resp.status>=400:
        print "Second round NTLM authentication for HTTP request failed", resp.status, resp.reason
        return False

    return True

if __name__ == '__main__':
    config = dict()

    if len(sys.argv)<2:
        print_help()

    try:
        options, remain = getopt.getopt(sys.argv[1:],'hu:p:d:P:',['help',
            'user=', 'password=', 'domain=', 'proxy='])
    except getopt.GetoptError, err:
        print err.msg
        print_help()
    if not remain or len(remain)!=1:
        print "You must provide only one URL."
        print_help()
    else:
        url = remain[0]

    for o, v in options: 
        if o in ['-h', '--help']:
            print_help()
        elif o in ['-u', '--user']:
            config['user'] = v
        elif o in ['-p', '--password']:
            config['password'] = v
        elif o in ['-d', '--domain']:
            config['domain'] = v
        elif o in ['-P', '--proxy']:
            config['proxy'] = v

    if 'user' in config and 'password' in config and 'domain' not in config:
        config['scheme']='Basic'
    elif 'user' in config and 'password' in config and 'domain' in config:
        config['scheme']='NTLM'
    else:
        print "Incorrect number of options specified."
        print_help()

    try:
        success = True
        if config['scheme']=='Basic':
            success &= basic_request(url, config['user'],
                    config['password'], config['proxy'])
        else:
            success &= ntlm_request(url, config['user'], config['password'],
                    config['domain'], config['proxy'])
        if success:
            print "OK"
        else:
            print "Authentication failed"

    except IOError, e:
        print e

