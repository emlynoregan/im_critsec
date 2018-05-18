import logging

from flask import Flask, redirect
from im_task_flask import setuptasksforflask
from im_futuretest import register_test
from im_futuretest_flask import register_futuretest_handlers, _create_route
from im_critsec import critsec
from im_future import GetFutureAndCheckReady, FutureReadyForResult
from im_task import PermanentTaskFailure

app = Flask(__name__)

setuptasksforflask(app)
register_futuretest_handlers(app)

@app.route("/", methods=["GET"])
def root():
    print "Here!" 
    return redirect(_create_route("ui/"), 301)

@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', 500



import time
from google.appengine.api import memcache

@register_test
def CallOnce(futurekey):
    
    @critsec
    def completion():
        fut = GetFutureAndCheckReady(futurekey)
        fut.set_success("called completion")
        
    completion()
        
    raise FutureReadyForResult("waiting")        

def _get_memcount(aMemcacheClient, aKey):
    return aMemcacheClient.gets(aKey)

def _set_memcount(aMemcacheClient, aKey, aValue):
    lretries = 20
    lsuccess = False
    while lretries:
        lvalue = _get_memcount(aMemcacheClient, aKey)
        if lvalue is None:
            lsuccess = aMemcacheClient.add(aKey, aValue)
        else:
            lsuccess = aMemcacheClient.cas(aKey, aValue)
        if lsuccess:
            break
        else:
            lretries -= 1
    if not lsuccess:
        raise Exception("Can't set memcount to %s (tests)" % aValue)

@register_test
def CallTwice(futurekey):
    @critsec
    def completion():
        lmemcacheClient2 = memcache.Client()
        try:
            lreentry = _get_memcount(lmemcacheClient1, "reentry")
            logging.info("reentry=%s" % lreentry)
            if (lreentry or 0) > 0:
                raise PermanentTaskFailure("Reentry == %s, should be 0" % lreentry)
            _set_memcount(lmemcacheClient2, "reentry", 1)

            time.sleep(2)
            lnumCalls = _get_memcount(lmemcacheClient1, "numcalls")
            lnumCalls = (lnumCalls or 0) + 1
            logging.info("lnumCalls=%s" % lnumCalls)
            if lnumCalls == 2:
                fut = GetFutureAndCheckReady(futurekey)
                fut.set_success("called completion twice")

            _set_memcount(lmemcacheClient1, "numcalls", lnumCalls)
        finally:
            _set_memcount(lmemcacheClient2, "reentry", 0)

    lmemcacheClient1 = memcache.Client()
    _set_memcount(lmemcacheClient1, "numcalls", 0)
    _set_memcount(lmemcacheClient1, "rentry", 0)
    completion()
    completion()
        
    raise FutureReadyForResult("waiting")        

@register_test
def CallOneHundredTimes(futurekey):
    @critsec
    def completion():
        lmemcacheClient2 = memcache.Client()
        try:
            lreentry = _get_memcount(lmemcacheClient1, "reentry")
            logging.info("reentry=%s" % lreentry)
            if (lreentry or 0) > 0:
                raise PermanentTaskFailure("Reentry == %s, should be 0" % lreentry)
            _set_memcount(lmemcacheClient2, "reentry", 1)

            time.sleep(5)
            lnumCalls = _get_memcount(lmemcacheClient1, "numcalls")
            lnumCalls = (lnumCalls or 0) + 1
            logging.info("lnumCalls=%s" % lnumCalls)
            if lnumCalls == 2:
                fut = GetFutureAndCheckReady(futurekey)
                fut.set_success("called completion twice")
            if lnumCalls > 2:
                raise PermanentTaskFailure("Called too many times (%s)" % lnumCalls)

            _set_memcount(lmemcacheClient1, "numcalls", lnumCalls)
        finally:
            _set_memcount(lmemcacheClient2, "reentry", 0)

    lmemcacheClient1 = memcache.Client()
    _set_memcount(lmemcacheClient1, "numcalls", 0)
    _set_memcount(lmemcacheClient1, "rentry", 0)
    for _ in range(100):
        completion()
        
    raise FutureReadyForResult("waiting")        

@register_test
def CallOneHundredTimesWithNoRerun(futurekey):
    @critsec(rerun_on_skip=False)
    def completion():
        lmemcacheClient2 = memcache.Client()
        try:
            lreentry = _get_memcount(lmemcacheClient1, "reentry")
            logging.info("reentry=%s" % lreentry)
            if (lreentry or 0) > 0:
                raise PermanentTaskFailure("Reentry == %s, should be 0" % lreentry)
            _set_memcount(lmemcacheClient2, "reentry", 1)

            time.sleep(5)
            lnumCalls = _get_memcount(lmemcacheClient1, "numcalls")
            lnumCalls = (lnumCalls or 0) + 1
            logging.info("lnumCalls=%s" % lnumCalls)

            if lnumCalls == 1:
                fut = GetFutureAndCheckReady(futurekey)
                fut.set_success("called completion once")
            if lnumCalls > 1:
                raise PermanentTaskFailure("Called too many times (%s)" % lnumCalls)

            _set_memcount(lmemcacheClient1, "numcalls", lnumCalls)
        finally:
            _set_memcount(lmemcacheClient2, "reentry", 0)

    lmemcacheClient1 = memcache.Client()
    _set_memcount(lmemcacheClient1, "numcalls", 0)
    _set_memcount(lmemcacheClient1, "rentry", 0)
    for _ in range(100):
        completion()
        
    raise FutureReadyForResult("waiting")        

