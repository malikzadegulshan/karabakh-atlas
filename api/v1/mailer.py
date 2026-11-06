#!/usr/bin/python3
"""Sends transactional email (password-reset codes)
via the Brevo HTTP API (https://www.brevo.com).

Falls back to printing the message when BREVO_API_KEY or
BREVO_SENDER_EMAIL isn't configured, so password reset stays fully
testable in local dev without a real account.

Why Brevo over HTTPS instead of SMTP or Resend:
- PaaS hosts commonly block outbound SMTP ports (25/465/587) on
  free/starter tiers while leaving outbound HTTPS (443) open.
- Resend requires owning and verifying a custom DNS domain before it
  will deliver to anyone other than the account owner's own address.
- Brevo's free tier (300 emails/day) lets you verify a single personal
  sender email address (e.g. a Gmail or Outlook address) via a
  confirmation link and send to any recipient without owning a domain.
"""
from email.utils import parseaddr
import html
import json
import logging
import os
import re
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_SENDER_NAME = "Karabakh Atlas"
MAX_EMAIL_LENGTH = 254
MAX_SENDER_NAME_LENGTH = 128
MAX_ERROR_LOG_CHARS = 500
SUPPORTED_LANGS = ("en", "az", "tr", "ru")
DEFAULT_LANG = "en"
_SAFE_EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_BIDI_OVERRIDE_RE = re.compile(r"[\u202A-\u202E\u2066-\u2069]")

PASSWORD_RESET_I18N = {
    "en": {
        "subject": "Your Karabakh Atlas password reset code",
        "kicker": "Karabakh Atlas · Dirchalish",
        "title": "Password Reset Verification",
        "greeting": "Hi {name},",
        "intro": (
            "We received a request to reset the password for your "
            "Karabakh Atlas account. Enter the verification code below "
            "in the app to choose a new password:"
        ),
        "code_label": "Verification Code",
        "validity": (
            "This code is valid for 15 minutes and can only be used once."
        ),
        "footer": (
            "If you did not request a password reset, you can safely "
            "ignore this message — your password has not been changed. "
            "Never share this code with anyone."
        ),
        "signoff": "— Karabakh Atlas (Dirchalish)",
    },
    "az": {
        "subject": "Qarabağ Atlası şifrə sıfırlama kodunuz",
        "kicker": "Qarabağ Atlası · Dirçəliş",
        "title": "Şifrənin Sıfırlanması",
        "greeting": "Salam, {name},",
        "intro": (
            "Qarabağ Atlası hesabınızın şifrəsini sıfırlamaq üçün sorğu "
            "aldıq. Yeni şifrə təyin etmək üçün aşağıdakı təsdiq kodunu "
            "tətbiqdə daxil edin:"
        ),
        "code_label": "Təsdiq Kodu",
        "validity": (
            "Bu kod 15 dəqiqə ərzində etibarlıdır və yalnız bir dəfə "
            "istifadə oluna bilər."
        ),
        "footer": (
            "Əgər şifrə sıfırlama sorğusunu siz göndərməmisinizsə, bu "
            "məktuba məhəl qoymaya bilərsiniz — şifrəniz dəyişdirilməyib. "
            "Bu kodu heç kimlə paylaşmayın."
        ),
        "signoff": "— Qarabağ Atlası (Dirçəliş)",
    },
    "tr": {
        "subject": "Karabağ Atlası şifre sıfırlama kodunuz",
        "kicker": "Karabağ Atlası · Diriliş",
        "title": "Şifre Sıfırlama Doğrulaması",
        "greeting": "Merhaba {name},",
        "intro": (
            "Karabağ Atlası hesabınızın şifresini sıfırlamak için bir "
            "talep aldık. Yeni bir şifre belirlemek için aşağıdaki "
            "doğrulama kodunu uygulamaya girin:"
        ),
        "code_label": "Doğrulama Kodu",
        "validity": (
            "Bu kod 15 dakika boyunca geçerlidir ve yalnızca bir kez "
            "kullanılabilir."
        ),
        "footer": (
            "Şifre sıfırlama talebinde bulunmadıysanız bu e-postayı "
            "güvenle yok sayabilirsiniz — şifreniz değiştirilmemiştir. "
            "Bu kodu kimseyle paylaşmayın."
        ),
        "signoff": "— Karabağ Atlası (Diriliş)",
    },
    "ru": {
        "subject": (
            "Ваш код для сброса пароля в Карабахском Атласе"
        ),
        "kicker": "Карабахский Атлас · Дирчалиш",
        "title": "Подтверждение сброса пароля",
        "greeting": "Здравствуйте, {name}!",
        "intro": (
            "Мы получили запрос на сброс пароля для вашего аккаунта "
            "в Карабахском Атласе. Введите код подтверждения ниже в "
            "приложении, чтобы задать новый пароль:"
        ),
        "code_label": "Код подтверждения",
        "validity": (
            "Этот код действителен в течение 15 минут и может быть "
            "использован только один раз."
        ),
        "footer": (
            "Если вы не запрашивали сброс пароля, просто проигнорируйте "
            "это письмо — ваш пароль не был изменён. Никому не "
            "сообщайте этот код."
        ),
        "signoff": "— Карабахский Атлас (Дирчалиш)",
    },
}

