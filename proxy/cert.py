#!/usr/bin/env python3

import os
from subprocess import Popen, PIPE
import ssl
import threading

cwd = os.path.dirname(__file__)


class CertificateHelper:
    certdir = f'{cwd}/certs/'
    cakey = f'{cwd}/certs/root.ca.key'
    cacert = f'{cwd}/certs/root.ca.pem'
    certkey = f'{cwd}/certs/private.key'
    lock = threading.Lock()

    @classmethod
    def generate_cert(cls, hostname):
        certpath = "%s/%s.crt" % (cls.certdir.rstrip('/'), hostname)
        if os.path.exists(certpath):
            return certpath
        cnfpath = "%s/%s.cnf" % (cls.certdir.rstrip('/'), hostname)
        with open(cnfpath, 'w') as f:
            content = 'subjectAltName=DNS:%s' % hostname
            f.write(content)
        p1 = Popen(["openssl", "req", "-new", "-key", cls.certkey,
                    "-subj", "/CN=%s" % hostname], stdout=PIPE)
        cmd = ('openssl x509 -req -days 365 -CA %s'
               ' -CAkey %s -CAcreateserial'
               ' -sha256 -extfile %s -out %s') % (
                   cls.cacert, cls.cakey, cnfpath, certpath)
        p2 = Popen(cmd, stdin=p1.stdout, stderr=PIPE, shell=True)
        outs, errs = p2.communicate()
        return certpath
