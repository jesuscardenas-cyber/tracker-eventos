import logging
import os

import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def get_db_config():
    """Obtiene la configuración de conexión desde st.secrets o variables de entorno."""
    if "postgres" in st.secrets:
        return {
            "host": st.secrets["postgres"]["host"],
            "port": st.secrets["postgres"]["port"],
            "dbname": st.secrets["postgres"]["dbname"],
            "user": st.secrets["postgres"]["user"],
            "password": st.secrets["postgres"]["password"],
        }
    else:
        # Fallback a variables de entorno si no existe secrets.toml
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "dbname": os.getenv("DB_NAME", "postgres"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASS", ""),
        }


def get_connection():
    config = get_db_config()

    # Se pasan los parámetros explícitos y client_encoding en UTF-8
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=config["user"],
        password=config["password"],
        cursor_factory=RealDictCursor,
        client_encoding="utf8",
    )


def init_db():
    """Crea las tablas e índices necesarios en PostgreSQL si no existen."""
    ddl = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        rol VARCHAR(50) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS equipo (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        puesto VARCHAR(50) NOT NULL,
        area VARCHAR(50) NOT NULL,
        jefe_id INT REFERENCES equipo(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS areas_solicitantes (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS catalogo (
        id SERIAL PRIMARY KEY,
        evento VARCHAR(150) NOT NULL,
        area_solicitante VARCHAR(100) NOT NULL,
        horas_estimadas INT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS eventos (
        id_ev VARCHAR(50) PRIMARY KEY,
        evento VARCHAR(150) NOT NULL,
        responsable VARCHAR(100) NOT NULL,
        estado VARCHAR(50) NOT NULL,
        area_solicitante VARCHAR(100) NOT NULL,
        fecha VARCHAR(20) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tareas (
        id_tarea VARCHAR(50) PRIMARY KEY,
        id_ev VARCHAR(50) REFERENCES eventos(id_ev) ON DELETE CASCADE,
        desc_tarea TEXT NOT NULL,
        hrs NUMERIC NOT NULL,
        quien VARCHAR(100) NOT NULL,
        estado VARCHAR(50) NOT NULL,
        prioridad VARCHAR(20) NOT NULL,
        fecha_asignacion VARCHAR(20) NOT NULL,
        fecha_limite VARCHAR(20) NOT NULL,
        evento VARCHAR(150) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS gastos (
        id VARCHAR(50) PRIMARY KEY,
        id_ev VARCHAR(50) REFERENCES eventos(id_ev) ON DELETE CASCADE,
        evento VARCHAR(150) NOT NULL,
        concepto VARCHAR(200) NOT NULL,
        importe NUMERIC NOT NULL,
        fecha VARCHAR(20) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS historial_tareas (
        id SERIAL PRIMARY KEY,
        id_tarea VARCHAR(50),
        evento VARCHAR(150),
        responsable VARCHAR(100),
        estado VARCHAR(50),
        fecha VARCHAR(20),
        horas NUMERIC
    );

    CREATE TABLE IF NOT EXISTS historial_eventos (
        id SERIAL PRIMARY KEY,
        id_ev VARCHAR(50),
        evento VARCHAR(150),
        responsable VARCHAR(100),
        estado VARCHAR(50),
        fecha VARCHAR(20)
    );

    CREATE TABLE IF NOT EXISTS historial_gastos (
        id SERIAL PRIMARY KEY,
        evento VARCHAR(150),
        concepto VARCHAR(200),
        importe NUMERIC,
        fecha VARCHAR(20)
    );
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
    except Exception:
        logger.exception("Error al inicializar las tablas en PostgreSQL")


# ================= AUTH & USUARIOS =================


def login(username, password):
    sql = "SELECT username, nombre, rol FROM usuarios WHERE username = %s AND password = %s;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (username, password))
        res = cur.fetchone()
        return dict(res) if res else None


def crear_usuario(username, password, nombre, rol, area="Global"):
    with get_connection() as conn, conn.cursor() as cur:
        sql = """
            INSERT INTO usuarios (username, password, nombre, rol, area)
            VALUES (%s, %s, %s, %s, %s)
        """
        cur.execute(sql, (username, password, nombre, rol, area))
        conn.commit()


def obtener_usuario(username):
    with get_connection() as conn, conn.cursor() as cur:
        sql = """
            SELECT id, username, nombre, rol, rol AS puesto, COALESCE(area, 'Global') AS area 
            FROM usuarios 
            WHERE username = %s
        """
        cur.execute(sql, (username,))
        return cur.fetchone()


def obtener_usuarios():
    sql = "SELECT id, username, nombre, rol, rol AS puesto, COALESCE(area, 'Global') AS area FROM usuarios ORDER BY id ASC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


# ================= EQUIPO =================


def insertar_miembro(nombre, puesto, area, jefe_id=None):
    sql = "INSERT INTO equipo (nombre, puesto, area, jefe_id) VALUES (%s, %s, %s, %s);"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (nombre, puesto, area, jefe_id))
        conn.commit()


def obtener_nombres_equipo():
    sql = "SELECT nombre FROM equipo ORDER BY nombre ASC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [r["nombre"] for r in cur.fetchall()]


def obtener_equipo_detalle():
    sql = "SELECT id, nombre, puesto, area, jefe_id FROM equipo ORDER BY id ASC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def obtener_miembro_por_username(username):
    sql = """
        SELECT e.id, e.nombre, e.puesto, e.area, e.jefe_id 
        FROM equipo e 
        JOIN usuarios u ON u.nombre = e.nombre 
        WHERE u.username = %s;
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (username,))
        res = cur.fetchone()
        return (
            dict(res)
            if res
            else {"nombre": username, "puesto": "Indefinido", "area": "Global"}
        )


def obtener_areas_equipo():
    with get_connection() as conn, conn.cursor() as cur:
        # Consultamos las áreas registradas en la tabla de miembros o catálogo,
        # asegurándonos de filtrar 'Global' para puestos operativos
        sql = """
            SELECT DISTINCT area 
            FROM equipo 
            WHERE area IS NOT NULL AND area != 'Global' AND area != ''
        """
        cur.execute(sql)
        registros = cur.fetchall()

        areas = [r["area"] for r in registros]

        # Si aún no hay áreas registradas en la base de datos, asignamos las predeterminadas
        if not areas:
            areas = ["Diseño", "Eventos"]

        return areas


def obtener_miembros_asignables(rol_usuario, area_usuario, nombre_usuario):
    with get_connection() as conn, conn.cursor() as cur:
        # Administradores y Puestos ejecutivos ven a todo el personal
        if rol_usuario in ["Admin", "Gerente", "Subgerente"]:
            sql = (
                "SELECT id, nombre, rol AS puesto, COALESCE(area, 'Global') AS"
                " area FROM usuarios ORDER BY nombre ASC"
            )
            cur.execute(sql)
            return cur.fetchall()

        # Jefe: ve a Jefes, Coordinadores y Auxiliares de SU MISMA ÁREA
        if rol_usuario == "Jefe":
            sql = """
                SELECT id, nombre, rol AS puesto, COALESCE(area, 'Global') AS area 
                FROM usuarios 
                WHERE area = %s AND rol IN ('Jefe', 'Coordinador', 'Auxiliar')
                ORDER BY nombre ASC
            """
            cur.execute(sql, (area_usuario,))

        # Coordinador: ve a Coordinadores y Auxiliares de SU MISMA ÁREA
        elif rol_usuario == "Coordinador":
            sql = """
                SELECT id, nombre, rol AS puesto, COALESCE(area, 'Global') AS area 
                FROM usuarios 
                WHERE area = %s AND rol IN ('Coordinador', 'Auxiliar')
                ORDER BY nombre ASC
            """
            cur.execute(sql, (area_usuario,))

        # Auxiliar: solo a sí mismo
        elif rol_usuario == "Auxiliar":
            sql = """
                SELECT id, nombre, rol AS puesto, COALESCE(area, 'Global') AS area 
                FROM usuarios 
                WHERE nombre = %s
            """
            cur.execute(sql, (nombre_usuario,))
        else:
            return []

        return cur.fetchall()


# ================= ÁREAS SOLICITANTES & CATÁLOGO =================


def insertar_area_solicitante(nombre):
    sql = "INSERT INTO areas_solicitantes (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (nombre,))
        conn.commit()


def obtener_areas_solicitantes():
    sql = "SELECT nombre FROM areas_solicitantes ORDER BY nombre ASC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [r["nombre"] for r in cur.fetchall()]


def insertar_catalogo(evento, area_solicitante, horas_totales):
    with get_connection() as conn, conn.cursor() as cur:
        sql = """
            INSERT INTO catalogo (evento, area_solicitante, horas_totales)
            VALUES (%s, %s, %s)
        """
        cur.execute(sql, (evento, area_solicitante, horas_totales))
        conn.commit()


def obtener_catalogo():
    with get_connection() as conn, conn.cursor() as cur:
        sql = """
            SELECT evento, area_solicitante, horas_totales AS horas_estimadas 
            FROM catalogo
        """
        cur.execute(sql)
        return cur.fetchall()


# ================= EVENTOS =================


def insertar_evento(id_ev, evento, responsable, estado, area_solicitante, fecha):
    sql_ev = """
        INSERT INTO eventos (id_ev, evento, responsable, estado, area_solicitante, fecha) 
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    sql_hist = """
        INSERT INTO historial_eventos (id_ev, evento, responsable, estado, fecha)
        VALUES (%s, %s, %s, %s, %s);
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql_ev, (id_ev, evento, responsable, estado, area_solicitante, fecha)
        )
        cur.execute(sql_hist, (id_ev, evento, responsable, estado, fecha))
        conn.commit()


def obtener_eventos():
    sql = "SELECT id_ev, evento, responsable, estado, area_solicitante, fecha FROM eventos ORDER BY fecha DESC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        registros = [dict(row) for row in cur.fetchall()]
        return {"registros": registros}


# ================= TAREAS =================


def insertar_tarea(tarea):
    with get_connection() as conn, conn.cursor() as cur:
        # Reemplazamos desc_tarea por "desc"
        sql_t = """
            INSERT INTO tareas (
                id_tarea, id_ev, "desc", hrs, quien, estado, 
                prioridad, fecha_asignacion, fecha_limite
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(
            sql_t,
            (
                tarea["id_tarea"],
                tarea["id_ev"],
                tarea["desc"],
                tarea["hrs"],
                tarea["quien"],
                tarea["estado"],
                tarea.get("prioridad", "Media"),
                tarea["fecha_asignacion"],
                tarea["fecha_limite"],
            ),
        )
        conn.commit()


def obtener_tareas_por_evento(id_ev):
    with get_connection() as conn, conn.cursor() as cur:
        sql = """
            SELECT id_tarea, id_ev, "desc", hrs, quien, estado, prioridad, fecha_asignacion, fecha_limite
            FROM tareas
            WHERE id_ev = %s
        """
        cur.execute(sql, (id_ev,))
        return cur.fetchall()


def actualizar_estado_tarea(id_tarea, nuevo_estado):
    with get_connection() as conn, conn.cursor() as cur:
        # 1. Obtenemos los datos de la tarea haciendo JOIN con eventos para traer el nombre del evento
        sql_tarea = """
            SELECT e.evento, t.quien, t.hrs 
            FROM tareas t
            JOIN eventos e ON t.id_ev = e.id_ev
            WHERE t.id_tarea = %s
        """
        cur.execute(sql_tarea, (id_tarea,))
        tarea = cur.fetchone()

        # 2. Actualizamos el estado de la tarea
        sql_update = """
            UPDATE tareas 
            SET estado = %s 
            WHERE id_tarea = %s
        """
        cur.execute(sql_update, (nuevo_estado, id_tarea))
        conn.commit()

        return tarea


# ================= GASTOS =================


def insertar_gasto(gasto):
    sql_g = "INSERT INTO gastos (id, id_ev, evento, concepto, importe, fecha) VALUES (%s, %s, %s, %s, %s, %s);"
    sql_h = "INSERT INTO historial_gastos (evento, concepto, importe, fecha) VALUES (%s, %s, %s, %s);"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql_g,
                (
                    gasto["id"],
                    gasto["id_ev"],
                    gasto["evento"],
                    gasto["concepto"],
                    gasto["importe"],
                    gasto["fecha"],
                ),
            )
            cur.execute(
                sql_h,
                (gasto["evento"], gasto["concepto"], gasto["importe"], gasto["fecha"]),
            )
        conn.commit()


def obtener_gastos_por_evento(id_ev):
    sql = "SELECT id, id_ev, evento, concepto, importe, fecha FROM gastos WHERE id_ev = %s ORDER BY fecha DESC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (id_ev,))
        return [dict(row) for row in cur.fetchall()]


# ================= HISTORIALES =================


def obtener_historial(nombre_tabla):
    tablas_permitidas = ["historial_tareas", "historial_eventos", "historial_gastos"]
    if nombre_tabla not in tablas_permitidas:
        return []

    sql = f"SELECT * FROM {nombre_tabla} ORDER BY id DESC;"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def obtener_historial_eventos_live():
    sql = """
        SELECT 
            e.evento AS "Evento",
            e.responsable AS "Responsable",
            COALESCE(SUM(t.hrs), 0) AS "Horas Totales",
            COALESCE(SUM(g.importe), 0) AS "Costo Total"
        FROM eventos e
        LEFT JOIN tareas t ON e.id_ev = t.id_ev
        LEFT JOIN gastos g ON e.id_ev = g.id_ev
        GROUP BY e.id_ev, e.evento, e.responsable
        ORDER BY e.fecha DESC;
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]
