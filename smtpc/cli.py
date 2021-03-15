import argparse
import logging
import smtplib
import sys
from email.mime.base import MIMEBase
from typing import Optional, List, Union

import structlog
import toml.decoder

from . import __version__
from .config import ensure_config_files, Profiles, Profile, PROFILES_FILE, Config, Messages, MESSAGES_FILE, Message
from .message import ContentType, build_message

logger = structlog.get_logger()
PROFILES: Optional[Profiles] = None
MESSAGES: Optional[Messages] = None
CONFIG: Optional[Config] = None


def parse_argv(argv):
    content_type_choices = [ContentType.PLAIN.value, ContentType.HTML.value]

    parser = argparse.ArgumentParser('SMTPc')
    parser.add_argument('--debug', '-D', action='count', default=0,
        help='Enable debug messages. Can be used multiple times to increase debug level.')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}',
        help='Display the version and exit')

    sub = parser.add_subparsers(dest='command')

    p_send = sub.add_parser('send', help="")
    p_send.add_argument('--profile', '-P', choices=PROFILES.keys(),
        help='Get set of connection details (--host, --port, --login, --password etc) from config file.')
    p_send.add_argument('--message', '-M', choices=MESSAGES.keys(),
        help='Get set of message details (--subject, --from, --to, --cc etc) from config file.')

    p_send.add_argument('--login', '-l', help='Login for SMTP authentication. Required if --password was given.')
    p_send.add_argument('--password', '-p',
        help='Password for SMTP authentication. Required if --login was given.')
    p_send.add_argument('--host', '-s', default='127.0.0.1',
        help='SMTP server. Can be also together with port, ie: 127.0.0.1:465.')
    p_send.add_argument('--port', '-o', type=int, help='Port for SMTP connection. Default: 25.')
    p_send.add_argument('--tls', action='store_true',
        help='Force upgrade connection to TLS. Default if --port is 587.')
    p_send.add_argument('--no-tls', action='store_true', help='Force disable TLS upgrade.')
    p_send.add_argument('--ssl', action='store_true', help='Force use SSL connection. Default if --port is 465.')
    p_send.add_argument('--no-ssl', action='store_true', help='Force disable SSL connection.')
    p_send.add_argument('--connection-timeout', type=int, default=30, help='')
    p_send.add_argument('--session-timeout', type=int, help='')
    p_send.add_argument('--identify-as', help='Domain used for SMTP identification in EHLO/HELO command.')
    p_send.add_argument('--source-address', help='Source IP address to use when connecting.')

    p_send.add_argument('--subject', '-j', help='Subject for email.')
    p_send.add_argument('--body', '-b',
        help='Body of email. Has less priority then --body-text and --body-html.')
    p_send.add_argument('--body-type', choices=content_type_choices, help='Typehint for email Content-Type. ')
    p_send.add_argument('--body-plain', help='Text part of the message for text/plain version.')
    p_send.add_argument('--body-html', help='Text part of the message for text/html version.')
    p_send.add_argument('--raw-body', action='store_true',
        help='Do not try to generate email body with headers, use content from --body as whole message body.')
    p_send.add_argument('--envelope-from', '-F',
        help='Sender address for SMTP session. If missing, then address from --from is used.')
    p_send.add_argument('--from', '-f', dest='address_from',
        help='Sender addres. Will be used for SMTP session if --envelope-from is missing.')
    p_send.add_argument('--envelope-to', '-T', action='append', default=[],
        help='Email recpients for SMTP session. Can be used multiple times. '
             'If used, then --to, -cc and --bcc are not used for SMTP session.')
    p_send.add_argument('--to', '-t', dest='address_to', action='append', default=[],
        help='Email recipients for To header. Used in SMTP session if --envelope-to is missing.')
    p_send.add_argument('--cc', '-c', dest='address_cc', action='append', default=[],
        help='Email recipients for Cc header. Used in SMTP session if --envelope-to is missing.')
    p_send.add_argument('--bcc', '-C', dest='address_bcc', action='append', default=[],
        help='Used in SMTP session if --envelope-to is missing. Will not be included in generated message.')
    p_send.add_argument('--header', '-H', dest='headers', action='append', default=[],
        help='Additional headers in format: HeaderName=HeaderValue. Can be used multiple times.')

    p_profiles = sub.add_parser('profiles', help="")
    p_profiles_sub = p_profiles.add_subparsers(dest='subcommand')

    p_profiles_edit = p_profiles_sub.add_parser('edit', help='')
    p_profiles_list = p_profiles_sub.add_parser('list', help='')
    p_profiles_add = p_profiles_sub.add_parser('add', help='')
    p_profiles_add.add_argument('name', nargs=1, help='')
    p_profiles_add.add_argument('--login', '-l', help='Login for SMTP authentication. Required if --password was given.')
    p_profiles_add.add_argument('--password', '-p', help='Password for SMTP authentication. Required if --login was given.')
    p_profiles_add.add_argument('--host', '-s', default='127.0.0.1',
        help='SMTP server. Can be also together with port, ie: 127.0.0.1:465.')
    p_profiles_add.add_argument('--port', '-o', type=int, help='Port for SMTP connection. Default: 25.')
    p_profiles_add.add_argument('--tls', action='store_true', help='Force upgrade connection to TLS. Default if --port is 587.')
    p_profiles_add.add_argument('--no-tls', action='store_true', help='Force disable TLS upgrade.')
    p_profiles_add.add_argument('--ssl', action='store_true', help='Force use SSL connection. Default if --port is 465.')
    p_profiles_add.add_argument('--no-ssl', action='store_true', help='Force disable SSL connection.')
    p_profiles_add.add_argument('--connection-timeout', type=int, default=30, help='')
    p_profiles_add.add_argument('--session-timeout', type=int, help='')
    p_profiles_add.add_argument('--identify-as', help='Domain used for SMTP identification in EHLO/HELO command.')
    p_profiles_add.add_argument('--source-address', help='Source IP address to use when connecting.')

    p_messages = sub.add_parser('messages', help='')
    p_messages_sub = p_messages.add_subparsers(dest='subcommand')

    p_messages_edit = p_messages_sub.add_parser('edit', help='')
    p_messages_list = p_messages_sub.add_parser('list', help='')
    p_messages_add = p_messages_sub.add_parser('add', help='')
    p_messages_add.add_argument('name', nargs=1, help='')
    p_messages_add.add_argument('--subject', '-j', help='Subject for email.')
    p_messages_add.add_argument('--body', '-b',
        help='Body of email. Has less priority then --body-text and --body-html.')
    p_messages_add.add_argument('--body-type', choices=content_type_choices, help='Typehint for email Content-Type. ')
    p_messages_add.add_argument('--body-plain', help='Text part of the message for text/plain version.')
    p_messages_add.add_argument('--body-html', help='Text part of the message for text/html version.')
    p_messages_add.add_argument('--raw-body', action='store_true',
        help='Do not try to generate email body with headers, use content from --body as whole message body.')
    p_messages_add.add_argument('--envelope-from', '-F',
        help='Sender address for SMTP session. If missing, then address from --from is used.')
    p_messages_add.add_argument('--from', '-f', dest='address_from',
        help='Sender addres. Will be used for SMTP session if --envelope-from is missing.')
    p_messages_add.add_argument('--envelope-to', '-T', action='append', default=[],
        help='Email recpients for SMTP session. Can be used multiple times. '
             'If used, then --to, -cc and --bcc are not used for SMTP session.')
    p_messages_add.add_argument('--to', '-t', dest='address_to', action='append', default=[],
        help='Email recipients for To header. Used in SMTP session if --envelope-to is missing.')
    p_messages_add.add_argument('--cc', '-c', dest='address_cc', action='append', default=[],
        help='Email recipients for Cc header. Used in SMTP session if --envelope-to is missing.')
    p_messages_add.add_argument('--bcc', '-C', dest='address_bcc', action='append', default=[],
        help='Used in SMTP session if --envelope-to is missing. Will not be included in generated message.')
    p_messages_add.add_argument('--header', '-H', dest='headers', action='append', default=[],
        help='Additional headers in format: HeaderName=HeaderValue. Can be used multiple times.')

    args = parser.parse_args(argv)

    def setup_connection_args(args):
        if args.tls and args.ssl:
            parser.error("Cannot use --ssl and --tls together")

        if args.host and args.host.startswith(('smtp://', 'smtps://')):
            args.host = args.host.replace('smtp://', '').replace('smtps://', '')

        if ':' in args.host:
            host, port = args.host.split(':', 1)
            args.host = host
            if not args.port:
                try:
                    args.port = int(port)
                except ValueError:
                    parser.error(f"SMTP port: invalid int value: {port}")

        if not args.port:
            args.port = 25

        if not args.ssl and not args.tls:
            if args.port == 465 and not args.no_ssl:
                args.ssl = True
            elif args.port == 587 and not args.no_tls:
                args.tls = True

        if (args.login and not args.password) or (not args.login and args.password):
            parser.error("Required both or none: --login, --password")

    def setup_message_args(args):
        if not getattr(args, 'message', False) and not args.envelope_from and not args.address_from:
            parser.error('Any from (--envelope-from or --from) required' + (
                ' if --message not specified' if not hasattr(args, 'message') else ''
            ))

        if not getattr(args, 'message', False) and not args.envelope_to and not args.address_to and not args.address_cc and not args.address_bcc:
            parser.error('Any from (--envelope-to,--to, --cc, --bcc) required' + (
                ' if --message not specified' if not hasattr(args, 'message') else ''
            ))

        if args.body_type in ('plain', 'html'):
            args.body_type = ContentType(args.body_type)
        elif args.body_plain and args.body_html:
            args.body_type = ContentType.ALTERNATIVE
        elif args.body_plain and not args.body_html:
            args.body_type = ContentType.PLAIN
        elif not args.body_plain and args.body_html:
            args.body_type = ContentType.HTML
        else:
            args.body_type = ContentType.PLAIN

        for header in args.headers:
            if '=' not in header:
                parser.error(f"Invalid header syntax: {header}. Required syntax: HeaderName=HeaderValue")

    if args.command == 'send':
        setup_connection_args(args)
        setup_message_args(args)

    elif args.command == 'profiles':
        if args.subcommand == 'add':
            setup_connection_args(args)
        elif not args.subcommand:
            p_profiles.print_help()
            sys.exit()
    elif args.command == 'messages':
        if args.subcommand == 'add':
            setup_message_args(args)
        elif not args.subcommand:
            p_messages.print_help()
            sys.exit()
    else:
        parser.print_help()
        sys.exit()

    return args


