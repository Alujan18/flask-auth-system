# prompt_builder.py

def build_prompt(prompt_files_contents, info_principal_content, message_thread_content):
    """
    Construye el prompt concatenando el contenido de los archivos de prompt, info_principal y el hilo de mensajes.
    """
    prompt_content = ''
    # Añadir contenido de archivos de prompt
    for content in prompt_files_contents:
        prompt_content += content + '\n'

    # Añadir contenido de info_principal
    prompt_content += info_principal_content + '\n'

    # Añadir contenido del hilo de mensajes
    prompt_content += message_thread_content

    return prompt_content
