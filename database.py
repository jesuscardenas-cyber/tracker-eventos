import sqlite3


DB = "data.db"


def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------ INIT ------------------


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS eventos (
        id_ev TEXT PRIMARY KEY,
        evento TEXT,
        responsable TEXT,
        estado TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tareas (
        id_tarea TEXT PRIMARY KEY,
        id_ev TEXT,
        desc TEXT,
        hrs INTEGER,
        quien TEXT,
        asignado_por TEXT,
        estado TEXT,
        prioridad TEXT,
        fecha_asignacion TEXT,
        fecha_limite TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS gastos (
        id TEXT PRIMARY KEY,
        id_ev TEXT,
        evento TEXT,
        concepto TEXT,
        importe REAL,
        fecha TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS equipo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        puesto TEXT,
        area TEXT
    )
    """)
    c.execute("PRAGMA table_info(equipo)")
    columnas = [col[1] for col in c.fetchall()]

    if "jefe_id" not in columnas:
        c.execute("ALTER TABLE equipo ADD COLUMN jefe_id INTEGER")
    c.execute("""
    CREATE TABLE IF NOT EXISTS catalogo (
        evento TEXT PRIMARY KEY,
        area TEXT,
        horas_totales INTEGER
    )
    """)

    # NUEVA TABLA AREAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )
    """)
    # ------------------ HISTORIAL ------------------

    c.execute("""
    CREATE TABLE IF NOT EXISTS historial_tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_tarea TEXT,
        evento TEXT,
        responsable TEXT,
        estado TEXT,
        fecha TEXT,
        horas REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS historial_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_evento TEXT,
        evento TEXT,
        responsable TEXT,
        estado TEXT,
        fecha TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS historial_gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evento TEXT,
        concepto TEXT,
        importe REAL,
        fecha TEXT
    )
    """)
    # -------- AREAS INTERNAS (EQUIPO) --------
    c.execute("""
    CREATE TABLE IF NOT EXISTS areas_equipo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )
    """)

    # -------- AREAS SOLICITANTES --------
    c.execute("""
    CREATE TABLE IF NOT EXISTS areas_solicitantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        nombre TEXT,
        rol TEXT
    )
    """)

    # ADMIN DEFAULT
    c.execute(
        """
        INSERT OR IGNORE INTO usuarios
        (username, password, nombre, rol)
        VALUES (?, ?, ?, ?)
        """,
        (
            "jesus.cardenas",
            "40115",
            "Jesus Cardenas",
            "Admin",
        ),
    )
    # Insertar valores por defecto
    c.execute("INSERT OR IGNORE INTO areas_equipo (nombre) VALUES ('Diseño')")
    c.execute("INSERT OR IGNORE INTO areas_equipo (nombre) VALUES ('Eventos')")

    try:
        c.execute("ALTER TABLE eventos ADD COLUMN area_solicitante TEXT")
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE equipo ADD COLUMN nivel TEXT")
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE equipo ADD COLUMN jefe_id INTEGER")
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE tareas ADD COLUMN asignado_por TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ------------------ HISTORIAL ------------------


def log_tarea(conn, t):
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO historial_tareas
        (id_tarea, evento, responsable, estado, fecha, horas)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            t["id_tarea"],
            t["evento"],
            t["quien"],
            t["estado"],
            t["fecha_asignacion"],
            t["hrs"],
        ),
    )

    conn.commit()


def log_evento(e):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
    INSERT INTO historial_eventos
    (id_ev, evento, responsable, estado, fecha)
    VALUES (?, ?, ?, ?, ?)
    """,
        (e["id_ev"], e["evento"], e["responsable"], e["estado"], e["fecha"]),
    )

    conn.commit()
    conn.close()


def log_gasto(g):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
    INSERT INTO historial_gastos
    (evento, concepto, importe, fecha)
    VALUES (?, ?, ?, ?)
    """,
        (g["evento"], g["concepto"], g["importe"], g["fecha"]),
    )

    conn.commit()
    conn.close()


def obtener_historial(tabla):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT * FROM {tabla}")
    rows = c.fetchall()
    conn.close()
    return rows


# ------------------ AREAS ------------------


