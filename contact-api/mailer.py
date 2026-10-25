import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

RECIPIENT = "operations@sama-transports.com"


class DeliveryError(Exception):
    def __init__(self, uncertain=False):
        self.uncertain = uncertain


def connect(settings):
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if settings["SMTP_SECURITY"] == "ssl":
        client = smtplib.SMTP_SSL(settings["SMTP_HOST"], settings["SMTP_PORT"],
                                  timeout=15, context=context)
    else:
        client = smtplib.SMTP(settings["SMTP_HOST"], settings["SMTP_PORT"], timeout=15)
    try:
        client.ehlo()
        if settings["SMTP_SECURITY"] == "starttls":
            # No plaintext fallback. STARTTLS and certificate verification must succeed.
            client.starttls(context=context)
            client.ehlo()
        client.login(settings["SMTP_USERNAME"], settings["SMTP_PASSWORD"])
        return client
    except Exception:
        client.close()
        raise


def send(settings, fields, attachment, request_id):
    message = EmailMessage()
    message["From"] = "SAMA Website <" + settings["SMTP_USERNAME"] + ">"
    message["To"] = RECIPIENT
    message["Reply-To"] = fields["email"]
    message["Subject"] = "SAMA quotation request — " + fields["service"]
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = "<" + request_id + "@sama-transports.com>"
    message["Auto-Submitted"] = "auto-generated"
    body = ["SAMA Transportation — website request", "Reference: " + request_id, ""]
    for key, value in fields.items():
        body.extend([key.replace("_", " ").title() + ":", value or "—", ""])
    body.append("Attachments are customer-supplied documents. Treat their contents as untrusted.")
    message.set_content("\n".join(body))
    if attachment:
        data, filename, mime = attachment
        main, subtype = mime.split("/", 1)
        message.add_attachment(data, maintype=main, subtype=subtype, filename=filename)
    client = None
    sending = False
    try:
        client = connect(settings)
        sending = True
        refused = client.send_message(message, from_addr=settings["SMTP_USERNAME"],
                                      to_addrs=[RECIPIENT])
        if refused:
            raise DeliveryError()
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError) as exc:
        raise DeliveryError() from exc
    except (OSError, smtplib.SMTPException) as exc:
        # A disconnect during DATA may follow acceptance; never blindly resend.
        raise DeliveryError(uncertain=sending) from exc
    finally:
        if client:
            # After the final DATA acknowledgement, a QUIT error must not change success.
            client.close()
