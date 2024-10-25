#conversarion_utils.py

import json
import os
from datetime import datetime, timezone

def load_conversations():
    """
    Carga las conversaciones desde el archivo JSON.
    """
    if os.path.exists('conversations.json'):
        try:
            with open('conversations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Asegurarse de que 'threads' y 'message_to_thread' existan
                if 'threads' not in data:
                    data['threads'] = {}
                if 'message_to_thread' not in data:
                    data['message_to_thread'] = {}
                return data
        except json.JSONDecodeError:
            print("Error al decodificar 'conversations.json'. Se creará una nueva estructura.")
            return {"threads": {}, "message_to_thread": {}}
    else:
        return {"threads": {}, "message_to_thread": {}}

def save_conversations(conversations):
    """
    Guarda las conversaciones en el archivo JSON.
    """
    with open('conversations.json', 'w', encoding='utf-8') as f:
        json.dump(conversations, f, indent=4, ensure_ascii=False)

def associate_to_thread(conversations, in_reply_to, references):
    """
    Asocia un correo a un hilo existente basado en 'In-Reply-To' y 'References'.
    Retorna el 'thread_id' si se encuentra uno existente, de lo contrario None.
    """
    if in_reply_to and in_reply_to in conversations["message_to_thread"]:
        return conversations["message_to_thread"][in_reply_to]
    
    if references:
        # Las referencias pueden contener múltiples Message-ID
        for ref in references:
            if ref in conversations["message_to_thread"]:
                return conversations["message_to_thread"][ref]
    
    return None

def process_email(conversations, thread_id, new_message_id=None):
    """
    Procesa el hilo de conversación asociado al thread_id.
    Retorna el contenido del hilo como una cadena de texto.
    """
    if thread_id not in conversations["threads"]:
        print("No se encontró el hilo de conversación.")
        return ''
    
    # Recuperar todos los emails del hilo
    thread_emails = conversations["threads"][thread_id]

    # Ordenar los correos con fecha basándose en UTC
    sorted_emails = sorted(
        [email for email in thread_emails if email['date']],
        key=lambda x: datetime.fromisoformat(x['date']).astimezone(timezone.utc)
    )
    # Añadir los correos sin fecha al final
    sorted_emails += [email for email in thread_emails if not email['date']]

    if not sorted_emails:
        print("El hilo de conversación está vacío.")
        return ''

    # Obtener el subject del primer mensaje del hilo
    subject = sorted_emails[0]['subject'] if sorted_emails[0]['subject'] else "(Sin Asunto)"

    # Construir el contenido del hilo
    contenido_hilo = ''
    contenido_hilo += f"Subject: {subject}\n"
    contenido_hilo += f"{'='*80}\n"

    # Añadir cada mensaje al contenido del hilo
    for idx, email in enumerate(sorted_emails, 1):
        sender = f"{email['from_name']} <{email['from_email']}>"
        # Convertir la fecha desde ISO a datetime y formatearla en UTC
        date_obj = datetime.fromisoformat(email['date']).astimezone(timezone.utc) if email['date'] else None
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S UTC") if date_obj else "Fecha desconocida"
        message_content = email['message']

        contenido_hilo += f"\nMensaje {idx}:\n"
        contenido_hilo += f"From: {sender}\n"
        contenido_hilo += f"Date: {date_str}\n"
        contenido_hilo += f"Body:\n{message_content}\n"
        contenido_hilo += f"{'-'*80}\n"

    return contenido_hilo
