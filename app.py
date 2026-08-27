import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

# ================= CONFIGURACIÓN DE PÁGINA (SIEMPRE PRIMERO) =================
st.set_page_config(layout="wide", page_title="Gestor SD")

logger = logging.getLogger(__name__)

from constantes import EstadoTarea, Labels, Mensajes
from database import (
    actualizar_estado_tarea,
    crear_usuario,
    init_db,
    insertar_area_solicitante,
    insertar_catalogo,
    insertar_evento,
    insertar_gasto,
    insertar_miembro,
    insertar_tarea,
    login,
    obtener_areas_equipo,
    obtener_areas_solicitantes,
    obtener_catalogo,
    obtener_equipo_detalle,
    obtener_eventos,
    obtener_gastos_por_evento,
    obtener_historial,
    obtener_historial_eventos_live,
    obtener_miembro_por_username,
    obtener_miembros_asignables,
    obtener_nombres_equipo,
    obtener_tareas_por_evento,
    obtener_usuario,
)

CONTRASENA_LABEL = "Contraseña"
CONTRASENA_FIELD_TYPE = "password"
HORAS_TOTALES_COLUMN = "Horas Totales"

# Inicialización del pool/motor de la base de datos
init_db()

# ================= AUTHENTICATION =================
if "auth" not in st.session_state:
    st.session_state.auth = False

if "user" not in st.session_state:
    st.session_state.user = None

if "nombre" not in st.session_state:
    st.session_state.nombre = ""

if "rol" not in st.session_state:
    st.session_state.rol = ""

if not st.session_state.auth:
    st.title("🔐 Login")

    username = st.text_input("Usuario").strip()
    contrasena_input = st.text_input(
        CONTRASENA_LABEL, type=CONTRASENA_FIELD_TYPE
    ).strip()

    if st.button("Ingresar"):
        user = login(username, contrasena_input)

        if user:
            st.session_state.auth = True
            st.session_state.user = user["username"]
            st.session_state.nombre = user["nombre"]
            st.session_state.rol = user["rol"]
            st.rerun()
        else:
            st.error("Credenciales inválidas")

    st.stop()

# ================= SIDEBAR & USUARIO AUTENTICADO =================
with st.sidebar:
    st.write(f"👤 {st.session_state.nombre}")
    st.write(f"🔑 {st.session_state.rol}")

    if st.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()

if st.session_state.rol == "Admin":
    usuario = {
        "nombre": "ADMIN",
        "puesto": "Admin",
        "area": "Global",
    }
else:
    usuario = obtener_miembro_por_username(st.session_state.user)


# ================= FUNCIONES AUXILIARES =================
def calcular_dias_habiles(fecha_inicio, fecha_fin):
    dias = 0
    actual = fecha_inicio

    while actual < fecha_fin:
        if actual.weekday() < 5:
            dias += 1
        actual += timedelta(days=1)

    return max(dias, 1)


def calcular_carga_dia(nombre, eventos):
    hoy = datetime.now(timezone.utc).date()
    carga = 0

    for ev in eventos:
        for t in ev.get("tareas", []):
            if t["quien"] != nombre:
                continue
            if t["estado"] == EstadoTarea.ENTREGADO.value:
                continue

            try:
                f_asig = date.fromisoformat(t["fecha_asignacion"])
                f_lim = date.fromisoformat(t["fecha_limite"])
                dias = calcular_dias_habiles(f_asig, f_lim)

                if f_asig <= hoy < f_lim:
                    carga += t["hrs"] / dias

            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                logger.exception("Error al calcular la carga de la tarea")

    return round(carga, 2)


# ================= DATA INICIAL =================
eventos_data = obtener_eventos()

for ev in eventos_data.get("registros", []):
    ev["tareas"] = obtener_tareas_por_evento(ev["id_ev"])
    ev["gastos"] = obtener_gastos_por_evento(ev["id_ev"])

# ================= VISTAS / TABS =================
st.title("🚀 Gestor de carga de trabajo SD")

tabs = st.tabs(
    [
        "📊 Dashboard",
        "➕ Eventos",
        "📝 Tareas",
        "📊 Carga",
        "💰 Gastos",
        "⚙️ Administración",
        "📜 Historial",
        "📈 Histórico Ejecutivo",
    ]
)

