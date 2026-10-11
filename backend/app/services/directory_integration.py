import base64
import hashlib
import ssl
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from app.core.config import settings


class DirectoryConnectionError(RuntimeError):
    pass


def _cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    return _cipher().decrypt(value.encode("ascii")).decode("utf-8")


def _ldap_connection(config):
    try:
        from ldap3 import ALL, Connection, Server, Tls
    except ImportError as exc:
        raise DirectoryConnectionError("LDAP support is not installed on the backend.") from exc

    parsed = urlparse(config.server_url)
    if parsed.scheme not in {"ldap", "ldaps"} or not parsed.hostname:
        raise DirectoryConnectionError("Server URL must use ldap:// or ldaps://.")
    use_ssl = parsed.scheme == "ldaps" or bool(config.use_ssl)
    port = parsed.port or (636 if use_ssl else 389)
    certificate_policy = ssl.CERT_REQUIRED if config.verify_tls_certificate else ssl.CERT_NONE
    server = Server(parsed.hostname, port=port, use_ssl=use_ssl, get_info=ALL, tls=Tls(validate=certificate_policy))
    connection = Connection(server, user=config.bind_dn, password=decrypt_secret(config.encrypted_bind_password), auto_bind=False, receive_timeout=12)
    try:
        if not connection.open():
            raise DirectoryConnectionError(str(connection.last_error or "Could not open LDAP connection."))
        if config.start_tls and not use_ssl and not connection.start_tls():
            raise DirectoryConnectionError(str(connection.last_error or "STARTTLS negotiation failed."))
        if not connection.bind():
            raise DirectoryConnectionError(str(connection.result.get("message") or "LDAP bind failed."))
    except DirectoryConnectionError:
        connection.unbind()
        raise
    except Exception as exc:
        connection.unbind()
        raise DirectoryConnectionError(f"LDAP connection failed: {exc}") from exc
    return connection


def test_connection(config) -> str:
    connection = _ldap_connection(config)
    try:
        return connection.server.info.vendor_name or "LDAP connection and bind succeeded."
    finally:
        connection.unbind()


def list_groups(config, search: str = "") -> list[dict]:
    from ldap3 import SUBTREE
    from ldap3.utils.conv import escape_filter_chars

    connection = _ldap_connection(config)
    try:
        group_filter = config.group_filter or "(objectClass=group)"
        if search.strip():
            group_filter = f"(&{group_filter}(|(cn=*{escape_filter_chars(search.strip())}*)(name=*{escape_filter_chars(search.strip())}*)))"
        connection.search(
            search_base=config.group_base_dn or config.base_dn,
            search_filter=group_filter,
            search_scope=SUBTREE,
            attributes=["cn", "name", "member"],
            size_limit=200,
        )
        groups = []
        for entry in connection.entries:
            values = entry.entry_attributes_as_dict
            name = (values.get("cn") or values.get("name") or [entry.entry_dn])[0]
            members = values.get("member") or []
            groups.append({"dn": entry.entry_dn, "name": str(name), "member_count": len(members)})
        return sorted(groups, key=lambda item: item["name"].lower())
    finally:
        connection.unbind()


def fetch_recipients(config, group_dns: list[str]) -> list[dict]:
    from ldap3 import SUBTREE
    from ldap3.utils.conv import escape_filter_chars

    connection = _ldap_connection(config)
    try:
        membership_filter = ""
        if group_dns:
            membership_filter = "(|" + "".join(f"(memberOf={escape_filter_chars(dn)})" for dn in group_dns) + ")"
        search_filter = config.user_filter or "(&(objectClass=person)(mail=*))"
        if membership_filter:
            search_filter = f"(&{search_filter}{membership_filter})"
        attributes = list(dict.fromkeys([config.email_attribute, config.name_attribute, config.department_attribute]))
        connection.search(config.base_dn, search_filter, search_scope=SUBTREE, attributes=attributes, size_limit=5000)
        recipients = []
        seen = set()
        for entry in connection.entries:
            values = entry.entry_attributes_as_dict
            raw_email = values.get(config.email_attribute) or []
            email = str(raw_email[0]).strip().lower() if raw_email else ""
            if not email or "@" not in email or email in seen:
                continue
            seen.add(email)
            raw_name = values.get(config.name_attribute) or []
            raw_department = values.get(config.department_attribute) or []
            recipients.append({
                "email": email,
                "full_name": str(raw_name[0]).strip() if raw_name else None,
                "department": str(raw_department[0]).strip() if raw_department else None,
                "dn": entry.entry_dn,
            })
        return sorted(recipients, key=lambda item: item["email"])
    finally:
        connection.unbind()
