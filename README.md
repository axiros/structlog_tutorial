---

Note: README for https://github.com/axiros/structlog_tutorial
Author: gk

---


# Structlog Mechanics

So, you spent your programmer live, logging with strings in mind?  

- Merged your precious [values][values] in the process into prosa, by doing things like: `.info("%s users logged in", total)`? 

- Thought a lot about how to *build* them but not about how to *parse* that prosa and felt senior, whenever you did drop the 's' in users if `total < 2` and (worse) changed the type of that value into a "No" for `total == 0`?

- Committed such "improvements" even for the next minor - and after the update customer ops wondered every morning why their home grown counter creation scripts failed yet again to deliver values during runs in non business hours?

- You found that adding context data into those soups of values and english text by simply modifying format strings elegant - and to get that you were ok with the logging system having to provide *any possibly wanted* value within "[LogRecords][logrec]" and their "extra" dicts before?

- And also you thought, spamming *all* that data into `json` is ok, in order to cope with the requirements of the age of data processing pipelines?

- Improving measures where reduced to adding yet more to the already existing plethora of formatters and handlers?

Did you never miss logging like

```python
log.info('UserCount', total=len(users)) 
```
- Where the string is now an event type i.e. yet a new precious value, which can e.g. be rated per hour by a counting system(...)

- And where only such *additional* meta data is added by the logging subsystem, which you declared to want - from global app config - down to function or threadlocal context?  


**Well, then [this][structlogdoc] is for you.**


We spare you of [further][bashingchris] stdlogging [bashing][bashing1] / structlog motivation but try to give you a headstart in *really* understanding *subsequent* readings about **structlog**. 

If you still lack motivation, maybe check [here][falcon] first. 

And [here][talk] is a talk about structlog from the [author][hynek], a Twisted and [CPython][cpython] committer, who works for a hosting provider (the talk is a great, also regarding other invaluable tools for building systems, like sentry).


## Preparation: Tutorial Setup

The tutorial module in its various phases are committed to git and then `show_run` is invoked:

```bash
$ cat show_run
#!/usr/bin/env bash

mode="$1"
# git diff to last one:
test "$mode"!="d" && cat tutorial || git diff

echo "Resulting Terminal Output:"
./tutorial
```
Enough for this tutorial. If you want the full source for copy and paste instead of the diffs shown, than go back in the commit history, within [this][gh] repo.

[gh]: https://github.com/axiros/structlog_tutorial/


## Make A Logger

We start from the end: **outputting** - done by so called 'Loggers'.
This is the last step of calling a log message, involving a function 
- usually sending a bunch of bytes to the world outside our process, e.g. to a file descriptor like `stdout`
- usually but not [always][returnlogger] causing a side effect.

This is such a logger:

```python
$ ./show_run
#!/usr/bin/env python

class PrintLogger(object):
    def msg(self, msg, *a, **kw):
        print('test:' + msg + str(kw))

PrintLogger().msg('hi')

Resulting Terminal Output:
test:hi{}
$
```
> Free your mind from the preconception that log entries *have* to be serialized to strings eventually. All structlog cares about is a dictionary of keys and values. What happens to it depends on the logger you wrap and your processors alone, see below. This gives you the power to log *directly* to databases, log aggregation servers, web services, and what not.

> *If* the log result is text, than also note that there is not a SINGLE reason why you would merge a value at hand into a plain english format string!
> Wrong: "Have 10 logged in users and 20 sessions"
> Right: "**Session count**: total: **20**, logged_in: **10**   
> and the latter, event type + kv based one, is allowing to later dig for times with max sessions and so on.


[returnlogger]: http://www.structlog.org/en/stable/_modules/structlog/_loggers.html#ReturnLogger

## Make The Logger Configurable

```python
$ ./show_run
#!/usr/bin/env python

class PrintLogger(object):
    def __init__(self, **cfg):
        self.cfg = cfg

    def msg(self, msg, *a, **kw):
        pref = self.cfg.get('prefix', 'test: ')
        print(' '.join((pref, msg, str(kw))))

log = PrintLogger(prefix='my prefix')
log.msg('hi')

Resulting Terminal Output:
my prefix hi {}
$
```
Now add structlog on top of that.

## Insert A Processor Chain

