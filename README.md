# im_critsec

This library contains the decorator @critsec, for running a function as a critical section (non-reentrant task).

[![Build Status](https://travis-ci.org/emlynoregan/im_critsec.svg?branch=master)](https://travis-ci.org/emlynoregan/im_critsec)

## Install 

Use the python package for this library. You can find the package online [here](https://pypi.org/project/im-critsec/).

Change to your Python App Engine project's root folder and do the following:

> pip install im_critsec --target lib

Or add it to your requirements.txt. You'll also need to set up vendoring, see [app engine vendoring instructions here](https://cloud.google.com/appengine/docs/python/tools/using-libraries-python-27).

## Usage

You'll need to have im_task set up correctly using either im_task_flask or im_task_webapp (or both!) depending on which framework you are using.

Then, you can run a function as a critical section as follows:

    @critsec
    def MyCriticalFunc():
      # do some stuff that needs to not be interrupted
      # this function will *never* run re-entrantly, even in other processes on other computers

    MyCriticalFunc() # kicking off the call to it here.

Critsec forms a separate critical section for each combination of arguments and outer scope references. eg:

    @critsec
    def MyCriticalFunc(value):
      # do some stuff that needs to not be interrupted
      # this function will *never* run re-entrantly, even in other processes on other computers

    MyCriticalFunc(1) # first call
    MyCriticalFunc(1) # in same critical section as first call
    MyCriticalFunc(2) # in a different critical section

## rerun_on_skip

When a critical section is entered, subsequent calls to the same critical section will be ignored while that critical section is running. However, those skipped calls are remembered. Once the critical section is finished, if any calls were skipped, then the critical section runs one more time. This is called rerun_on_skip.

If you would prefer not to have rerun_on_skip, you can turn it off:

    @critsec(rerun_on_skip = False)
    def ThisFunctionIsNotRerunOnSkip(value):
      # do a thing 

## @critsec is a form of @task

@critsec is exactly like @task; you can pass in task arguments, eg:

    @critsec(queue = "myqueue")
    def ThisFunctionRunsOnMyQueue():
      # do a thing 
