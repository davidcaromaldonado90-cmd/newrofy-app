"""
app.py
Base de la aplicación web Newrofy.
Incluye: conexión a la base de datos, login con roles,
y un panel (dashboard) que muestra un menú distinto según el rol
del usuario que inició sesión.
"""

import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

from db import obtener_conexion

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


def consulta_unica(sql, parametros=()):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchone()
    finally:
        conexion.close()


def consulta_varias(sql, parametros=()):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()
    finally:
        conexion.close()


def empresa_actual():
    return consulta_unica(
        "SELECT * FROM empresas WHERE id_usuario = %s ORDER BY fecha_creacion DESC, id_empresa DESC LIMIT 1",
        (session["id_usuario"],),
    )


def diagnostico_actual(id_empresa):
    if not id_empresa:
        return None
    dato = consulta_unica(
        """SELECT f.id_formulario, f.respuestas, f.fecha_completado, m.nivel, m.puntaje
           FROM formularios_diagnostico f
           LEFT JOIN madurez_digital m ON m.id_formulario = f.id_formulario
           WHERE f.id_empresa = %s ORDER BY f.fecha_completado DESC, f.id_formulario DESC LIMIT 1""",
        (id_empresa,),
    )
    if dato and dato["respuestas"]:
        dato["respuestas"] = json.loads(dato["respuestas"]) if isinstance(dato["respuestas"], str) else dato["respuestas"]
    return dato


def estrategia_actual(id_empresa):
    if not id_empresa:
        return None
    dato = consulta_unica(
        "SELECT * FROM estrategias WHERE id_empresa = %s ORDER BY fecha_generacion DESC, id_estrategia DESC LIMIT 1",
        (id_empresa,),
    )
    if dato and dato["canales_recomendados"]:
        dato["canales_recomendados"] = json.loads(dato["canales_recomendados"]) if isinstance(dato["canales_recomendados"], str) else dato["canales_recomendados"]
    return dato


# ------------------------------------------------------------
# Decorador para proteger rutas: si no hay sesión iniciada,
# manda de vuelta al login.
# ------------------------------------------------------------
def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "id_usuario" not in session:
            flash("Debes iniciar sesión primero.", "error")
            return redirect(url_for("login"))
        return vista(*args, **kwargs)
    return envoltura


# ------------------------------------------------------------
# Página raíz: si ya hay sesión, va al dashboard; si no, al login.
# ------------------------------------------------------------
@app.route("/")
def inicio():
    if "id_usuario" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ------------------------------------------------------------