WELCOME_I18N = {
    "en": {
        "subject": "Welcome to Karabakh Atlas — your membership is ready",
        "kicker": "Karabakh Atlas · Dirchalish",
        "title": "Welcome to the Community",
        "greeting": "Welcome, {name}!",
        "intro": (
            "We are delighted to have you with us. Your request to join "
            "Karabakh Atlas has been approved, and your account is now "
            "open and ready whenever you are."
        ),
        "box_title": "What You Can Do Next",
        "b1_title": "Save favorite places",
        "b1_body": (
            "bookmark historic landmarks, cities, and nature across "
            "Karabakh to revisit anytime."
        ),
        "b2_title": "Explore the timeline",
        "b2_body": (
            "trace how Karabakh’s regions and heritage have evolved "
            "through the years."
        ),
        "b3_title": "Share your voice",
        "b3_body": (
            "join the community forum to share local knowledge, "
            "memories, and reflections."
        ),
        "outro": (
            "Simply sign in with the email address and password you "
            "chose when registering. Thank you for helping celebrate "
            "and preserve the stories of Karabakh."
        ),
        "signoff_1": "Warm regards,",
        "signoff_2": "The Karabakh Atlas Team",
        "footer": (
            "If you did not request a Karabakh Atlas account, you can "
            "safely ignore this message."
        ),
    },
    "az": {
        "subject": (
            "Qarabağ Atlasına xoş gəlmisiniz — hesabınız təsdiqləndi"
        ),
        "kicker": "Qarabağ Atlası · Dirçəliş",
        "title": "İcmamıza Xoş Gəlmisiniz",
        "greeting": "Xoş gəldiniz, {name}!",
        "intro": (
            "Sizi aramızda görməkdən məmnunuq. Qarabağ Atlasına "
            "qoşulmaq üçün müraciətiniz təsdiqləndi və hesabınız "
            "artıq istifadəyə hazırdır."
        ),
        "box_title": "Nələri Kəşf Edə Bilərsiniz",
        "b1_title": "Sevimli məkanları yadda saxlayın",
        "b1_body": (
            "Qarabağın tarixi abidələrini, şəhərlərini və təbiət "
            "guşələrini istənilən vaxt yenidən baxmaq üçün işarələyin."
        ),
        "b2_title": "Tarixi xronologiyanı izləyin",
        "b2_body": (
            "Qarabağ bölgələrinin və irsinin illər ərzində necə "
            "dəyişdiyini araşdırın."
        ),
        "b3_title": "Fikirlərinizi bölüşün",
        "b3_body": (
            "icma forumuna qoşularaq yerli biliklərinizi, "
            "xatirələrinizi və təəssüratlarınızı paylaşın."
        ),
        "outro": (
            "Sadəcə qeydiyyat zamanı seçdiyiniz e-poçt ünvanı və "
            "şifrə ilə daxil olun. Qarabağın tarixini və hekayələrini "
            "yaşatmağa dəstək olduğunuz üçün təşəkkür edirik."
        ),
        "signoff_1": "Ən xoş arzularla,",
        "signoff_2": "Qarabağ Atlası Komandası",
        "footer": (
            "Əgər Qarabağ Atlasında hesab yaratmaq üçün müraciət "
            "etməmisinizsə, bu məktuba məhəl qoymaya bilərsiniz."
        ),
    },
    "tr": {
        "subject": (
            "Karabağ Atlası’na hoş geldiniz — üyeliğiniz hazır"
        ),
        "kicker": "Karabağ Atlası · Diriliş",
        "title": "Topluluğumuza Hoş Geldiniz",
        "greeting": "Hoş geldiniz, {name}!",
        "intro": (
            "Aramızda olmanızdan büyük mutluluk duyuyoruz. Karabağ "
            "Atlası’na katılma talebiniz onaylandı ve hesabınız artık "
            "kullanıma hazır."
        ),
        "box_title": "Neler Yapabilirsiniz",
        "b1_title": "Favori yerleri kaydedin",
        "b1_body": (
            "Karabağ genelindeki tarihi yapıları, şehirleri ve doğal "
            "güzellikleri istediğiniz zaman tekrar görmek için işaretleyin."
        ),
        "b2_title": "Zaman çizelgesini keşfedin",
        "b2_body": (
            "Karabağ’ın bölgelerinin ve mirasının yıllar içinde "
            "nasıl geliştiğini inceleyin."
        ),
        "b3_title": "Sesinizi paylaşın",
        "b3_body": (
            "yerel bilgilerinizi, anılarınızı ve düşüncelerinizi "
            "paylaşmak için topluluk forumuna katılın."
        ),
        "outro": (
            "Kayıt olurken belirlediğiniz e-posta adresi ve şifreyle "
            "giriş yapabilirsiniz. Karabağ’ın hikayelerini yaşatmaya "
            "katkıda bulunduğunuz için teşekkür ederiz."
        ),
        "signoff_1": "En içten dileklerimizle,",
        "signoff_2": "Karabağ Atlası Ekibi",
        "footer": (
            "Karabağ Atlası’nda hesap talebinde bulunmadıysanız bu "
            "mesajı güvenle yok sayabilirsiniz."
        ),
    },
    "ru": {
        "subject": (
            "Добро пожаловать в Карабахский Атлас — "
            "ваш аккаунт одобрен"
        ),
        "kicker": "Карабахский Атлас · Дирчалиш",
        "title": "Добро пожаловать в сообщество",
        "greeting": "Добро пожаловать, {name}!",
        "intro": (
            "Мы искренне рады видеть вас среди нас. Ваша заявка на "
            "вступление в Карабахский Атлас одобрена, и ваш аккаунт "
            "теперь полностью готов к работе."
        ),
        "box_title": "Что вам доступно",
        "b1_title": "Сохраняйте избранные места",
        "b1_body": (
            "отмечайте исторические памятники, города и уголки "
            "природы Карабаха, чтобы легко возвращаться к ним."
        ),
        "b2_title": "Исследуйте хронологию",
        "b2_body": (
            "проследите, как менялись регионы и наследие Карабаха "
            "на протяжении лет."
        ),
        "b3_title": "Делитесь своим мнением",
        "b3_body": (
            "участвуйте в форуме сообщества, делитесь знаниями, "
            "воспоминаниями и впечатлениями."
        ),
        "outro": (
            "Просто войдите с адресом электронной почты и паролем, "
            "которые вы указали при регистрации. Спасибо, что "
            "помогаете сохранять историю и живую память о Карабахе."
        ),
        "signoff_1": "С тёплыми пожеланиями,",
        "signoff_2": "Команда Карабахского Атласа",
        "footer": (
            "Если вы не подавали заявку на создание аккаунта в "
            "Карабахском Атласе, просто проигнорируйте это письмо."
        ),
    },
}


