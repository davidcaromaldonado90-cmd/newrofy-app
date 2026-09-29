"""
crear_admin.py
Script de un solo uso: crea el rol 'Administrador' (si no existe)
y un usuario administrador de prueba para poder iniciar sesión
por primera vez.

Ejecutar UNA sola vez con:
    python crear_admin.py
"""

from werkzeug.security import generate_password_hash
from db import obtener_conexion

NOMBRE = "Admin Newrofy"
CORREO = "admin@newrofy.com"
CONTRASENA_PLANA = "admin123"   # cámbiala luego desde la app, esto es solo para la primera entrada
DNI = "0000000000"

conexion = obtener_conexion()
with conexion.cursor() as cursor:
    # 1. Crear el rol si no existe
    cursor.execute("SELECT id_rol FROM roles WHERE nombre_cargo = %s", ("Administrador",))
    rol = cursor.fetchone()

    if rol:
        id_rol = rol["id_rol"]
        print("El rol 'Administrador' ya existía, se reutiliza.")
    else:
        cursor.execute(
            "INSERT INTO roles (nombre_cargo, permisos) VALUES (%s, %s)",
            ("Administrador", '["todo"]'),
        )
        id_rol = cursor.lastrowid
        print("Rol 'Administrador' creado.")

    # 2. Crear el usuario si no existe
    cursor.execute("SELECT id_usuario FROM usuarios WHERE correo = %s", (CORREO,))
    existente = cursor.fetchone()

    if existente:
        print(f"Ya existe un usuario con el correo {CORREO}, no se creó de nuevo.")
    else:
        hash_contrasena = generate_password_hash(CONTRASENA_PLANA)
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, correo, contrasena, dni, id_rol)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (NOMBRE, CORREO, hash_contrasena, DNI, id_rol),
        )
        print("Usuario administrador creado con éxito.")
        print(f"   Correo:     {CORREO}")
        print(f"   Contraseña: {CONTRASENA_PLANA}")

conexion.close()