# ------------------ DASHBOARD ------------------
with tabs[0]:
    st.header("📊 Dashboard Ejecutivo")
    eventos = eventos_data.get("registros", [])

    total_eventos = len(eventos)
    total_tareas = sum(len(ev.get("tareas", [])) for ev in eventos)
    tareas_finalizadas = sum(
        1
        for ev in eventos
        for t in ev.get("tareas", [])
        if t["estado"] == EstadoTarea.ENTREGADO.value
    )

    progreso = (tareas_finalizadas / total_tareas * 100) if total_tareas > 0 else 0
    total_gasto = sum(g["importe"] for ev in eventos for g in ev.get("gastos", []))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eventos activos", total_eventos)
    c2.metric("Tareas totales", total_tareas)
    c3.metric("Avance %", f"{progreso:.1f}%")
    c4.metric("Gasto total", f"${total_gasto:,.0f}")

    st.divider()

    st.subheader("🔥 Carga por persona")
    data = []
    nombres = obtener_nombres_equipo()

    for n in nombres:
        carga = calcular_carga_dia(n, eventos)
        data.append({"Persona": n, "Carga": carga})

    df = pd.DataFrame(data)

    if not df.empty:
        st.bar_chart(df.set_index("Persona"), height=300)

    st.divider()

    st.subheader("📌 Distribución de tareas")
    estados = {}
    for ev in eventos:
        for t in ev.get("tareas", []):
            estados[t["estado"]] = estados.get(t["estado"], 0) + 1

    if estados:
        df_estado = pd.DataFrame(
            {"Estado": list(estados.keys()), "Cantidad": list(estados.values())}
        )
        st.bar_chart(df_estado.set_index("Estado"), height=300)

    st.divider()

    st.subheader("🚨 Alertas de saturación")
    alertas = []
    for n in nombres:
        carga = calcular_carga_dia(n, eventos)
        if carga > 8:
            alertas.append((n, carga, "🔴 Saturado"))
        elif carga >= 6:
            alertas.append((n, carga, "🟡 Alto"))
        else:
            alertas.append((n, carga, "🟢 OK"))

    for nombre, carga, estado in alertas:
        if "🔴" in estado:
            st.error(f"{estado} - {nombre}: {carga}h/día")
        elif "🟡" in estado:
            st.warning(f"{estado} - {nombre}: {carga}h/día")
        else:
            st.success(f"{estado} - {nombre}: {carga}h/día")

    st.divider()

    st.subheader("⚠️ Eventos con riesgo")
    eventos_riesgo = []
    for ev in eventos:
        for t in ev.get("tareas", []):
            carga = calcular_carga_dia(t["quien"], eventos)
            if carga > 8:
                eventos_riesgo.append(ev["evento"])
                break

    if eventos_riesgo:
        for ev in set(eventos_riesgo):
            st.warning(f"⚠️ {ev} tiene miembros saturados")
    else:
        st.success("Todos los eventos están bajo control ✅")

# ------------------ EVENTOS ------------------
with tabs[1]:
    nombres = obtener_nombres_equipo()
    catalogo = obtener_catalogo()
    areas_sol = obtener_areas_solicitantes()

    eventos_dict = {e["evento"]: e for e in catalogo}

    with st.form("ev"):
        resp = st.selectbox("Responsable", nombres)
        ev = st.selectbox("Evento", list(eventos_dict.keys()))

        if areas_sol:
            area = st.selectbox("Área solicitante", areas_sol)
        else:
            area = None
            st.warning("No hay áreas disponibles")

        submitted = st.form_submit_button("Crear", disabled=not areas_sol)

        if submitted and area:
            insertar_evento(
                str(uuid.uuid4())[:8],
                ev,
                resp,
                EstadoTarea.EN_PROCESO.value,
                area,
                str(datetime.now(timezone.utc).date()),
            )
            st.success("Evento creado")
            st.rerun()

