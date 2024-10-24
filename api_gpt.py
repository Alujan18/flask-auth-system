# api_gpt.py

import openai
import os
from dotenv import load_dotenv
import openai.error

class ApiGPT:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('API_OPENAI')
        if not self.api_key:
            raise ValueError("La clave de API de OpenAI no está definida en las variables de entorno.")
        openai.api_key = self.api_key

    def gpt4_request(self, prompt):
        try:
            print("Enviando solicitud a GPT-4")
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un asistente útil."},
                    {"role": "user", "content": prompt}
                ]
            )
            result = response.choices[0].message['content'].strip()
            print(f"Respuesta de GPT-4 recibida: {result[:50]}")
            return result
        except openai.error.RateLimitError as e:
            print(f"Límite de tasa alcanzado: {e}")
            return None
        except openai.error.APIConnectionError as e:
            print(f"Error de conexión con la API de OpenAI: {e}")
            return None
        except openai.error.InvalidRequestError as e:
            print(f"Solicitud inválida a la API de OpenAI: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado al generar respuesta con GPT: {e}")
            return None