def insertar_area(nombre):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO areas (nombre) VALUES (?)", (nombre,))
    conn.commit()
    conn.close()


def obtener_areas():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nombre FROM areas")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


# ------------------ EVENTOS ------------------


def insertar_evento(id_ev, evento, responsable, estado, area_solicitante):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        """
    INSERT INTO eventos (id_ev, evento, responsable, estado, area_solicitante)
    VALUES (?, ?, ?, ?, ?)
    """,
        (id_ev, evento, responsable, estado, area_solicitante),
    )

    conn.commit()
    conn.close()


def obtener_eventos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM eventos")
    rows = c.fetchall()
    conn.close()

    return {
        "registros": [
            {"id_ev": r[0], "evento": r[1], "responsable": r[2], "estado_evento": r[3]}
            for r in rows
        ]
    }


# ------------------ TAREAS ------------------


def insertar_tarea(t):
    with sqlite3.connect(DB, timeout=10) as conn:
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO tareas (
                id_tarea,
                id_ev,
                desc,
                hrs,
                quien,
                estado,
                prioridad,
                fecha_asignacion,
                fecha_limite,
                asignado_por
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t["id_tarea"],
                t["id_ev"],
                t["desc"],
                t["hrs"],
                t["quien"],
                t["estado"],
                t["prioridad"],
                t["fecha_asignacion"],
                t["fecha_limite"],
                t.get("asignado_por"),  # 👈 clave
            ),
        )

        log_tarea(conn, t)
        conn.commit()


def obtener_tareas_por_evento(id_ev):
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    c = conn.cursor()

    c.execute(
        """
        SELECT 
            id_tarea,
            id_ev,
            desc,
            hrs,
            quien,
            estado,
            prioridad,
            fecha_asignacion,
            fecha_limite,
            asignado_por
        FROM tareas
        WHERE id_ev = ?
        """,
        (id_ev,),
    )

    rows = c.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def actualizar_estado_tarea(id_tarea, estado):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE tareas SET estado = ? WHERE id_tarea = ?", (estado, id_tarea))
    conn.commit()
    conn.close()


# ------------------ GASTOS ------------------


def insertar_gasto(g):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
    INSERT INTO gastos VALUES (?, ?, ?, ?, ?, ?)
    """,
        (g["id"], g["id_ev"], g["evento"], g["concepto"], g["importe"], g["fecha"]),
    )
    log_gasto(
        {
            "evento": g["evento"],
            "concepto": g["concepto"],
            "importe": g["importe"],
            "fecha": g["fecha"],
        }
    )

    conn.commit()
    conn.close()


def obtener_gastos_por_evento(id_ev):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM gastos WHERE id_ev = ?", (id_ev,))
    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "id_ev": r[1],
            "evento": r[2],
            "concepto": r[3],
            "importe": r[4],
            "fecha": r[5],
        }
        for r in rows
    ]


# ------------------ EQUIPO ------------------
def generar_nivel(area, puesto):
    # PREFIJO
    if area.lower() == "eventos":
        pref = "E"
    elif area.lower() == "diseño":
        pref = "D"
    elif area.lower() == "global":
        pref = "G"
    else:
        pref = "X"

    # NIVEL
    mapa = {"Jefe": "1", "Coordinador": "2", "Auxiliar": "3"}

    nivel = mapa.get(puesto, "9")

    return f"{pref}{nivel}"


def insertar_miembro(nombre, puesto, area, jefe_id=None):
    conn = get_conn()
    c = conn.cursor()

    nivel = generar_nivel(area, puesto)

    c.execute(
        """
    INSERT INTO equipo (nombre, puesto, area, nivel, jefe_id)
    VALUES (?, ?, ?, ?, ?)
    """,
        (nombre, puesto, area, nivel, jefe_id),
    )

    conn.commit()
    conn.close()


def obtener_equipo_detalle():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute("SELECT id, nombre, puesto, area, jefe_id FROM equipo")

    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "nombre": r[1],
            "puesto": r[2],
            "area": r[3],
            "jefe_id": r[4],
        }
        for r in rows
    ]


def obtener_nombres_equipo():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nombre FROM equipo")
    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]


# ------------------ CATÁLOGO ------------------


def obtener_catalogo():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM catalogo")
    rows = c.fetchall()
    conn.close()

    return [{"evento": r[0], "area": r[1], "horas_totales": r[2]} for r in rows]


def insertar_catalogo(evento, area, horas):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO catalogo VALUES (?, ?, ?)", (evento, area, horas))
    conn.commit()
    conn.close()


def actualizar_tarea(id_tarea, quien, hrs, fecha_limite, estado, asignado_por=None):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        UPDATE tareas
        SET quien = ?, hrs = ?, fecha_limite = ?, estado = ?
        WHERE id_tarea = ?
    """,
        (quien, hrs, fecha_limite, estado, id_tarea),
    )

    conn.commit()
    conn.close()