def configure_logger(debug_mode: bool = False):
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper("ISO"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug_mode else logging.WARNING),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def send_message(*,
    connection_timeout: int,
    source_address: Optional[str],
    debug_level: Optional[int],
    host: str,
    port: int,
    identify_as: Optional[str],
    tls: bool,
    ssl: bool,
    login: Optional[str],
    password: Optional[str],
    envelope_from: Optional[str],
    address_from: Optional[str],
    envelope_to: Optional[List[str]],
    address_to: Optional[List[str]],
    address_cc: Optional[List[str]],
    address_bcc: Optional[List[str]],
    message_body: Optional[Union[MIMEBase, str]],
    profile: Optional[Profile],
    message: Optional[Message],
):
    if profile:
        logger.debug('using connection details from predefined profile', profile=profile.name)
        login = profile.login
        password = profile.password
        host = profile.host
        port = profile.port
        ssl = profile.ssl
        tls = profile.tls
        connection_timeout = profile.connection_timeout
        identify_as = profile.identify_as
        source_address = profile.source_address

    if message:
        logger.debug('using message details from predefined message', message=message.name)
        envelope_from = message.envelope_from
        address_from = message.address_from
        envelope_to = message.envelope_to
        address_to = message.address_to
        address_cc = message.address_cc
        address_bcc = message.address_bcc

    if ssl:
        logger.debug('connecting using ssl', connection_timeout=connection_timeout,
            source_address=source_address)
        # don't pass host, don't want to connect yet!
        smtp = smtplib.SMTP_SSL(timeout=connection_timeout, source_address=source_address)
    else:
        logger.debug('connecting using plain connection', connection_timeout=connection_timeout,
            source_address=source_address)
        # don't pass host, don't want to connect yet!
        smtp = smtplib.SMTP(timeout=connection_timeout, source_address=source_address)

    if debug_level > 1:
        smtp.set_debuglevel(debug_level - 1)

    try:
        # HACK: connect doesn't set smtp._host, then ssl/tls will not work :/
        smtp._host = host
        smtp_code, smtp_message = smtp.connect(host, port, source_address=source_address)
        logger.debug('connected', host=host, port=port, source_address=source_address,
            smtp_code=smtp_code, smtp_message=smtp_message)
    except Exception as exc:
        logger.exception('connection error', host=host, port=port, exc=exc)
        raise exc

    smtp.ehlo(identify_as)

    if tls:
        logger.debug('upgrade connection to tls')
        smtp.starttls()

    if login and password:
        logger.debug('call login, will authorize when required', login=login)
        smtp.login(login, password)

    envelope_from = envelope_from or address_from
    envelope_to = envelope_to or (address_to + address_cc + address_bcc)

    try:
        smtp.sendmail(envelope_from, envelope_to, getattr(message_body, 'as_string', lambda: message_body)())
    except smtplib.SMTPSenderRefused as exc:
        logger.error(exc.smtp_error.decode(), smtp_code=exc.smtp_code)
        raise exc
    finally:
        smtp.quit()


