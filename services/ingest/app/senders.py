"""How alert messages leave the service: one small interface, an SMTP sender and a dry run that only logs.

A chat bot is added as another sender with its own `channel` key, matching a key in the site file's `alerts`.
Credentials come from environment variables only and are never logged, shown in health or kept in a repr.
"""
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.site import email_address

log = logging.getLogger("hk_site_display.alerts")
SMTP_TIMEOUT = 10
SECURITY = ("starttls", "ssl", "none")


@dataclass(frozen=True)
class Message:
    subject: str
    body: str


class SendError(Exception):
    """Nothing could be sent (no connection, login refused...). The caller retries later."""


def mask(address):
    """`s***@example.com`: enough to recognise an address in a log, not enough to collect it."""
    local, _, domain = str(address).partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


class DryRunSender:
    """Logs each message instead of sending it. The default until SMTP is configured."""

    channel = "email"
    mode = "dry-run"

    def describe(self):
        return "dry run: messages are logged, not sent"

    def send(self, recipients, message):
        shown = ", ".join(mask(r) for r in recipients)
        body = "\n".join(f"    {line}" for line in message.body.splitlines())
        log.info("alert (dry run, not sent) to %d: %s\n    %s\n%s", len(recipients), shown, message.subject, body)
        return []


class SmtpSender:
    """Plain-text email, one copy per recipient so nobody sees the others' addresses."""

    channel = "email"
    mode = "email"

    def __init__(self, host, port, security, user, password, from_addr, timeout=SMTP_TIMEOUT):
        self.host, self.port, self.security = host, port, security
        self.user, self.from_addr, self.timeout = user, from_addr, timeout
        self._password = password

    def __repr__(self):
        return f"SmtpSender({self.host}:{self.port}, {self.security})"

    def describe(self):
        return f"email via {self.host}:{self.port} ({self.security}) from {mask(self.from_addr)}"

    def _open(self):
        if self.security == "ssl":
            smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        try:
            if self.security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if self.user:
                smtp.login(self.user, self._password)
        except BaseException:
            smtp.close()
            raise
        return smtp

    def _mail(self, address, message):
        mail = EmailMessage()
        mail["From"] = self.from_addr
        mail["To"] = address
        mail["Subject"] = message.subject
        mail["Date"] = formatdate(localtime=True)
        mail["Message-ID"] = make_msgid(domain=self.from_addr.rpartition("@")[2] or None)
        mail["Auto-Submitted"] = "auto-generated"  # RFC 3834: no out-of-office replies to an alert
        mail.set_content(message.body)
        return mail

    def send(self, recipients, message):
        """Returns the recipients the server refused. Raises SendError when the server cannot be used at all."""
        try:
            smtp = self._open()
        except (smtplib.SMTPException, OSError) as error:
            raise SendError(describe_error(error)) from None
        refused = []
        try:
            for address in recipients:
                try:
                    smtp.send_message(self._mail(address, message))
                except smtplib.SMTPRecipientsRefused:
                    refused.append(address)
        except (smtplib.SMTPException, OSError) as error:
            raise SendError(describe_error(error)) from None
        finally:
            try:
                smtp.quit()
            except (smtplib.SMTPException, OSError):  # the messages are already handed over
                smtp.close()
        return refused


def describe_error(error):
    """The error's type and the server's reply code and text. Servers never echo the password back."""
    text = type(error).__name__
    code = getattr(error, "smtp_code", None)
    reply = getattr(error, "smtp_error", None)
    if code:
        text += f" {code}"
    if isinstance(reply, bytes):
        reply = reply.decode("utf-8", "replace")
    if reply:
        text += f": {' '.join(str(reply).split())[:160]}"
    elif not code and str(error):
        text += f": {str(error)[:160]}"
    return text


def sender_from_env(env):
    """(sender, problems). Without SMTP_HOST, or with ALERT_DRY_RUN=true, messages are only logged.

    A setting that cannot work (bad port, password over an unencrypted connection, no sender address) is a
    problem: the service still runs, in dry run, and /api/v1/health reports it.
    """
    host = (env.get("SMTP_HOST") or "").strip()
    if not host or (env.get("ALERT_DRY_RUN") or "").strip().lower() in ("1", "true", "yes"):
        return DryRunSender(), []
    problems = []
    try:
        port = int((env.get("SMTP_PORT") or "587").strip())
        if not 0 < port < 65536:
            raise ValueError
    except ValueError:
        problems.append("SMTP_PORT must be a port number")
        port = 0
    security = (env.get("SMTP_SECURITY") or ("ssl" if port == 465 else "starttls")).strip().lower()
    if security not in SECURITY:
        problems.append(f"SMTP_SECURITY must be one of {', '.join(SECURITY)}")
    user = (env.get("SMTP_USER") or "").strip()
    password = env.get("SMTP_PASSWORD") or ""
    if bool(user) != bool(password):
        problems.append("set both SMTP_USER and SMTP_PASSWORD, or neither")
    if security == "none" and password:
        problems.append("SMTP_SECURITY=none would send SMTP_PASSWORD unencrypted")
    from_addr = email_address(env.get("ALERT_FROM") or user)
    if from_addr is None:
        problems.append("set ALERT_FROM to the sender's email address")
    if problems:
        return DryRunSender(), [f"{p}; alerts are only logged until it is fixed" for p in problems]
    return SmtpSender(host, port, security, user, password, from_addr), []