Between the log invokation and the side effect we want to insert a chain of processors, making the output a bit more sophisticated. 

E.g.

```flow  (requires flowchart js to get rendered)
st=>start: log.msg('hi')
op1=>operation: create dict like context from event
op2=>operation: add_timestamp
op3=>operation: context to colorized string
e=>end: call log.msg(processed msg)

st->op1->op2->op3->e
```


We could do that by providing a function like `wrap_logger`, which accepts our PrintLogger with config and processors chain - and returns a wrapped logger, where the wrapper has something like a `__getattr__` based adapter, passing the args through configured processors first, before invoking the output function (here `msg`).


Structlog provides both:
- The [BoundLogger][slbound] with its base class, invoking the configured processor chain [here][bbase_procs] - before calling the logger method with the result of the last processor.
- And the [wrap_logger][wrap] function to get back such a bound logger (ignore the lazyproxy and the other variables except processors for now in the [source][wrap]

> Squeezing in the processor chain invokatation at gettatr time of log.msg is "magic" - in a bad sense. Though supported in structlog (as the one and only "magic" mechanic) they provide a [better way][custom_wrapper] - which you'll fully understand after this tutorial, not relevant at this point.


[custom_wrapper]:http://www.structlog.org/en/stable/custom-wrappers.html
[slbound]: http://www.structlog.org/en/stable/_modules/structlog/_generic.html#BoundLogger
[bbase_procs]: http://www.structlog.org/en/stable/_modules/structlog/_base.html#BoundLoggerBase._proxy_to_logger
[wrap]:http://www.structlog.org/en/stable/_modules/structlog/_config.html#wrap_logger

If we do NOT provide processors then the default ones are taken, and those are *basically* the ones shown in the example:

```diff
$ ./show_run d
diff --git a/tutorial b/tutorial

+import structlog

 class PrintLogger(object):

-log = PrintLogger(prefix='my prefix')
-log.msg('hi')
+log = structlog.wrap_logger(PrintLogger(prefix='my prefix'))
+log.msg('hi', key='value')
```
and here is a shot of the output:  
![colored terminal output with timestamp](https://axc2.axiros.com/maxmd/uploads/upload_f8ca5b6cc3d7a6a3b47b84300d1c37c3.png)
The padding of the message string is a config option of the processor which creates the output string.

## Processors

Lets see how they work in detail.  
Completely removing the default processors and building our own chain:

```diff
$ ./show_run d
diff --git a/tutorial b/tutorial
-import structlog
+import structlog, time
+
+def proc1(*a):
+    print('processor args of structlog:', ' '.join(str(s) for s in a))
+    ev_dict = a[2]
+    ev_dict['our_timestamp'] = time.ctime()
+    return ev_dict
+
+def proc2(Logger, meth_name, ev_dict):
+    # Last processor must match Logger method sig:
+    return '%(our_timestamp)s %(event)s processed result' % ev_dict

 
-log = structlog.wrap_logger(PrintLogger(prefix='my prefix'))
+pl = PrintLogger(prefix='my prefix')
+log = structlog.wrap_logger(pl, processors=[proc1, proc2])
 log.msg('hi', key='value')

Resulting Terminal Output:
('processor args of structlog:', "<__main__.PrintLogger object at 0x7f5c3ec99dd0> msg OrderedDict([('key', 'value'), ('event', 'hi')])")
my prefix Sat Sep  1 12:30:21 2018 hi processed result {}
```

Lesson: structlog processors signature is fix:
 - Logger
 - methodname
 - ev_dict


Question: Why not force the output function to follow that simple rule, so that we can avoid the requirement that the last processor has to produce sig matching output? 
Answer: [DRY][dry]: In the example flow above, there is this last processor making a string from the event_dict. You do not want to have to do that in the outputter, since that might involve tasks, which other outputters also need to have done, e.g. ordering of keys, before colorizing.

> In most use cases you could call that last processor 'Renderer' - to whatever, incl. strings.

> Yes, structlog does [contain][logkw] a renderer to [stdlib][logging] compliant formatters.

[dry]: https://en.wikipedia.org/wiki/Don%27t_repeat_yourself
[logkw]: http://www.structlog.org/en/stable/_modules/structlog/stdlib.html#render_to_log_kwargs
[logging]: https://docs.python.org/3/library/logging.html#module-logging



### Configurable Processors

> This is for Python beginners, the technique shown here is not for structlog only.

Simply add a processors holding config to the chain.
- For simple functions use [`partial`][partial]
 
or
- Pass a configured object with a `__call__` method

[partial]: https://pymotw.com/2/functools/

```diff
$ ./show_run d

-def proc2(Logger, meth_name, ev_dict):
+def proc2(Logger, meth_name, ev_dict, **cfg):
     # Last processor must match Logger method sig:
+    # we are the 'renderer', no ev_dict after us anyway:
+    ev_dict.update(cfg)
     return '%(our_timestamp)s %(event)s [%(msg)s]' % ev_dict
        
pl = PrintLogger(prefix='my prefix')
+ proc2 = partial(proc2, msg='custom messge')
log = structlog.wrap_logger(pl, processors=[proc1, proc2])
log.msg('hi', key='value')

Resulting Terminal Output:
my prefix Sat Sep  1 16:31:40 2018 hi [custom messge]
```

## Performance

It should be not overstated but also not ignored, that structlog's supertransparent design ('just enough logging') compared to stdlib's 'batteries in - and NOT removable' design performs well better:

Example: Comparing raw performance [[test setup][ghperf]]

```
stdlib log
0.2720661163330078
stdlib log
1.9453916549682617
```


[ghperf]:https://github.com/axiros/structlog_tutorial/blob/master/perf.py


## (Deferring) Configuration: `get_logger`

When the application starts up, tons of modules acquiring a logger at import time. How do they know about their config, e.g. processors - we often did not even read any config file?

Here is how:

Structlog assigns the *default* processors initially to loggers which are made with `.get_logger` and not `wrap_logger` - until **`structlog.configure`** call:

`.configure` has basically the effect to change the defaults of

- `processors` (default: see example flow)
- `logger_factory` (default: [PrintLogger][prl] )
- `initial_values` (default: {})
- `context_class`  (default: `dict`)


You can
- configure incrementally (e.g. first `processors`, later more )
- run `configure` more often
- `.bind(**kw)` configured loggers, to prevent them from changing behaviour, after later `configure` runs.



## Immutable Loggers / Mutable Context

Lastly we explain why `context_class` in the config options is a key ingredient to getting the powers of structlog:

When you say

```python
log = log.bind(req="req_id")
```

- the old context is shallow copied and the key added. So you'll find it for (only) that (wrapped) logger from now on. 

- You can do this *incrementally* and that is why `OrderedDict` as default context holding class for Python versions [below 3.6][guido] makes sense, to keep multi step context additions in order - and there is a more performant [alternative][ordering] as well. 

[ordering]:http://www.structlog.org/en/stable/performance.html

- You can also [declare][tll], that the context class should be thread/greenlet local. By this you keep immutable i.e. cacheable loggers - but with [thread local context values][tllflask]

[guido]:https://mail.python.org/pipermail/python-dev/2017-December/151283.html
----

And that is all there is to know for the base mechanics - you'll have now an easy time understanding the well crafted [documentation][structlogdoc] system of `structlog`, which you should now have a look at.  

It explains in great detail the integration with stdlib logging for example , should you still want parts of that ;-)

---

[talk]:https://hynek.me/talks/beyond-grep/
[structlogdoc]:http://www.structlog.org/en/stable/

[bashingchris]:https://twitter.com/chrismcdonough/status/280251086609203200
[bashing1]:[https://news.ycombinator.com/item?id=4331848]

[hynek]: https://hynek.me/about/
[cpython]:https://hynek.me/articles/my-road-to-the-python-commit-bit/
[logrec]:https://github.com/python/cpython/blob/2d7102e726e973ab2d307aa9748c7ec433677877/Lib/logging/__init__.py#L228
[values]:https://www.youtube.com/watch?v=-6BsiVyC1kM
[falcon]:http://stevetarver.github.io/2017/05/10/python-falcon-logging.html

[tll]:http://www.structlog.org/en/stable/thread-local.html
[tllflask]: http://www.structlog.org/en/stable/examples.html#flask-example


[prl]:http://www.structlog.org/en/stable/_modules/structlog/_loggers.html?highlight=PrintLogger




