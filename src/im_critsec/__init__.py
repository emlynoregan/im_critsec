from google.appengine.api import memcache
from datetime import datetime, timedelta
from im_task import task, RetryTaskException, PermanentTaskFailure
import functools
from im_util import make_flash, get_utcnow_unixtimestampusec
from google.appengine.ext import ndb
import logging
# from im_debouncedtask import debouncedtask

_EXCLUDE_FROM_FLASH = "__x__"

class _CritSecLock(ndb.model.Model):
    updated = ndb.DateTimeProperty(auto_now=True)
    locked = ndb.BooleanProperty()
    skip = ndb.BooleanProperty()
    
    @classmethod
    def ConstructKey(cls, f, *args, **kwargs):
        if _EXCLUDE_FROM_FLASH in kwargs:
            lflashKwargs = dict(kwargs)
            del lflashKwargs[_EXCLUDE_FROM_FLASH]
        else:
            lflashKwargs = kwargs
        lflash = make_flash(f, "_DebouncedCritSecLock", *args, **lflashKwargs)
        return ndb.Key(_CritSecLock, lflash)
    
    @classmethod
    def GetOrCreate(cls, aKey):
        llock = aKey.get()
        if not llock:
            llock = _CritSecLock(locked=False, skip=False, key=aKey)
        return llock
    
# def DeleteSomeOldLocks(aAmount=1000):
#     ltwentyFourHoursAgo = datetime.utcnow() - timedelta(days=1)
#     lkeysToDelete = list(_CritSecLock.query(_CritSecLock.updated < ltwentyFourHoursAgo).fetch(aAmount, keys_only=True))
#     ndb.delete_multi(lkeysToDelete)
#     return len(lkeysToDelete) == aAmount
    
def _get_memskip(aMemcacheClient, aLockKey):
    return aMemcacheClient.gets(aLockKey.id())

def _set_memskip_to_0_or_raise(aMemcacheClient, aLockKey):
    lretries = 20
    lsuccess = False
    while lretries:
        lcurrentMemskip = _get_memskip(aMemcacheClient, aLockKey)
        if lcurrentMemskip is None:
            lsuccess = aMemcacheClient.add(aLockKey.id(), 0)
        else:
            lsuccess = aMemcacheClient.cas(aLockKey.id(), 0)
        if lsuccess:
            break
        else:
            lretries -= 1
    if not lsuccess:
        raise Exception("Can't set memskip to 0 (debouncedcritsec)")

def _set_memskip_to_1_or_raise(aMemcacheClient, aLockKey):
    lretries = 20
    lsuccess = False
    while lretries:
        lcurrentMemskip = _get_memskip(aMemcacheClient, aLockKey)
        if lcurrentMemskip is None:
            lsuccess = aMemcacheClient.add(aLockKey.id(), 1)
        elif lcurrentMemskip == 0:
            lsuccess = aMemcacheClient.cas(aLockKey.id(), 1)
        else:
            lsuccess = True
        if lsuccess:
            break
        else:
            lretries -= 1
    if not lsuccess:
        raise Exception("Can't set memskip to 1 (debouncedcritsec)")

def _set_memskip_to_2_if_possible(aMemcacheClient, aLockKey):
    lretries = 20
    lsuccess = False
    while lretries:
        lcurrentMemskip = _get_memskip(aMemcacheClient, aLockKey)
        if lcurrentMemskip == 1:
            lsuccess = aMemcacheClient.cas(aLockKey.id(), 2)
        else:
            lsuccess = True
        if lsuccess:
            break
        else:
            lretries -= 1
    # if failed, just exit quietly, same as success

def critsec(f = None, rerun_on_skip=True, **taskkwargs):
    if not f:
        return functools.partial(
            critsec, 
            rerun_on_skip=rerun_on_skip, 
            **taskkwargs
        )
    
    @functools.wraps(f)
    def runf(*args, **kwargs):
        llockKey = _CritSecLock.ConstructKey(f, *args, **kwargs)
            
        @task(**taskkwargs)
        def acquiretask():
            lmemcacheClient1 = memcache.Client()
            lmemSkip = _get_memskip(lmemcacheClient1, llockKey)
            
            if lmemSkip is None or lmemSkip < 2:
                ltaskkwargsCopy = dict(taskkwargs)
                ltaskkwargsCopy["transactional"] = True

                @task(**taskkwargs)
                def releasetask():
                    @ndb.transactional
                    def release():
                        llock = _CritSecLock.GetOrCreate(llockKey)
                    
                        lskipped = llock.skip

                        llock.key.delete()                        
                        
                        lmemcacheClient4 = memcache.Client()
                        # will rollback transaction if fails to set
                        # can accidentally set to 0 but transaction rolls back, that's ok.
                        _set_memskip_to_0_or_raise(lmemcacheClient4, llockKey)
                        
                        return lskipped
                        
                    lskipped = release()

                    if lskipped and rerun_on_skip:
                        # we're definitely released here, acquiretask() is safe to call multiple times
                        # ie: this doesn't require the transactional flag is set.
                        acquiretask()
                        
                @task(**ltaskkwargsCopy)
                def runFtask():
                    lmemcacheClient3 = memcache.Client()
                    _set_memskip_to_1_or_raise(lmemcacheClient3, llockKey)
                    try:
                        f(*args, **kwargs)
                    except RetryTaskException:
                        raise
                    except PermanentTaskFailure:
                        logging.exception("Permanent Task Failure in %s" % f.__name__)
                    except Exception:
                        logging.exception("Exception in %s" % f.__name__)
                    
                    releasetask()
                
                @ndb.transactional
                def acquire():
                    llock = _CritSecLock.GetOrCreate(llockKey)
                    
                    if llock.locked and llock.skip:
                        pass # should skip here. Don't write!
                    else:
                        if not llock.locked:
                            llock.locked = True
                            llock.skip = False
                            runFtask() # transactional
                        else:
                            llock.skip = True
                        llock.put()
                    return llock.skip
                    
                lskip = acquire()
                
                if lskip:
                    lmemcacheClient2 = memcache.Client()
                    _set_memskip_to_2_if_possible(lmemcacheClient2, llockKey)
            
        acquiretask()
# 
#         CleanupLocks()

    return runf

# @debouncedtask(initsec=3600, repeatsec=3600)
# def CleanupLocks():
#     lmore = DeleteSomeOldLocks()
#     if lmore:
#         CleanupLocks()