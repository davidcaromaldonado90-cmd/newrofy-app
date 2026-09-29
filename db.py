"""
db.py
Módulo único encargado de la conexión a MySQL.
Todo el resto del proyecto pide la conexión desde aquí,
así si algo de la base de datos cambia, solo se edita este archivo.
"""

import os
from dotenv import load_dotenv

try:
    import pymysql
    import pymysql.cursors
    DRIVER = "pymysql"
except ImportError:
    import MySQLdb
    import MySQLdb.cursors
    DRIVER = "mysqldb"

load_dotenv()


def obtener_conexion():
    """Abre y devuelve una nueva conexión a la base de datos newrofy_db."""
    configuracion = {"host": os.getenv("DB_HOST"), "port": int(os.getenv("DB_PORT", "3306")), "user": os.getenv("DB_USER"), "autocommit": True}
    if DRIVER == "pymysql":
        configuracion.update({"password": os.getenv("DB_PASSWORD"), "database": os.getenv("DB_NAME"), "cursorclass": pymysql.cursors.DictCursor})
        return pymysql.connect(**configuracion)

    configuracion.update({"passwd": os.getenv("DB_PASSWORD"), "db": os.getenv("DB_NAME"), "cursorclass": MySQLdb.cursors.DictCursor})
    return MySQLdb.connect(**configuracion)
