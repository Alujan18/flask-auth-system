#email_utilis.py

from email.header import decode_header
from bs4 import BeautifulSoup
import re

def decode_str(s):
    """
    Decodifica una cadena de encabezado de correo electrónico.
    """
    if s:
        decoded_fragments = decode_header(s)
        decoded_string = ''
        for decoded_bytes, charset in decoded_fragments:
            if isinstance(decoded_bytes, bytes):
                if not charset:
                    charset = 'utf-8'
                decoded_string += decoded_bytes.decode(charset, errors='ignore')
            else:
                decoded_string += decoded_bytes
        return decoded_string
    else:
        return ''

def get_email_body(msg):
    """
    Extrae el cuerpo del correo electrónico, manejando texto plano y HTML.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset()
                if not charset:
                    charset = 'utf-8'
                try:
                    body += part.get_payload(decode=True).decode(charset, errors='ignore')
                except Exception as e:
                    print(f"Error al decodificar texto plano: {e}")
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == "text/html" and "attachment" not in content_disposition:
                charset = part.get_content_charset()
                if not charset:
                    charset = 'utf-8'
                try:
                    html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                    soup = BeautifulSoup(html_content, 'html.parser')
                    body += soup.get_text()
                except Exception as e:
                    print(f"Error al decodificar HTML: {e}")
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            charset = msg.get_content_charset()
            if not charset:
                charset = 'utf-8'
            try:
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
            except Exception as e:
                print(f"Error al decodificar texto plano: {e}")
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        elif content_type == "text/html":
            charset = msg.get_content_charset()
            if not charset:
                charset = 'utf-8'
            try:
                html_content = msg.get_payload(decode=True).decode(charset, errors='ignore')
                soup = BeautifulSoup(html_content, 'html.parser')
                body = soup.get_text()
            except Exception as e:
                print(f"Error al decodificar HTML: {e}")
                body = ""
    return body
