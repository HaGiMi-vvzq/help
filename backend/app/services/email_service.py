"""Email service — SMTP-based async email sending."""

import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.host: str = settings.__dict__.get("SMTP_HOST", "")
        self.port: int = int(settings.__dict__.get("SMTP_PORT", "587"))
        self.username: str = settings.__dict__.get("SMTP_USER", "")
        self.password: str = settings.__dict__.get("SMTP_PASSWORD", "")
        self.from_addr: str = settings.__dict__.get("SMTP_FROM", "noreply@campus-match.com")

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username)

    async def send(self, to: str, subject: str, html_body: str) -> bool:
        if not self.configured:
            logger.debug("SMTP not configured, skipping email to %s", to)
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        def _send():
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, [to], msg.as_string())

        try:
            await asyncio.get_event_loop().run_in_executor(None, _send)
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception as exc:
            logger.error("Email failed to %s: %s", to, exc)
            return False


_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


async def send_verification_email(to: str, username: str, token: str) -> bool:
    svc = get_email_service()
    if not svc.configured:
        return False
    link = f"{settings.__dict__.get('DOMAIN', 'http://localhost')}/verify-email?token={token}"
    return await svc.send(to, "验证你的校园AI互助匹配账号", f"""
    <h2>欢迎加入校园AI互助匹配，{username}！</h2>
    <p>请点击下方链接验证你的邮箱：</p>
    <p><a href="{link}">验证邮箱</a></p>
    <p>链接 24 小时内有效。</p>
    """)


async def send_password_reset_email(to: str, username: str, token: str) -> bool:
    svc = get_email_service()
    if not svc.configured:
        return False
    link = f"{settings.__dict__.get('DOMAIN', 'http://localhost')}/reset-password?token={token}"
    return await svc.send(to, "重置你的校园AI互助匹配密码", f"""
    <h2>{username}，你请求了密码重置</h2>
    <p>请点击下方链接重置密码：</p>
    <p><a href="{link}">重置密码</a></p>
    <p>如果这不是你本人的操作，请忽略此邮件。链接 15 分钟内有效。</p>
    """)
