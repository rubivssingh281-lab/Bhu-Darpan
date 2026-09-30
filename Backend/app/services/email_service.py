"""Transactional email (SMTP) for one-time-password delivery.

Sends the OTP over SMTP when credentials are configured (SMTP_HOST / SMTP_USER /
SMTP_PASS in the environment — e.g. a Gmail account with an app password). When
SMTP is *not* configured, the service runs in dev mode: it logs the OTP to the
server console and the API returns it in the response, so the whole sign-up /
sign-in flow is fully demo-able offline with zero setup.

This module never stores or logs real user passwords; only the transient OTP.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

from ..config import settings

log = logging.getLogger("bhu-darpan.email")

_SUBJECTS = {
    "register": "Verify your Bhū-Darpan account",
    "login": "Your Bhū-Darpan sign-in code",
}


def _html(code: str, purpose: str) -> str:
    """OTP email styled as the code arriving on an iPhone lock screen (notch /
    Dynamic Island + a Bhū-Darpan push notification). Table + inline-CSS only,
    with bgcolor fallbacks, so it renders in Gmail / Apple Mail."""
    action = "confirm your new account" if purpose == "register" else "sign in"
    title = "New account" if purpose == "register" else "Sign-in requested"
    spaced = "&nbsp;".join(code)  # airy spacing on the notification
    mins = settings.otp_expire_minutes
    fam = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif"

    # Real send-time clock/date (server local time) — 24h, synced, like the reference.
    now = datetime.now()
    clock = f"{now.hour:02d}:{now.minute:02d}"                          # e.g. 17:12
    datestr = f"{now.strftime('%A')}, {now.strftime('%B')} {now.day}"    # e.g. Tuesday, December 3

    # titanium / silver rail + side-button gradients
    rail = "linear-gradient(135deg,#eaedf0 0%,#b7bcc2 24%,#d9dde1 50%,#a6abb1 78%,#e6e9ec 100%)"
    btn = "linear-gradient(180deg,#d3d7db,#a7acb2 55%,#cdd1d5)"
    # Bhū-Darpan multicolour flowing wallpaper (teal + cream + terracotta over deep teal-navy)
    wall = ("linear-gradient(180deg,rgba(6,20,28,.45) 0%,transparent 26%),"
            "radial-gradient(130% 100% at 82% 30%,rgba(150,236,214,.92) 0%,rgba(60,186,166,.55) 22%,rgba(18,120,110,.22) 44%,transparent 60%),"
            "radial-gradient(80% 70% at 93% 5%,rgba(248,231,190,.78) 0%,transparent 42%),"
            "radial-gradient(120% 120% at 13% 96%,rgba(201,96,58,.52) 0%,rgba(150,60,40,.26) 34%,transparent 60%),"
            "radial-gradient(95% 90% at 28% 14%,rgba(38,92,122,.42),transparent 52%),"
            "linear-gradient(155deg,#0c3f39 0%,#0a2a3c 52%,#071c2b 100%)")
    # Fill spacer that pushes the bottom buttons down so the SCREEN is exactly
    # 19.5:9 (iPhone 18 Pro Max). Tuned for the 300px body / ~278px screen width.
    fill = 93

    def sidebtn(h):
        return (f'<tr><td width="5" height="{h}" bgcolor="#b7bcc2" '
                f'style="background:{btn};border-radius:4px 0 0 4px;width:5px;height:{h}px;'
                f'font-size:0;line-height:0">&nbsp;</td></tr>')

    def spacer_rail(h):
        return f'<tr><td height="{h}" style="height:{h}px;font-size:0;line-height:0">&nbsp;</td></tr>'

    return f"""\
