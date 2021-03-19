SMTPc
=====

[![smtpc version](https://img.shields.io/pypi/v/smtpc.svg)](https://pypi.python.org/pypi/smtpc)
[![smtpc license](https://img.shields.io/pypi/l/smtpc.svg)](https://pypi.python.org/pypi/smtpc)
[![smtpc python compatibility](https://img.shields.io/pypi/pyversions/smtpc.svg)](https://pypi.python.org/pypi/smtpc)
[![say thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/marcin%40urzenia.net)

SMTPc is simple SMTP client for easy mail sending from CLI. It's dedicated
for developers, however it's easy to use and every CLI user will be satisfied
using this.

Main purpose of SMTPc is to help developers test and/or verify SMTP servers or
their SMTP configuration. But of course it can be used in every place you want
to automate any system, and use predefined messages (with templates) for
notifications, like daemons or crons.

If you like this tool, just [say thanks](https://saythanks.io/to/marcin%40urzenia.net).

Current stable version
----------------------

0.6.0

Features
--------

* Predefined profiles for using with many SMTP servers
* Predefined messages for sending messages just by the name
* Automatically build message from given parameters, do not glue headers manually
* Templating system using Jinja2 module for customizing messages
* Of course, handling authorization, SSL and TLS connections
* You can easily spoof your own messages, by specifying other sender/recipient in
  message headers, and other one for SMTP session
* Easily add own email headers
* If you have multiple IP addresses available, choose which one you want to use
* It's all Python!

Installation
------------

`SMTPc` should work on any POSIX platform where [Python](http://python.org)
is available, it means Linux, macOS/OSX etc.

Simplest way is to use Python's built-in package system:

    python3 -m pip install smtpc[extended]

It will install SMTPc and related packages for best user experience. If you want
to install simplest version without additions, then start with:

    python3 -m pip install smtpc

You can also use [pipx](https://pipxproject.github.io/pipx/) if you don't want to
mess with system packages and install `SMTPc` in virtual environment:

    pipx install smtpc

Voila!

Python version
--------------

`SMTPc` is tested against Python 3.7+. Older Python versions may work, or may not.

How to use
----------

First, add some account you want to use for sending. In this example we are using
[Sendria](https://github.com/msztolcman/sendria) run on local environment:

```bash
smtpc profiles add sendria --host 127.0.0.1 --port 1025
```

You can verify:
```bash
smtpc profiles list
```

Now, add few messages for future use:

```bash
smtpc messages add plain --subject 'Some plain email' --body-plain 'Some plain message body' --from plain@smtpc.net --to receiver@smtpc.net
smtpc messages add html --subject 'Some html email' --body-html 'Some <b>HTML</b> message body' --from html@smtpc.net --to receiver@smtpc.net
smtpc messages add alternative --subject 'Some alternative email' --body-plain 'Some plain message body' --body-html 'Some <b>HTML</b> message body' --from alternative@smtpc.net --to receiver@smtpc.net
```

And verification:
```bash
smtpc messages list
```

Now, let send something:

```bash
smtpc send --profile sendria --message alternative
smtpc send --profile sendria --message plain --subject 'Changed subject for plain'
```
In second example above, we are using predefined message `plain`, but with changed subject.

Of course, if you don't want, you don't need to use predefined profiles and/or messages, you can pass them directly when sending:

```bash
smtpc send --host 127.0.0.1 --port 1025 --body-type html --subject 'Some html email' --body-html 'Some <b>HTML</b> message body' --from not-funny@smtpc.net --to receiver@smtpc.net
```

But it's not so funny :)

Also you can use your predefined messages as templates:

```bash
smtpc messages add template-test --subject 'Some templated email: {{ date }}' --body-plain 'Some templated email body: {{ uuid }}' --from templated@smtpc.net --to receiver@smtpc.net
smtpc send --profile sendria --message template-test --template-field "date=$(date)" --template-field "uuid=$(uuidgen)"
```

And received email subject may looks like:

```
Some templated email: Thu Mar 18 19:05:53 CET 2021
```

And the body:

```
Some templated email body: C21B7FF0-C6BC-47C9-B3AC-5554865487E4
```

If there is also available [Jinja2](https://jinja.palletsprojects.com) module,
you can also use it as templating engine!
See more in [Templating chapter](#Templating).

Templating
----------

Templating can be realized in simple and extended form. In simplest case, when
[Jinja2](https://jinja.palletsprojects.com) module is not found, SMTPc can only
substitute some placeholders with any data. For example, if you will specify
subject as:
```
--subject "Now we have {{ date }}"
```

and when sending:

```angular2html
--template-field "date=$(date +"%Y-%m-%dT%H:%M:%S%Z")"
```

And email will look like:

```
Now we have 2021-03-19T10:56:31CET
```

But it can't handle conditions, loops and any other complicated and convenient example.

If you need some more, you need to install [Jinja2](https://jinja.palletsprojects.com)
module (more: [Installation](#Installation)).
Now, you have the full power of one of best templating engines Python has. Here you have an example:

```bash
smtpc messages add template-test --subject 'Some of my projects, state on {{ date }}' --from templated@smtpc.net --to receiver@smtpc.net --body-html '<p>Here I am!</p>
{% if projects %}
<p>Some of my projects:</p>
<ul>
{% for project in projects %}
    <li><a href="https://github.com/msztolcman/{{ project }}">{{ project }}</a></li>
{% endfor %}
</ul>
{% else %}
<p>I have no projects to show :(</p>
{% endif %}
<p>That&#39;s all folks!</p>'
smtpc send --profile sendria --message template-test --template-field "date=$(date -u +'%Y-%m-%dT%H:%M:%S%Z')" --template-field-json='projects=["sendria", "smtpc", "versionner", "ff"]'
```

And you will receive an email with subject:

```
Some of my projects, state on 2021-03-19T10:03:56UTC
```

And body (slightly reformatted here):

```html
<p>Here I am!</p>
<p>Some of my projects:</p>
<ul>
    <li><a href="https://github.com/msztolcman/sendria">sendria</a></li>
    <li><a href="https://github.com/msztolcman/smtpc">smtpc</a></li>
    <li><a href="https://github.com/msztolcman/versionner">versionner</a></li>
    <li><a href="https://github.com/msztolcman/ff">ff</a></li>
</ul>
<p>That&#39;s all folks!</p>
```

Please read more about Jinja2 capabilities on [Jinja2 homepage](https://jinja.palletsprojects.com).

Authors
-------

* Marcin Sztolcman ([marcin@urzenia.net](mailto:marcin@urzenia.net))

Contact
-------

If you like or dislike this software, please do not hesitate to tell me about
this me via email ([marcin@urzenia.net](mailto:marcin@urzenia.net)).

If you find bug or have an idea to enhance this tool, please use GitHub's
[issues](https://github.com/msztolcman/smtpc/issues).

ChangeLog
---------

### v0.6.0

* added `--template-field` and `--template-field-json` params for `send` command,
  allows to replace some `{{ fields }}` in email body or subject with specified
  values. Or you can also use [Jinja2](https://jinja.palletsprojects.com) if
  module is installed

### v0.5.0

* safe writing config files: will show file content if writing will fail
* messages list is simplified by default (just message name like in profiles list)
* new commands: `smtpc profiles delete`, `smtpc messages delete` - self explanatory I guess :)
* few minor bugs squashed
* few internal changes and improvements

### v0.4.1

* fixed handling --ssl and --tls when sending message using profile
* added simple --dry-run option
* added --reply-to option
* minor fixes to error handling
* added User-Agent header to generated messages

### v0.4.0

* BC: renamed command: `profile` -> `profiles`
* added new command: `messages` for managing of saved email messages
* allow overwriting profile or message predefined options from CLI arguments
* cleaner and more elegant code

### v0.3.0

* using commands now instead of dozens of CLI arguments

### v0.2.0

* added profiles

### v0.1.1

* fixed --version

### v0.1.0

* very initial version