# ------------------ TAREAS ------------------
with tabs[2]:
    # Integrando la jerarquía filtrada de asignación:
    eventos = eventos_data.get("registros", [])
    opciones = [f"{e['evento']} ({e['responsable']})" for e in eventos]

    if not opciones:
        st.info("No hay eventos disponibles para gestionar tareas.")
    else:
        if "proyecto_idx" not in st.session_state:
            st.session_state.proyecto_idx = 0

        idx = st.selectbox(
            "Proyecto",
            range(len(opciones)),
            format_func=lambda x: opciones[x],
            key="proyecto_idx",
        )

        ev_sel = eventos[idx]

        usuario_actual = (
            obtener_usuario(st.session_state.user)
            if st.session_state.user != "ADMIN"
            else {"nombre": "ADMIN", "puesto": "Admin", "area": "Global"}
        )

        asignado_por = usuario_actual.get("nombre", "ADMIN")
        st.text_input("Asignado por", asignado_por, disabled=True)

        # ---------------------------------------------------------------------
        # REEMPLAZO IMPORTANTE: Filtrado de miembros según la Jerarquía de Área
        # ---------------------------------------------------------------------
        miembros_asignables = obtener_miembros_asignables(
            rol_usuario=st.session_state.rol,
            area_usuario=usuario_actual.get("area", "Global"),
            nombre_usuario=asignado_por,
        )

        personas = [m["nombre"] for m in miembros_asignables]

        if st.session_state.rol == "Admin" and "ADMIN" not in personas:
            personas.append("ADMIN")

        if not personas:
            st.warning(
                "No tienes miembros a tu cargo o en tu área para asignar tareas."
            )
            st.stop()

        asignado_a = st.selectbox("Asignar a", personas, key="resp")

        desc = st.text_input("Descripción", key="desc")
        hrs = st.number_input("Horas", min_value=1, key="hrs")
        fecha = st.date_input("Entrega", key="fecha")

        estado = st.selectbox(
            "Estatus",
            [
                EstadoTarea.EN_PROCESO.value,
                EstadoTarea.ENTREGADO.value,
                EstadoTarea.PAUSADO.value,
                EstadoTarea.REVISION.value,
                EstadoTarea.REVISION_FINAL.value,
            ],
            key="estado",
        )

        if st.button("Asignar", key="btn_tarea"):
            if (
                asignado_a == asignado_por
                and st.session_state.rol != "Admin"
                and usuario_actual.get("puesto") != "Auxiliar"
            ):
                # Nota: Los auxiliares sí se asignan a sí mismos, por eso permitimos el pase
                pass

            if not asignado_a:
                st.error("Selecciona a quién asignar")
                st.stop()

            carga_actual = calcular_carga_dia(asignado_a, eventos)
            dias = calcular_dias_habiles(datetime.now(timezone.utc).date(), fecha)
            carga_nueva = hrs / dias if dias > 0 else hrs

            if carga_actual + carga_nueva > 8:
                st.error("Excede capacidad diaria de 8 horas")
            else:
                insertar_tarea(
                    {
                        "id_tarea": str(uuid.uuid4())[:8],
                        "id_ev": ev_sel["id_ev"],
                        "desc": desc,
                        "hrs": hrs,
                        "quien": asignado_a,
                        "estado": estado,
                        "prioridad": "Media",
                        "fecha_asignacion": str(datetime.now(timezone.utc).date()),
                        "fecha_limite": str(fecha),
                        "evento": ev_sel["evento"],
                    }
                )
                st.success("Tarea asignada correctamente")
                st.rerun()

        st.divider()
        st.subheader("📋 Tablero de tareas")

        tareas = obtener_tareas_por_evento(ev_sel["id_ev"])
        lista_estados = [
            EstadoTarea.EN_PROCESO.value,
            EstadoTarea.PAUSADO.value,
            EstadoTarea.REVISION.value,
            EstadoTarea.REVISION_FINAL.value,
            EstadoTarea.ENTREGADO.value,
        ]

        cols = st.columns(len(lista_estados))

        for i, estado_col in enumerate(lista_estados):
            with cols[i]:
                st.markdown(f"### {estado_col}")
                tareas_estado = [t for t in tareas if t["estado"] == estado_col]

                for t in tareas_estado:
                    with st.container(border=True):
                        st.markdown(f"**{t['desc']}**")
                        st.caption(
                            f"👤 {t['quien']} | "
                            f"📌 {t.get('asignado_por', 'N/A')} | "
                            f"⏱️ {t['hrs']}h"
                        )

                        puede_editar = (
                            usuario_actual.get("puesto")
                            in ["Jefe", "Coordinador", "Subgerente", "Gerente"]
                            or st.session_state.rol == "Admin"
                        )
                        puede_cerrar = t["quien"] == usuario_actual.get("nombre")

                        if puede_editar:
                            nuevo_estado = st.selectbox(
                                "Mover a",
                                lista_estados,
                                index=lista_estados.index(t["estado"]),
                                key=f"move_{t['id_tarea']}",
                            )

                            if nuevo_estado != t["estado"]:
                                actualizar_estado_tarea(t["id_tarea"], nuevo_estado)
                                st.rerun()
                        else:
                            st.caption(f"Estado: {t['estado']}")

                        c1, c2 = st.columns(2)

                        if (
                            (puede_editar or puede_cerrar)
                            and t["estado"] != EstadoTarea.ENTREGADO.value
                            and c2.button("✅ Done", key=f"done_{t['id_tarea']}")
                        ):
                            actualizar_estado_tarea(
                                t["id_tarea"], EstadoTarea.ENTREGADO.value
                            )
                            st.rerun()

                        if not (puede_editar or puede_cerrar):
                            st.caption("🔒 Solo lectura")
