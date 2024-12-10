import httpx
from typing import Optional

def enviar_correo_bienvenida(correo_destinatario: str, contraseña: str) -> Optional[bool]:
    try:
        # Configuración de Mailtrap
        url = "https://sandbox.api.mailtrap.io/api/send/3309844"
        
        # Construir el payload
        payload = {
            "from": {
                "email": "sistema@seguridadhogar.com",
                "name": "Sistema de Seguridad Hogar"
            },
            "to": [
                {
                    "email": correo_destinatario
                }
            ],
            "subject": "Bienvenido a tu Sistema de Seguridad Hogar",
            "text": f"""
Bienvenido a tu Sistema de Seguridad Hogar,

Se ha creado tu cuenta con éxito. 

Tus credenciales de acceso son:
Correo electrónico: {correo_destinatario}
Contraseña temporal: {contraseña}

Por seguridad, te recomendamos cambiar tu contraseña al iniciar sesión por primera vez.

Saludos cordiales,
Equipo de SKYZO
            """,
            "category": "Bienvenida Cliente"
        }

        # Configurar los headers
        headers = {
            "Authorization": "Bearer f4f840f9aeabc65950144bca030d1e58",
            "Content-Type": "application/json"
        }

        # Enviar la solicitud
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)

        # Verificar si el envío fue exitoso
        if response.status_code == 200:
            print(f"Correo enviado exitosamente a {correo_destinatario}")
            return True
        else:
            print(f"Error al enviar correo. Código de estado: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False

    except Exception as e:
        print(f"Error al enviar correo: {str(e)}")
        return False
    

# Función para enviar correo de recuperación
def enviar_correo_recuperacion(correo_destinatario: str, nueva_contraseña: str) -> bool:
    try:
        # Configuración de Mailtrap
        url = "https://sandbox.api.mailtrap.io/api/send/3309844"
        
        payload = {
            "from": {
                "email": "sistema@seguridadhogar.com",
                "name": "Sistema de Seguridad Hogar"
            },
            "to": [
                {
                    "email": correo_destinatario
                }
            ],
            "subject": "Recuperación de contraseña",
            "text": f"""
Hola,

Se ha solicitado la recuperación de tu contraseña.

Tu nueva contraseña temporal es:
{nueva_contraseña}

Por seguridad, te recomendamos cambiar tu contraseña al iniciar sesión.

Saludos cordiales,
Equipo de SKYZO
            """,
            "category": "Recuperación Contraseña"
        }

        headers = {
            "Authorization": "Bearer f4f840f9aeabc65950144bca030d1e58",
            "Content-Type": "application/json"
        }

        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            print(f"Correo enviado exitosamente a {correo_destinatario}")
            return True
        else:
            print(f"Error al enviar correo. Código de estado: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False

    except Exception as e:
        print(f"Error al enviar correo: {str(e)}")
        return False
