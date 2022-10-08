import smtplib
import mimetypes

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart


class MailSender:
    def __init__(self,
                 host: str,
                 port: int,
                 sent_from: str,
                 username: str,
                 password: str):
        self.message = MIMEMultipart()
        self.sent_from = sent_from
        self.message['From'] = sent_from
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.smtp_server = smtplib.SMTP_SSL(self.host, self.port)
        self.smtp_server.login(self.username, self.password)

    def send_mail(self,
                  subject: str,
                  send_to: str,
                  attachment_name: str = None):
        self.message['Subject'] = subject
        self.message.preamble = subject
        self.message['To'] = send_to
        if attachment_name:
            maintype, subtype = self.__get_type_of_attachment(attachment_name)
            with open(attachment_name, 'rb') as stream:
                attachment_ = MIMEBase(maintype, _subtype=subtype)
                attachment_.set_payload(stream.read())
            encoders.encode_base64(attachment_)
            attachment_.add_header("Content-Disposition", "attachment",
                                   filename=attachment_name)
            self.message.attach(attachment_)
        self.smtp_server.sendmail(self.sent_from, send_to,
                                  self.message.as_string())

    def __get_type_of_attachment(self,
                                 attachment_name: str):
        ctype, encoding = mimetypes.guess_type(attachment_name)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"

        return ctype.split("/", 1)

    def __del__(self):
        self.smtp_server.quit()