# ------------------ CARGA ------------------
with tabs[3]:
    data = []
    for n in obtener_nombres_equipo():
        data.append(
            {
                "Persona": n,
                "Carga": calcular_carga_dia(n, eventos_data.get("registros", [])),
            }
        )
    st.table(pd.DataFrame(data))

# ------------------ GASTOS ------------------
with tabs[4]:
    st.header("💰 Gestión de Gastos")
    eventos = eventos_data.get("registros", [])
    opciones = [f"{e['evento']} ({e['responsable']})" for e in eventos]

    if opciones:
        idx = st.selectbox(
            "Selecciona evento",
            range(len(opciones)),
            format_func=lambda x: opciones[x],
            key="gasto_sel",
        )

        ev_sel = eventos[idx]
        concepto = st.text_input("Concepto", key="gasto_con")
        monto = st.number_input("Monto", min_value=0.0, key="gasto_mon")

        if st.button("Registrar gasto", key="btn_gasto"):
            insertar_gasto(
                {
                    "id": str(uuid.uuid4())[:6],
                    "id_ev": ev_sel["id_ev"],
                    "evento": ev_sel["evento"],
                    "concepto": concepto,
                    "importe": monto,
                    "fecha": str(datetime.now(timezone.utc).date()),
                }
            )
            st.success("Gasto registrado")
            st.rerun()

        st.divider()

        gastos = obtener_gastos_por_evento(ev_sel["id_ev"])
        if gastos:
            df = pd.DataFrame(gastos)
            st.dataframe(df, use_container_width=True)
            total = df["importe"].sum()
            st.metric("Total gasto", f"${total:,.0f}")
        else:
            st.info("Sin gastos registrados")