def normalize_lang(lang):
    """Return a supported language code ('en', 'az', 'tr', 'ru')."""
    if isinstance(lang, str):
        code = lang.strip().lower()
        if code in SUPPORTED_LANGS:
            return code
    return DEFAULT_LANG


def build_password_reset_email(name, otp, lang=DEFAULT_LANG):
    """Return (subject, text_body, html_body) for a password-reset OTP
    in the requested language ('en', 'az', 'tr', 'ru')."""
    code = normalize_lang(lang)
    strings = PASSWORD_RESET_I18N[code]
    clean_name = sanitize_email_name(name)
    safe_name = html.escape(clean_name, quote=True)
    safe_otp = html.escape(str(otp), quote=True)
    html_greeting = strings["greeting"].format(
        name="<strong>{}</strong>".format(safe_name))
    text_greeting = strings["greeting"].format(name=clean_name)

    text_body = (
        "{greeting}\n\n"
        "{intro}\n\n"
        "{code_label}: {otp}\n\n"
        "{validity}\n\n"
        "{footer}\n\n"
        "{signoff}"
    ).format(
        greeting=text_greeting,
        intro=strings["intro"],
        code_label=strings["code_label"],
        otp=otp,
        validity=strings["validity"],
        footer=strings["footer"],
        signoff=strings["signoff"],
    )
    html_body = (
        '<!DOCTYPE html>'
        '<html lang="{lang}"><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:32px 16px;background-color:#f5f1e8;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,'
        'Helvetica,Arial,sans-serif;color:#1e2923;">'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="max-width:480px;margin:0 auto;'
        'background-color:#ffffff;border:1px solid #e2dccf;'
        'border-radius:12px;overflow:hidden;">'
        '<tr><td style="background-color:#1f3a2e;padding:22px 28px;">'
        '<div style="font-size:11px;letter-spacing:1.6px;'
        'text-transform:uppercase;color:#c9b99a;font-weight:600;">'
        '{kicker}</div>'
        '<div style="font-size:19px;font-weight:700;color:#ffffff;'
        'margin-top:4px;">{title}</div>'
        '</td></tr>'
        '<tr><td style="padding:28px;">'
        '<p style="margin:0 0 14px;font-size:15px;line-height:1.5;'
        'color:#1e2923;">{greeting}</p>'
        '<p style="margin:0 0 20px;font-size:14px;line-height:1.6;'
        'color:#47544c;">{intro}</p>'
        '<div style="margin:0 0 20px;padding:18px 16px;'
        'background-color:#f8f5ee;border:1px solid #dfd7c6;'
        'border-radius:8px;text-align:center;">'
        '<div style="font-size:11px;text-transform:uppercase;'
        'letter-spacing:1.2px;color:#6e6556;margin-bottom:6px;">'
        '{code_label}</div>'
        '<div style="font-family:\'SFMono-Regular\',Consolas,'
        '\'Liberation Mono\',Menlo,monospace;font-size:28px;'
        'font-weight:700;letter-spacing:6px;color:#1f3a2e;">{otp}</div>'
        '</div>'
        '<p style="margin:0 0 18px;font-size:13px;line-height:1.5;'
        'color:#5c6860;">{validity}</p>'
        '<hr style="border:none;border-top:1px solid #ebe5d8;'
        'margin:20px 0;">'
        '<p style="margin:0;font-size:12px;line-height:1.5;'
        'color:#78827b;">{footer}</p>'
        '</td></tr></table></body></html>'
    ).format(
        lang=code,
        kicker=html.escape(strings["kicker"]),
        title=html.escape(strings["title"]),
        greeting=html_greeting,
        intro=html.escape(strings["intro"]),
        code_label=html.escape(strings["code_label"]),
        otp=safe_otp,
        validity=html.escape(strings["validity"]),
        footer=html.escape(strings["footer"]),
    )
    return strings["subject"], text_body, html_body