def obtener_areas_equipo():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT nombre FROM areas_equipo")
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data


def insertar_area_equipo(nombre):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO areas_equipo (nombre) VALUES (?)", (nombre,))
    conn.commit()
    conn.close()


def obtener_areas_solicitantes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT nombre FROM areas_solicitantes")
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data


def insertar_area_solicitante(nombre):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO areas_solicitantes (nombre) VALUES (?)", (nombre,))
    conn.commit()
    conn.close()


def obtener_puesto(nombre):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute("SELECT puesto FROM equipo WHERE nombre = ?", (nombre,))
    res = c.fetchone()

    conn.close()
    return res[0] if res else None


def obtener_miembro(nombre):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute(
        """
        SELECT id, nombre, puesto, area, jefe_id
        FROM equipo
        WHERE nombre = ?
    """,
        (nombre,),
    )

    res = c.fetchone()
    conn.close()

    if res:
        return {
            "id": res[0],
            "nombre": res[1],
            "puesto": res[2],
            "area": res[3],
            "jefe_id": res[4],
        }

    return None


def obtener_usuario(nombre):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        SELECT id, nombre, puesto, area, jefe_id
        FROM equipo
        WHERE nombre = ?
        """,
        (nombre,),
    )

    row = c.fetchone()

    conn.close()

    if row:
        return {
            "id": row[0],
            "nombre": row[1],
            "puesto": row[2],
            "area": row[3],
            "jefe_id": row[4],
        }

    return None


# ------------------ USUARIOS ------------------


def crear_usuario(username, password, nombre, rol):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO usuarios (username, password, nombre, rol)
        VALUES (?, ?, ?, ?)
        """,
        (username, password, nombre, rol),
    )

    conn.commit()
    conn.close()


def obtener_usuarios(username):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        SELECT id, username, nombre, rol
        FROM usuarios
        """
    )

    rows = c.fetchall()

    conn.close()

    return [
        {
            "id": r[0],
            "username": r[1],
            "nombre": r[2],
            "rol": r[3],
        }
        for r in rows
    ]


def login(username, password):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
    SELECT username, nombre, rol
    FROM usuarios
    WHERE username = ? AND password = ?
    """,
        (username, password),
    )

    row = c.fetchone()

    conn.close()

    if row:
        return {"username": row[0], "nombre": row[1], "rol": row[2]}

    return None


def obtener_personas_asignables(usuario):
    if not usuario:
        return []

    puesto = usuario["puesto"]
    nombre = usuario["nombre"]

    if puesto in ["Gerente", "Subgerente"]:
        return []

    if puesto in ["Jefe", "Coordinador"]:
        return obtener_subordinados(nombre)

    return []


def filtrar_tareas_por_usuario(usuario, tareas):

    # Gerente/Subgerente ven todo
    if usuario["puesto"] in ["Gerente", "Subgerente"]:
        return tareas

    # Operativos ven su línea
    subs = obtener_subordinados(usuario["id"])
    nombres_validos = [usuario["nombre"]] + [s["nombre"] for s in subs]

    return [t for t in tareas if t["quien"] in nombres_validos]


def obtener_subordinados(nombre):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT id FROM equipo WHERE nombre = ?", (nombre,))
    row = c.fetchone()

    if not row:
        conn.close()
        return []

    jefe_id = row[0]

    c.execute("SELECT nombre FROM equipo WHERE jefe_id = ?", (jefe_id,))
    data = c.fetchall()

    conn.close()

    return [r[0] for r in data]