def list_profiles(debug_level):
    if not PROFILES:
        print('No known profiles')
    else:
        print('Known profiles:')
        for name, profile in PROFILES.items():
            if debug_level > 0:
                data = profile.to_dict()
                if debug_level == 1:
                    data['password'] = '***'
                print(f"- {name} ({data})")
            else:
                print(f"- {name}")


def edit_profiles():
    import os
    import subprocess
    cmd = [
        os.environ.get('EDITOR') or os.environ.get('VISUAL') or 'vim',
        str(PROFILES_FILE),
    ]
    subprocess.run(cmd)


def list_messages():
    if not MESSAGES:
        print('No known messages')
    else:
        print('Known messages:')
        for name, message in MESSAGES.items():
            print(f"- {name} (from: \"{message.address_from or message.envelope_from}\", subject: \"{message.subject or ''}\")")


def edit_messages():
    import os
    import subprocess
    cmd = [
        os.environ.get('EDITOR') or os.environ.get('VISUAL') or 'vim',
        str(MESSAGES_FILE),
    ]
    subprocess.run(cmd)


def handle_profiles(args):
    if args.subcommand == 'list':
        list_profiles(args.debug)
        sys.exit()
    elif args.subcommand == 'edit':
        edit_profiles()
        sys.exit()
    else:
        PROFILES.add(Profile(
            name=args.name[0],
            login=args.login,
            password=args.password,
            host=args.host,
            port=args.port,
            ssl=args.ssl,
            tls=args.tls,
            connection_timeout=args.connection_timeout,
            identify_as=args.identify_as,
            source_address=args.source_address,
        ))
        logger.info('Profile saved', profile=args.name[0])