<div style="margin:0;padding:28px 10px;background:#e9efe9;
            background:linear-gradient(160deg,#eef5f0,#e2ebe5);font-family:{fam}">
  <!-- iPhone assembly: [left buttons][body][right button] -->
  <table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0">
    <tr valign="top">

      <!-- LEFT RAIL: action switch + volume up/down -->
      <td valign="top" style="font-size:0;line-height:0;padding-top:6px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          {spacer_rail(120)}{sidebtn(22)}{spacer_rail(16)}{sidebtn(46)}{spacer_rail(12)}{sidebtn(46)}
        </table>
      </td>

      <!-- PHONE BODY -->
      <td valign="top">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="300"
               bgcolor="#c4c8cd" style="width:300px;background:#c4c8cd;background:{rail};
               border-radius:56px;padding:3px;box-shadow:0 22px 52px rgba(6,40,36,.4)">
          <tr><td bgcolor="#060708" style="background:#060708;border-radius:53px;padding:8px">
            <!-- Screen -->
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                   bgcolor="#0a2a3c" style="border-radius:46px;background:#0a2a3c;background:{wall};
                   overflow:hidden">

              <!-- status bar + Dynamic Island (centred by equal side columns) -->
              <tr><td style="padding:15px 20px 0 20px">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td width="64" align="left" style="width:64px">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
                        <td bgcolor="#ff5a4d" width="9" height="9" style="background:#ff5a4d;
                            border-radius:50%;width:9px;height:9px;font-size:0;line-height:0">&nbsp;</td>
                      </tr></table>
                    </td>
                    <td align="center">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
                        <tr><td bgcolor="#000000" width="92" height="28" align="right" valign="middle"
                                style="background:#000;border-radius:16px;width:92px;height:28px;padding-right:10px">
                          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                                background:#123f39;border:1px solid #1c5a50">&nbsp;</span></td></tr>
                      </table>
                    </td>
                    <td width="64" align="right" style="width:64px;color:#eafff7;font-size:12px;
                        letter-spacing:.3px;white-space:nowrap">&#9601;&#9603;&#9605;&nbsp;&#128246;&nbsp;<span
                        style="border:1px solid rgba(255,255,255,.85);border-radius:3px;padding:0 2px;font-size:9px">&#9646;&#9646;&#9646;</span></td>
                  </tr>
                </table>
              </td></tr>

              <!-- date + big 24h clock (upper third) -->
              <tr><td align="center" style="padding:22px 20px 2px 20px">
                <div style="color:#f4f8ff;font-size:15px;font-weight:600;letter-spacing:.3px;
                            text-shadow:0 1px 10px rgba(0,0,0,.4)">{datestr}</div>
                <div style="color:#ffffff;font-size:74px;font-weight:600;line-height:1.0;
                            letter-spacing:1px;text-shadow:0 2px 26px rgba(0,0,0,.35)">{clock}</div>
              </td></tr>

              <tr><td height="16" style="height:16px;font-size:0;line-height:0">&nbsp;</td></tr>

              <!-- push notification card -->
              <tr><td style="padding:0 15px">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                       bgcolor="#f6fbf8" style="background:#f6fbf8;border-radius:20px;
                       box-shadow:0 10px 28px rgba(0,0,0,.3)">
                  <tr><td style="padding:13px 14px">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                      <tr>
                        <td width="40" valign="top">
                          <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                            <tr><td bgcolor="#0f766e" width="36" height="36" align="center" valign="middle"
                                    style="background:#0f766e;background:linear-gradient(145deg,#15a897,#c9603a);
                                    border-radius:10px;width:36px;height:36px;color:#fff;font-size:18px">&#127807;</td></tr>
                          </table>
                        </td>
                        <td valign="top" style="padding-left:11px">
                          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr>
                              <td style="color:#0f2f2a;font-size:12px;font-weight:700;
                                         letter-spacing:.6px;text-transform:uppercase">Bhū-Darpan</td>
                              <td align="right" style="color:#8aa39c;font-size:11px">now</td>
                            </tr>
                          </table>
                          <div style="color:#20302c;font-size:13.5px;font-weight:700;margin-top:3px">{title}</div>
                          <div style="color:#4a5a55;font-size:13px;margin-top:2px">
                            Your verification code is <b style="color:#0f766e;letter-spacing:2px">{spaced}</b></div>
                        </td>
                      </tr>
                    </table>
                  </td></tr>
                </table>
              </td></tr>

              <!-- big code block -->
              <tr><td align="center" style="padding:12px 18px 0 18px">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                       bgcolor="#08302b" style="background:rgba(5,32,29,.55);border-radius:16px;
                       border:1px solid rgba(150,235,214,.30)">
                  <tr><td align="center" style="padding:13px 10px">
                    <div style="color:#bfe9dd;font-size:11px;letter-spacing:2px;text-transform:uppercase">
                      Verification code</div>
                    <div style="color:#ffffff;font-size:33px;font-weight:700;letter-spacing:10px;
                                padding-top:6px">{code}</div>
                  </td></tr>
                </table>
                <div style="color:#e6f2ec;font-size:12px;margin-top:11px;line-height:1.5;
                            text-shadow:0 1px 8px rgba(0,0,0,.4)">
                  Use it to {action}.<br>Expires in {mins} minutes.</div>
              </td></tr>

              <tr><td height="{fill}" style="height:{fill}px;font-size:0;line-height:0">&nbsp;</td></tr>

              <!-- lock-screen quick buttons (flashlight / camera) -->
              <tr><td align="center" style="padding:0 40px">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td align="left">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
                        <td bgcolor="#0b2a26" width="44" height="44" align="center" valign="middle"
                            style="background:rgba(6,28,25,.55);border:1px solid rgba(200,220,214,.25);
                            border-radius:50%;width:44px;height:44px;font-size:18px">&#128294;</td>
                      </tr></table>
                    </td>
                    <td align="right">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
                        <td bgcolor="#0b2a26" width="44" height="44" align="center" valign="middle"
                            style="background:rgba(6,28,25,.55);border:1px solid rgba(200,220,214,.25);
                            border-radius:50%;width:44px;height:44px;font-size:18px">&#128247;</td>
                      </tr></table>
                    </td>
                  </tr>
                </table>
              </td></tr>

              <!-- home indicator -->
              <tr><td align="center" style="padding:16px 0 14px 0">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
                  <tr><td bgcolor="#eef6f2" width="120" height="5"
                          style="background:rgba(238,246,242,.85);border-radius:3px;width:120px;height:5px;
                          font-size:0;line-height:0">&nbsp;</td></tr>
                </table>
              </td></tr>
            </table>
          </td></tr>
        </table>
      </td>

      <!-- RIGHT RAIL: power / side button -->
      <td valign="top" style="font-size:0;line-height:0;padding-top:6px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          {spacer_rail(150)}
          <tr><td width="5" height="66" bgcolor="#b7bcc2"
                  style="background:{btn};border-radius:0 4px 4px 0;width:5px;height:66px;
                  font-size:0;line-height:0">&nbsp;</td></tr>
        </table>
      </td>
    </tr>
  </table>

  <div style="text-align:center;color:#7d8f89;font-size:11.5px;margin-top:18px;
              font-family:{fam}">
    Bhū-Darpan · Climate Digital Twin<br>
    If you didn't request this, you can safely ignore this email.</div>
</div>"""


def send_otp_email(to_email: str, code: str, purpose: str) -> bool:
    """Deliver the OTP. Returns True if actually sent over SMTP, False in dev mode.

    Raises RuntimeError only if SMTP is configured but the send fails (so callers
    can surface a real delivery error to the user).
    """
    if not settings.smtp_configured:
        log.warning("[DEV OTP] %s -> %s (purpose=%s) — SMTP not configured; "
                    "set SMTP_HOST/SMTP_USER/SMTP_PASS to send real email.",
                    to_email, code, purpose)
        return False

    msg = EmailMessage()
    msg["Subject"] = _SUBJECTS.get(purpose, "Your Bhū-Darpan code")
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Your Bhū-Darpan verification code is {code}. "
        f"It expires in {settings.otp_expire_minutes} minutes."
    )
    msg.add_alternative(_html(code, purpose), subtype="html")

    try:
        if settings.smtp_use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=15) as s:
                s.login(settings.smtp_user, settings.smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                s.ehlo()
                if settings.smtp_starttls:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                s.login(settings.smtp_user, settings.smtp_pass)
                s.send_message(msg)
    except Exception as exc:  # surface a clean error to the caller
        log.error("SMTP send failed: %s", exc)
        raise RuntimeError(f"Could not send verification email: {exc}") from exc

    log.info("OTP email sent to %s (purpose=%s)", to_email, purpose)
    return True