# Login
# ------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "")

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id_usuario, u.nombre, u.correo, u.contrasena,
                       r.id_rol, r.nombre_cargo
                FROM usuarios u
                JOIN roles r ON r.id_rol = u.id_rol
                WHERE u.correo = %s
                """,
                (correo,),
            )
            usuario = cursor.fetchone()
        conexion.close()

        if usuario and check_password_hash(usuario["contrasena"], contrasena):
            session["id_usuario"] = usuario["id_usuario"]
            session["nombre"] = usuario["nombre"]
            session["rol"] = usuario["nombre_cargo"]
            flash(f"Bienvenido, {usuario['nombre']}.", "exito")
            return redirect(url_for("dashboard"))

        flash("Correo o contraseña incorrectos.", "error")

    return render_template("login.html")


# ------------------------------------------------------------
# Logout
# ------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "exito")
    return redirect(url_for("login"))


# ------------------------------------------------------------
# Dashboard: el menú que se muestra depende del rol guardado
# en la sesión (nombre_cargo de la tabla roles).
# ------------------------------------------------------------
@app.route("/dashboard")
@login_requerido
def dashboard():
    empresa = empresa_actual()
    id_empresa = empresa["id_empresa"] if empresa else None
    diagnostico = diagnostico_actual(id_empresa)
    estrategia = estrategia_actual(id_empresa)
    metricas = consulta_unica(
        """SELECT
              (SELECT COUNT(*) FROM empresas WHERE id_usuario = %s) AS empresas_activas,
              (SELECT COUNT(*) FROM estrategias e JOIN empresas em ON em.id_empresa = e.id_empresa WHERE em.id_usuario = %s) AS campanas,
              (SELECT COUNT(*) FROM contenidos c JOIN estrategias e ON e.id_estrategia = c.id_estrategia JOIN empresas em ON em.id_empresa = e.id_empresa WHERE em.id_usuario = %s) AS usos_ia,
              (SELECT ROUND(AVG(i.roi), 2) FROM indicadores_desempeno i JOIN calendarios_editoriales ce ON ce.id_calendario = i.id_calendario JOIN estrategias e ON e.id_estrategia = ce.id_estrategia JOIN empresas em ON em.id_empresa = e.id_empresa WHERE em.id_usuario = %s) AS roi""",
        (session["id_usuario"],) * 4,
    )
    actividad = consulta_varias(
        """SELECT 'Estrategia creada' AS accion, e.fecha_generacion AS fecha FROM estrategias e JOIN empresas em ON em.id_empresa = e.id_empresa WHERE em.id_usuario = %s
           UNION ALL SELECT CONCAT('Contenido ', c.tipo, ' generado') AS accion, c.fecha_generacion AS fecha FROM contenidos c JOIN estrategias e ON e.id_estrategia = c.id_estrategia JOIN empresas em ON em.id_empresa = e.id_empresa WHERE em.id_usuario = %s
           ORDER BY fecha DESC LIMIT 3""",
        (session["id_usuario"], session["id_usuario"]),
    )
    return render_template(
        "dashboard.html",
        empresa=empresa, diagnostico=diagnostico, estrategia=estrategia,
        metricas=metricas, actividad=actividad,
    )


@app.route("/diagnostico", methods=["GET", "POST"])
@login_requerido
def diagnostico():
    empresa = empresa_actual()
    if request.method == "POST":
        respuestas = {
            "presencia": int(request.form.get("presencia", 62)),
            "datos": int(request.form.get("datos", 54)),
            "contenido": int(request.form.get("contenido", 68)),
            "conversion": int(request.form.get("conversion", 48)),
        }
        puntaje = round(sum(respuestas.values()) / len(respuestas))
        if puntaje >= 76:
            nivel, mensaje = "Avanzado", "Tienes una base sólida para escalar con experimentación y automatización."
        elif puntaje >= 51:
            nivel, mensaje = "En desarrollo", "Ya hay avances. Priorizamos conectar datos, contenido y conversión."
        else:
            nivel, mensaje = "Fundamentos", "Empezamos por ordenar los canales que sostienen tu crecimiento."
        negocio = request.form.get("negocio", "").strip()
        sector = request.form.get("sector", "").strip()
        propuesta = request.form.get("propuesta", "").strip()
        objetivo = request.form.get("objetivo", "").strip()
        presupuesto = request.form.get("presupuesto", "0").replace("$", "").replace("COP", "").replace(".", "").replace(",", "").strip() or "0"
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                if empresa:
                    cursor.execute("UPDATE empresas SET nombre_empresa=%s, sector=%s, propuesta_valor=%s, objetivo=%s, presupuesto=%s WHERE id_empresa=%s", (negocio, sector, propuesta, objetivo, presupuesto, empresa["id_empresa"]))
                    id_empresa = empresa["id_empresa"]
                else:
                    cursor.execute("INSERT INTO empresas (id_usuario, nombre_empresa, sector, propuesta_valor, objetivo, presupuesto, fecha_creacion) VALUES (%s,%s,%s,%s,%s,%s,CURDATE())", (session["id_usuario"], negocio, sector, propuesta, objetivo, presupuesto))
                    id_empresa = cursor.lastrowid
                cursor.execute("INSERT INTO formularios_diagnostico (id_empresa, respuestas, fecha_completado) VALUES (%s,%s,NOW())", (id_empresa, json.dumps(respuestas)))
                id_formulario = cursor.lastrowid
                cursor.execute("INSERT INTO madurez_digital (id_formulario, nivel, puntaje) VALUES (%s,%s,%s)", (id_formulario, nivel, puntaje))
            conexion.commit()
        finally:
            conexion.close()
        flash("Diagnóstico guardado en la base de datos.", "exito")
        return redirect(url_for("diagnostico"))
    return render_template("diagnostico.html", empresa=empresa, diagnostico=diagnostico_actual(empresa["id_empresa"] if empresa else None))


@app.route("/estrategia", methods=["GET", "POST"])
@login_requerido
def estrategia():
    empresa = empresa_actual()
    if not empresa:
        flash("Primero registra el diagnóstico de tu empresa.", "error")
        return redirect(url_for("diagnostico"))
    if request.method == "POST":
        canales = request.form.getlist("canales")
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("INSERT INTO estrategias (id_empresa, segmentacion, propuesta_valor, canales_recomendados, tono_comunicacion, fecha_generacion, estado) VALUES (%s,%s,%s,%s,%s,NOW(),'activa')", (empresa["id_empresa"], request.form.get("segmentacion", "").strip(), request.form.get("propuesta_valor", "").strip(), json.dumps(canales), request.form.get("tono", "Cercano").strip()))
                id_estrategia = cursor.lastrowid
                fases = [{"nombre": "Construir identidad visual coherente", "tipo": "Orgánico", "estado": "Pendiente"}, {"nombre": "Generar contenido consistente", "tipo": "Orgánico", "estado": "Pendiente"}, {"nombre": "Activar pauta con audiencia caliente", "tipo": "Pauta", "estado": "Pendiente"}]
                presupuesto = [{"nombre": "Contenido orgánico", "porcentaje": 45}, {"nombre": "Comunidad", "porcentaje": 30}, {"nombre": "Pauta digital", "porcentaje": 25}]
                cursor.execute("INSERT INTO hojas_ruta (id_estrategia, fases, distribucion_presupuesto) VALUES (%s,%s,%s)", (id_estrategia, json.dumps(fases), json.dumps(presupuesto)))
            conexion.commit()
        finally:
            conexion.close()
        flash("Estrategia creada y guardada en la base de datos.", "exito")
        return redirect(url_for("estrategia"))
    estrategia_guardada = estrategia_actual(empresa["id_empresa"])
    hoja_ruta = consulta_unica("SELECT * FROM hojas_ruta WHERE id_estrategia=%s", (estrategia_guardada["id_estrategia"],)) if estrategia_guardada else None
    if hoja_ruta:
        for campo in ("fases", "distribucion_presupuesto"):
            hoja_ruta[campo] = json.loads(hoja_ruta[campo]) if isinstance(hoja_ruta[campo], str) else hoja_ruta[campo]
    return render_template("estrategia.html", empresa=empresa, estrategia=estrategia_guardada, diagnostico=diagnostico_actual(empresa["id_empresa"]), hoja_ruta=hoja_ruta)


@app.route("/reportes")
@login_requerido
def reportes():
    empresa = empresa_actual()
    if not empresa:
        flash("No hay una empresa registrada para mostrar reportes.", "error")
        return redirect(url_for("diagnostico"))
    indicadores = consulta_varias(
        """SELECT ce.fecha, i.* FROM indicadores_desempeno i JOIN calendarios_editoriales ce ON ce.id_calendario=i.id_calendario
           JOIN estrategias e ON e.id_estrategia=ce.id_estrategia WHERE e.id_empresa=%s ORDER BY ce.fecha DESC LIMIT 4""",
        (empresa["id_empresa"],),
    )
    resumen = consulta_unica(
        """SELECT SUM(i.alcance) alcance, SUM(i.impresiones) impresiones, SUM(i.leads) leads, SUM(i.conversiones) conversiones,
                  AVG(i.roi) roi, AVG(i.cpc) cpc, AVG(i.engagement) engagement, SUM(i.gasto_real) gasto
           FROM indicadores_desempeno i JOIN calendarios_editoriales ce ON ce.id_calendario=i.id_calendario
           JOIN estrategias e ON e.id_estrategia=ce.id_estrategia WHERE e.id_empresa=%s""",
        (empresa["id_empresa"],),
    )
    return render_template(
        "reportes.html",
        empresa=empresa, estrategia=estrategia_actual(empresa["id_empresa"]), indicadores=indicadores, resumen=resumen,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