def build_welcome_email(name, lang=DEFAULT_LANG):
    """Return (subject, text_body, html_body) welcoming a newly approved
    member in the requested language ('en', 'az', 'tr', 'ru')."""
    code = normalize_lang(lang)
    strings = WELCOME_I18N[code]
    clean_name = sanitize_email_name(name)
    safe_name = html.escape(clean_name, quote=True)
    html_greeting = strings["greeting"].format(
        name="<strong>{}</strong>".format(safe_name))
    text_greeting = strings["greeting"].format(name=clean_name)

    text_body = (
        "{greeting}\n\n"
        "{intro}\n\n"
        "{box_title}:\n"
        "- {b1_title} \u2014 {b1_body}\n"
        "- {b2_title} \u2014 {b2_body}\n"
        "- {b3_title} \u2014 {b3_body}\n\n"
        "{outro}\n\n"
        "{signoff_1}\n"
        "{signoff_2}"
    ).format(
        greeting=text_greeting,
        intro=strings["intro"],
        box_title=strings["box_title"],
        b1_title=strings["b1_title"],
        b1_body=strings["b1_body"],
        b2_title=strings["b2_title"],
        b2_body=strings["b2_body"],
        b3_title=strings["b3_title"],
        b3_body=strings["b3_body"],
        outro=strings["outro"],
        signoff_1=strings["signoff_1"],
        signoff_2=strings["signoff_2"],
    )
    html_body = (
        '<!DOCTYPE html>'
        '<html lang="{lang}"><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:32px 16px;background-color:#f5f1e8;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,'
        'Helvetica,Arial,sans-serif;color:#1e2923;">'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="max-width:480px;margin:0 auto;'
        'background-color:#ffffff;border:1px solid #e2dccf;'
        'border-radius:12px;overflow:hidden;">'
        '<tr><td style="background-color:#1f3a2e;padding:24px 28px;">'
        '<div style="font-size:11px;letter-spacing:1.6px;'
        'text-transform:uppercase;color:#c9b99a;font-weight:600;">'
        '{kicker}</div>'
        '<div style="font-size:20px;font-weight:700;color:#ffffff;'
        'margin-top:4px;">{title}</div>'
        '</td></tr>'
        '<tr><td style="padding:28px;">'
        '<p style="margin:0 0 14px;font-size:16px;line-height:1.5;'
        'color:#1e2923;">{greeting}</p>'
        '<p style="margin:0 0 18px;font-size:14px;line-height:1.6;'
        'color:#47544c;">{intro}</p>'
        '<div style="margin:0 0 20px;padding:18px 20px;'
        'background-color:#f8f5ee;border:1px solid #dfd7c6;'
        'border-radius:8px;">'
        '<div style="font-size:12px;text-transform:uppercase;'
        'letter-spacing:1.2px;color:#6e6556;font-weight:600;'
        'margin-bottom:10px;">{box_title}</div>'
        '<p style="margin:0 0 8px;font-size:13px;line-height:1.5;'
        'color:#2c3a32;"><strong>&bull; {b1_title}</strong> '
        '&mdash; {b1_body}</p>'
        '<p style="margin:0 0 8px;font-size:13px;line-height:1.5;'
        'color:#2c3a32;"><strong>&bull; {b2_title}</strong> '
        '&mdash; {b2_body}</p>'
        '<p style="margin:0;font-size:13px;line-height:1.5;'
        'color:#2c3a32;"><strong>&bull; {b3_title}</strong> '
        '&mdash; {b3_body}</p>'
        '</div>'
        '<p style="margin:0 0 18px;font-size:14px;line-height:1.6;'
        'color:#47544c;">{outro}</p>'
        '<p style="margin:0 0 20px;font-size:14px;line-height:1.5;'
        'color:#1f3a2e;font-weight:600;">{signoff_1}<br>'
        '{signoff_2}</p>'
        '<hr style="border:none;border-top:1px solid #ebe5d8;'
        'margin:18px 0;">'
        '<p style="margin:0;font-size:12px;line-height:1.5;'
        'color:#78827b;">{footer}</p>'
        '</td></tr></table></body></html>'
    ).format(
        lang=code,
        kicker=html.escape(strings["kicker"]),
        title=html.escape(strings["title"]),
        greeting=html_greeting,
        intro=html.escape(strings["intro"]),
        box_title=html.escape(strings["box_title"]),
        b1_title=html.escape(strings["b1_title"]),
        b1_body=html.escape(strings["b1_body"]),
        b2_title=html.escape(strings["b2_title"]),
        b2_body=html.escape(strings["b2_body"]),
        b3_title=html.escape(strings["b3_title"]),
        b3_body=html.escape(strings["b3_body"]),
        outro=html.escape(strings["outro"]),
        signoff_1=html.escape(strings["signoff_1"]),
        signoff_2=html.escape(strings["signoff_2"]),
        footer=html.escape(strings["footer"]),
    )
    return strings["subject"], text_body, html_body