# ------------------ ADMIN ------------------
with tabs[5]:
    st.header("⚙️ Administración")

    sub1, sub2, sub3, sub4 = st.tabs(
        ["👤 Equipo", "🏢 Áreas solicitantes", "📚 Catálogo", "🔐 Accesos"]
    )

    with sub1:
        if st.session_state.rol != "Admin":
            st.warning("Solo administradores")
        else:
            st.subheader("👥 Equipo actual")
            equipo = obtener_equipo_detalle()
            if equipo:
                st.dataframe(pd.DataFrame(equipo), use_container_width=True)
            else:
                st.info("Sin miembros registrados")

    with sub2:
        st.subheader("Áreas que solicitan eventos")
        nueva_area = st.text_input("Nueva área solicitante", key="new_area_sol")

        if st.button("Agregar área", key="btn_area_sol"):
            insertar_area_solicitante(nueva_area)
            st.success("Área agregada")
            st.rerun()

        st.divider()
        areas = obtener_areas_solicitantes()
        if areas:
            df = pd.DataFrame({"Áreas solicitantes": areas})
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Sin áreas registradas")

    with sub3:
        st.subheader("Catálogo de eventos")
        areas_sol = obtener_areas_solicitantes()

        ev = st.text_input("Evento", key="cat_ev")
        area = st.selectbox(
            "Área solicitante",
            areas_sol if areas_sol else ["Sin áreas"],
            key="cat_area",
        )
        hrs = st.number_input("Horas", min_value=1, key="cat_hr")

        if st.button("Guardar evento", key="btn_cat"):
            insertar_catalogo(ev, area, hrs)
            st.success("Evento guardado")
            st.rerun()

        st.divider()
        st.dataframe(pd.DataFrame(obtener_catalogo()), use_container_width=True)

    with sub4:
        if st.session_state.rol != "Admin":
            st.warning("Solo administradores")
        else:
            st.subheader("🔐 Crear acceso")

            nombre_user = st.text_input("Nombre completo", key="acc_nom")
            username = st.text_input("Usuario", key="acc_user")
            password = st.text_input("Contraseña", type="password", key="acc_pass")
            rol = st.selectbox(
                "Rol",
                [
                    "Admin",
                    "Gerente",
                    "Subgerente",
                    "Jefe",
                    "Coordinador",
                    "Auxiliar",
                ],
                key="acc_rol",
            )

            jefe_nombre = "N/A"
            jefe_id = None

            # Asignación de Puesto y Área según jerarquía
            if rol in ["Admin", "Gerente", "Subgerente"]:
                puesto = rol
                area = "Global"
                if rol == "Admin":
                    st.info("Los administradores no forman parte del equipo operativo.")
                else:
                    st.info(
                        f"El puesto {rol} tiene cobertura Global de manera predeterminada."
                    )
            else:
                # Puestos operativos: Jefe, Coordinador, Auxiliar
                puesto = rol
                areas_disponibles = obtener_areas_equipo()

                # Aseguramos que siempre existan las opciones 'Diseño' y 'Eventos'
                for area_defecto in ["Diseño", "Eventos"]:
                    if area_defecto not in areas_disponibles:
                        areas_disponibles.append(area_defecto)

                area = st.selectbox(
                    "Área",
                    areas_disponibles,
                    key="acc_area_operativa",
                )

            # Selección de Jefe Directo según puesto
            equipo = obtener_equipo_detalle()
            opciones_jefe = []

            if puesto == "Subgerente":
                opciones_jefe = [
                    m["nombre"] for m in equipo if m["puesto"] == "Gerente"
                ]
            elif puesto == "Jefe":
                opciones_jefe = [
                    m["nombre"] for m in equipo if m["puesto"] == "Subgerente"
                ]
            elif puesto == "Coordinador":
                opciones_jefe = [
                    m["nombre"]
                    for m in equipo
                    if m["puesto"] == "Jefe" and m["area"] == area
                ]
            elif puesto == "Auxiliar":
                opciones_jefe = [
                    m["nombre"]
                    for m in equipo
                    if m["puesto"] == "Coordinador" and m["area"] == area
                ]

            if opciones_jefe:
                jefe_nombre = st.selectbox("Jefe directo", opciones_jefe)
                jefe_id = next(m["id"] for m in equipo if m["nombre"] == jefe_nombre)
            else:
                if rol not in ["Admin", "Gerente"]:
                    st.info(
                        f"No hay un superior directo disponible actualmente para {puesto} en el área {area}."
                    )

            if st.button("Crear acceso", key="btn_access"):
                try:
                    # ----------------------------------------------------------------------
                    # CAMBIO AQUÍ: Se pasa 'area' como 5to argumento a crear_usuario
                    # ----------------------------------------------------------------------
                    crear_usuario(username, password, nombre_user, rol, area)

                    if rol != "Admin":
                        insertar_miembro(nombre_user, puesto, area, jefe_id)

                    st.success("Acceso creado correctamente")
                    st.rerun()

                except (ValueError, TypeError, KeyError) as e:
                    st.error(f"Error de base de datos: {e}")

