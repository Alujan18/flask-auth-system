import imaplib
import email
from email.message import EmailMessage
import smtplib
from dotenv import load_dotenv
import os
import time

class EmailClient:
    def __init__(self):
        load_dotenv()
        self.imap_server = os.getenv('IMAP_SERVER')
        self.imap_port = int(os.getenv('IMAP_PORT', '993'))
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.connection = None
        self.smtp_connection = None

    def connect(self):
        if not all([self.imap_server, self.imap_port, self.smtp_server, 
                   self.smtp_port, self.email_address, self.email_password]):
            raise ValueError("Email configuration is incomplete")

        # Conexión al servidor IMAP
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_address, self.email_password)
            print("Conectado al servidor IMAP exitosamente.")
        except imaplib.IMAP4.error as e:
            print(f"Error al conectar al servidor IMAP: {e}")
            raise

        # Conexión al servidor SMTP
        try:
            self.smtp_connection = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            self.smtp_connection.login(self.email_address, self.email_password)
            print("Conectado al servidor SMTP exitosamente.")
        except smtplib.SMTPException as e:
            print(f"Error al conectar al servidor SMTP: {e}")
            raise

    def reconnect_imap(self):
        try:
            if self.connection:
                self.connection.logout()
        except:
            pass
        self.connect()

    def reconnect_smtp(self):
        try:
            if self.smtp_connection:
                self.smtp_connection.quit()
        except:
            pass
        try:
            self.smtp_connection = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            self.smtp_connection.login(self.email_address, self.email_password)
            print("Reconectado al servidor SMTP exitosamente.")
        except smtplib.SMTPException as e:
            print(f"Error al reconectar al servidor SMTP: {e}")
            raise

    def close_connection(self):
        if self.connection:
            try:
                self.connection.logout()
                print("Desconectado del servidor IMAP.")
            except imaplib.IMAP4.error as e:
                print(f"Error al cerrar la conexión IMAP: {e}")
        if self.smtp_connection:
            try:
                self.smtp_connection.quit()
                print("Desconectado del servidor SMTP.")
            except smtplib.SMTPException as e:
                print(f"Error al cerrar la conexión SMTP: {e}")

    def fetch_emails(self):
        emails = []
        folders = ["INBOX", "Sent"]  # Check both INBOX and Sent folders
        
        for folder in folders:
            try:
                # Select folder first
                typ, _ = self.connection.select(folder, readonly=True)
                if typ != 'OK':
                    print(f"Error al seleccionar la carpeta {folder}")
                    continue

                # Search for all emails in the folder
                typ, data = self.connection.search(None, 'ALL')
                if typ != 'OK':
                    print(f"Error al buscar correos en {folder}")
                    continue

                email_count = 0
                max_emails = 50  # Limit per folder
                
                # Reverse the order to get newest first
                message_numbers = data[0].split()[::-1]
                
                for num in message_numbers:
                    if email_count >= max_emails:
                        break
                        
                    try:
                        typ, msg_data = self.connection.fetch(num, '(RFC822)')
                        if typ == 'OK':
                            email_message = email.message_from_bytes(msg_data[0][1])
                            emails.append((num.decode(), email_message, folder))
                            email_count += 1
                        else:
                            print(f"Error al obtener el correo {num.decode()} de {folder}")
                    except Exception as e:
                        print(f"Error al obtener el correo {num.decode()} de {folder}: {e}")
                        continue
                    
            except Exception as e:
                print(f"Error al acceder a la carpeta {folder}: {e}")
                continue
                
        return emails

    def send_email(self, to_email, subject, body, in_reply_to=None, references=None, max_retries=3):
        msg = EmailMessage()
        msg['From'] = self.email_address
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(body)

        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
        if references:
            msg['References'] = references

        for attempt in range(max_retries):
            try:
                self.smtp_connection.send_message(msg)
                print(f"Correo enviado a {to_email}")
                return True
            except smtplib.SMTPException as e:
                print(f"Error al enviar correo a {to_email}: {e}")
                if attempt < max_retries - 1:
                    print("Intentando reconectar al servidor SMTP.")
                    self.reconnect_smtp()
                    time.sleep(5)
                    
        print(f"No se pudo enviar el correo a {to_email} después de {max_retries} intentos.")
        return False