def _has_control_chars(value):
    return (
        any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
        or bool(_BIDI_OVERRIDE_RE.search(value))
    )


def sanitize_email_name(name):
    """Strip control characters and Unicode BiDi overrides from a display
    name before interpolating it into plain-text or HTML email bodies."""
    if not isinstance(name, str):
        return "Member"
    cleaned = _BIDI_OVERRIDE_RE.sub("", name)
    cleaned = "".join(
        ch for ch in cleaned if ord(ch) >= 32 and ord(ch) != 127
    ).strip()
    return cleaned[:MAX_SENDER_NAME_LENGTH] or "Member"


def _is_valid_email(addr):
    return (
        isinstance(addr, str)
        and 3 <= len(addr) <= MAX_EMAIL_LENGTH
        and not _has_control_chars(addr)
        and bool(_SAFE_EMAIL_RE.match(addr))
    )


def _is_production():
    env = (os.environ.get("KBA_ENV") or "").strip().lower()
    return env in ("prod", "production") or bool(os.environ.get("RENDER"))


def _sanitize_for_log(text, max_len=MAX_ERROR_LOG_CHARS):
    cleaned = "".join(
        " " if (ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in str(text)
    )
    return cleaned[:max_len]


def _brevo_config():
    api_key = (os.environ.get("BREVO_API_KEY") or "").strip()
    raw_sender = (os.environ.get("BREVO_SENDER_EMAIL") or "").strip()
    if not api_key or not raw_sender:
        return None
    # Reject control or non-ASCII chars in API key (HTTP header safety)
    if any(ord(ch) <= 32 or ord(ch) >= 127 for ch in api_key):
        logger.error("Invalid characters in BREVO_API_KEY")
        return None
    # Guard against CVE-2023-27043 / multi-angle-bracket address injection
    if _has_control_chars(raw_sender) or raw_sender.count("<") > 1:
        logger.error("Invalid BREVO_SENDER_EMAIL configuration")
        return None
    parsed_name, sender_email = parseaddr(raw_sender)
    if not _is_valid_email(sender_email):
        logger.error("Invalid BREVO_SENDER_EMAIL address")
        return None
    sender_name = (
        os.environ.get("BREVO_SENDER_NAME") or ""
    ).strip() or parsed_name or DEFAULT_SENDER_NAME
    if _has_control_chars(sender_name):
        logger.error("Invalid characters in BREVO_SENDER_NAME")
        return None
    return {
        "api_key": api_key,
        "sender_email": sender_email,
        "sender_name": sender_name[:MAX_SENDER_NAME_LENGTH],
    }


def send_email(to_addr, subject, body, html_body=None):
    """Send a plain-text (and optional HTML) email, or log it if Brevo
    isn't configured. Never raises — a mail failure shouldn't break the
    request that triggered it (e.g. a password-reset request should
    still return 200 even if the email couldn't be sent).
    """
    if not _is_valid_email(to_addr) or not isinstance(subject, str):
        logger.error("Refusing to send email to invalid recipient")
        return False
    if _has_control_chars(subject) or not isinstance(body, str):
        logger.error("Refusing to send email with invalid subject/body")
        return False
    if html_body is not None and not isinstance(html_body, str):
        logger.error("Refusing to send email with invalid html_body")
        return False

    config = _brevo_config()
    if config is None:
        if _is_production():
            # Never log plaintext password-reset OTP bodies in production
            logger.warning(
                "BREVO_API_KEY / BREVO_SENDER_EMAIL not configured in "
                "production — dropping email to %s",
                _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            )
            return False
        logger.info(
            "BREVO_API_KEY / BREVO_SENDER_EMAIL not configured — "
            "printing email instead of sending it:\n"
            "  To: %s\n  Subject: %s\n  Body:\n%s",
            to_addr, subject, body,
        )
        return True

    message = {
        "sender": {
            "name": config["sender_name"],
            "email": config["sender_email"],
        },
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": body,
    }
    if html_body:
        message["htmlContent"] = html_body
    payload = json.dumps(message).encode("utf-8")
    request = urllib.request.Request(
        BREVO_API_URL,
        data=payload,
        method="POST",
        headers={
            "api-key": config["api_key"],
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Avoid generic "Python-urllib/x.y" User-Agent blocks on
            # Cloudflare-fronted APIs (error 1010).
            "User-Agent": "karabakh-atlas-mailer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
        return True
    except urllib.error.HTTPError as error:
        detail = ""
        if error.fp is not None:
            raw = error.fp.read(MAX_ERROR_LOG_CHARS * 2)
            detail = _sanitize_for_log(raw.decode("utf-8", "replace"))
        logger.error(
            "Failed to send email to %s: HTTP %s %s%s",
            _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            error.code,
            _sanitize_for_log(error.reason, 128),
            " - {}".format(detail) if detail else "",
        )
        return False
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error(
            "Failed to send email to %s: %s",
            _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            _sanitize_for_log(error),
        )
        return False