def handle_messages(args):
    if args.subcommand == 'list':
        list_messages()
        sys.exit()
    elif args.subcommand == 'edit':
        edit_messages()
        sys.exit()
    else:
        MESSAGES.add(Message(
            name=args.name[0],
            envelope_from=args.envelope_from,
            address_from=args.address_from,
            envelope_to=args.envelope_to,
            address_to=args.address_to,
            address_cc=args.address_cc,
            address_bcc=args.address_bcc,
            subject=args.subject,
            body_plain=args.body_plain,
            body_html=args.body_html,
            body_raw=args.body if args.raw_body else None,
            body_type=args.body_type,
            headers=args.headers,
        ))
        logger.info('Message saved', message=args.name[0])


def handle_send(args):
    message = None if not args.message else MESSAGES[args.message]
    if not message and args.raw_body:
        message_body = args.body
    else:
        message_body = build_message(
            subject=args.subject if not message else message.subject,
            envelope_from=args.envelope_from if not message else message.envelope_from,
            address_from=args.address_from if not message else message.address_from,
            envelope_to=args.envelope_to if not message else message.envelope_to,
            address_to=args.address_to if not message else message.address_to,
            address_cc=args.address_cc if not message else message.address_cc,
            body_type=args.body_type if not message else message.body_type,
            body_html=args.body_html or args.body if not message else message.body_html,
            body_plain=args.body_plain or args.body if not message else message.body_plain,
            headers=args.headers if not message else message.headers,
        )

    if args.profile:
        profile = PROFILES[args.profile]
    else:
        profile = None

    try:
        send_message(
            profile=profile,
            message=message,
            connection_timeout=args.connection_timeout,
            source_address=args.source_address,
            debug_level=args.debug,
            host=args.host,
            port=args.port,
            identify_as=args.identify_as,
            tls=args.tls,
            ssl=args.ssl,
            login=args.login,
            password=args.password,
            envelope_from=args.envelope_from,
            address_from=args.address_from,
            envelope_to=args.envelope_to,
            address_to=args.address_to,
            address_cc=args.address_cc,
            address_bcc=args.address_bcc,
            message_body=message_body,
        )
    except (smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError) as exc:
        logger.error(exc.smtp_error.decode(), smtp_code=exc.smtp_code)


def main():
    ensure_config_files()

    global PROFILES, MESSAGES
    try:
        PROFILES = Profiles.read()
    except toml.decoder.TomlDecodeError as exc:
        PROFILES = Profiles()
        logger.error(f"profiles configuration error: {exc}")

    try:
        MESSAGES = Messages.read()
    except toml.decoder.TomlDecodeError as exc:
        MESSAGES = Messages()
        logger.error(f"messages configuration error: {exc}")

    args = parse_argv(sys.argv[1:])
    configure_logger(args.debug > 0)

    if args.command == 'profiles':
        handle_profiles(args)
    elif args.command == 'send':
        handle_send(args)
    elif args.command == 'messages':
        handle_messages(args)

    sys.exit(0)