# ------------------ HISTORIAL ------------------
with tabs[6]:
    st.header("📜 Historial")

    t1, t2, t3 = st.tabs(["Tareas", "Eventos", "Gastos"])

    with t1:
        data = obtener_historial("historial_tareas")
        if data:
            df = pd.DataFrame(data)
            base_cols = [
                "ID",
                "ID Tarea",
                "Evento",
                "Responsable",
                "Estado",
                "Fecha",
                "Horas",
            ]

            if len(df.columns) > len(base_cols):
                extra_cols = [
                    f"Extra_{i}" for i in range(len(df.columns) - len(base_cols))
                ]
                df.columns = base_cols + extra_cols
            else:
                df.columns = base_cols[: len(df.columns)]

            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date

            f1, f2 = st.columns(2)
            fecha_min = df["Fecha"].min() if "Fecha" in df.columns else None
            fecha_max = df["Fecha"].max() if "Fecha" in df.columns else None

            rango = f1.date_input(
                Labels.FILTRAR_FECHAS,
                [fecha_min, fecha_max] if fecha_min and fecha_max else None,
                key="hist_f_tareas",
            )

            responsables = f2.multiselect(
                Labels.RESPONSABLE,
                df["Responsable"].dropna().unique()
                if "Responsable" in df.columns
                else [],
                default=df["Responsable"].dropna().unique()
                if "Responsable" in df.columns
                else [],
                key="hist_r_tareas",
            )

            mask = pd.Series([True] * len(df))
            if "Responsable" in df.columns:
                mask &= df["Responsable"].isin(responsables)

            if (
                "Fecha" in df.columns
                and isinstance(rango, (list, tuple))
                and len(rango) == 2
            ):
                mask &= (df["Fecha"] >= rango[0]) & (df["Fecha"] <= rango[1])

            df_f = df[mask]
            st.dataframe(df_f, use_container_width=True)
            st.metric("Total tareas", len(df_f))
        else:
            st.info(Mensajes.SIN_HISTORIAL)

    with t2:
        data = obtener_historial("historial_eventos")
        if data:
            df = pd.DataFrame(data)
            df.columns = [
                "ID",
                "ID Evento",
                "Evento",
                "Responsable",
                "Estado",
                "Fecha",
            ][: len(df.columns)]

            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
            f1, f2 = st.columns(2)

            fecha_min = df["Fecha"].min()
            fecha_max = df["Fecha"].max()

            rango = f1.date_input(
                "Filtrar fechas",
                [fecha_min, fecha_max] if fecha_min and fecha_max else None,
                key="hist_f_eventos",
            )

            responsables = f2.multiselect(
                "Responsables",
                df["Responsable"].dropna().unique(),
                default=df["Responsable"].dropna().unique(),
                key="hist_r_eventos",
            )

            mask = df["Responsable"].isin(responsables)
            if isinstance(rango, (list, tuple)) and len(rango) == 2:
                mask &= (df["Fecha"] >= rango[0]) & (df["Fecha"] <= rango[1])

            df_f = df[mask]
            st.dataframe(df_f, use_container_width=True)
            st.metric("Total eventos", len(df_f))
        else:
            st.info(Mensajes.SIN_HISTORIAL)

    with t3:
        data = obtener_historial("historial_gastos")
        if data:
            df = pd.DataFrame(data)
            df.columns = [
                "ID",
                "Evento",
                "Concepto",
                "Importe",
                "Fecha",
            ][: len(df.columns)]

            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
            f1, f2 = st.columns(2)

            fecha_min = df["Fecha"].min()
            fecha_max = df["Fecha"].max()

            rango = f1.date_input(
                "Filtrar fechas",
                [fecha_min, fecha_max] if fecha_min and fecha_max else None,
                key="hist_f_gastos",
            )

            eventos = f2.multiselect(
                "Eventos",
                df["Evento"].dropna().unique(),
                default=df["Evento"].dropna().unique(),
                key="hist_e_gastos",
            )

            mask = df["Evento"].isin(eventos)
            if isinstance(rango, (list, tuple)) and len(rango) == 2:
                mask &= (df["Fecha"] >= rango[0]) & (df["Fecha"] <= rango[1])

            df_f = df[mask]
            st.dataframe(df_f, use_container_width=True)
            st.metric("Total gasto", f"${df_f['Importe'].sum():,.0f}")
        else:
            st.info("Sin historial")

# ================== HISTÓRICO EJECUTIVO ==================
with tabs[7]:
    st.header("📈 Histórico Ejecutivo")

    data = obtener_historial_eventos_live()

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)

        if HORAS_TOTALES_COLUMN in df.columns:
            st.metric(HORAS_TOTALES_COLUMN, int(df[HORAS_TOTALES_COLUMN].sum()))
        if "Costo Total" in df.columns:
            st.metric("Costo Total", f"${df['Costo Total'].sum():,.0f}")
    else:
        st.info("Sin información")
