from database import (
    init_db,
    obtener_eventos,
    obtener_tareas_por_evento,
    obtener_gastos_por_evento,
    obtener_nombres_equipo,
    obtener_catalogo,
    insertar_evento,
    insertar_tarea,
    actualizar_estado_tarea,
    obtener_equipo_detalle,
    obtener_areas_solicitantes,
    obtener_areas_equipo,
    insertar_miembro,
    insertar_area_solicitante,
    insertar_catalogo,
    insertar_gasto,
    obtener_historial,
    obtener_usuario,
    login,
    crear_usuario,
    obtener_usuarios,
    obtener_miembro_por_username,
)
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import uuid

init_db()

# ================= AUTH =================

if "auth" not in st.session_state:
    st.session_state.auth = False

# LOGIN
if not st.session_state.auth:
    st.title("🔐 Login")

    username = st.text_input("Usuario").strip()
    password = st.text_input("Contraseña", type="password").strip()

    if st.button("Ingresar"):
        user = login(username, password)

        if user:
            st.session_state.auth = True
            st.session_state.user = user["username"]
            st.session_state.nombre = user["nombre"]
            st.session_state.rol = user["rol"]

            st.rerun()

        else:
            st.error("Credenciales inválidas")

    st.stop()

# ================= USUARIO ACTUAL =================

if st.session_state.rol == "Admin":
    usuario = {
        "nombre": "ADMIN",
        "puesto": "Admin",
        "area": "Global",
    }

else:
    usuario = obtener_miembro_por_username(st.session_state.user)

# ================= CONFIG =================

st.set_page_config(layout="wide")

# ================= SIDEBAR =================

with st.sidebar:
    st.write(f"👤 {st.session_state.nombre}")
    st.write(f"🔑 {st.session_state.rol}")

    if st.button("Cerrar sesión"):
        st.session_state.clear()

        st.rerun()
# ------------------ CARGA ------------------


def calcular_dias_habiles(fecha_inicio, fecha_fin):
    dias = 0
    actual = fecha_inicio

    # excluye fecha límite
    while actual < fecha_fin:
        # Lunes=0 | Domingo=6
        if actual.weekday() < 5:
            dias += 1

        actual += timedelta(days=1)

    return max(dias, 1)


def calcular_carga_dia(nombre, eventos):
    hoy = date.today()
    carga = 0

    for ev in eventos:
        for t in ev["tareas"]:
            # Solo tareas de la persona
            if t["quien"] != nombre:
                continue

            # Ignorar entregadas
            if t["estado"] == "Entregado":
                continue

            try:
                f_asig = date.fromisoformat(t["fecha_asignacion"])
                f_lim = date.fromisoformat(t["fecha_limite"])

                dias = calcular_dias_habiles(f_asig, f_lim)

                # Solo contar tareas vigentes
                if f_asig <= hoy < f_lim:
                    carga += t["hrs"] / dias

            except Exception:
                pass

    return round(carga, 2)


# ------------------ DATA ------------------

eventos_data = obtener_eventos()

# Obtener usuario actual
if st.session_state.rol == "Admin":
    usuario = {
        "nombre": "ADMIN",
        "puesto": "Admin",
        "area": "Global",
    }
else:
    usuario = obtener_miembro_por_username(st.session_state.user)

for ev in eventos_data["registros"]:
    ev["tareas"] = obtener_tareas_por_evento(ev["id_ev"])
    ev["gastos"] = obtener_gastos_por_evento(ev["id_ev"])

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
    ]
)

# ------------------ DASHBOARD ------------------

with tabs[0]:
    st.header("📊 Dashboard Ejecutivo")

    eventos = eventos_data["registros"]

    # ================= KPIs =================
    total_eventos = len(eventos)
    total_tareas = sum(len(ev["tareas"]) for ev in eventos)
    tareas_finalizadas = sum(
        1 for ev in eventos for t in ev["tareas"] if t["estado"] == "Entregado"
    )

    progreso = (tareas_finalizadas / total_tareas * 100) if total_tareas > 0 else 0

    total_gasto = sum(g["importe"] for ev in eventos for g in ev.get("gastos", []))

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Eventos activos", total_eventos)
    c2.metric("Tareas totales", total_tareas)
    c3.metric("Avance %", f"{progreso:.1f}%")
    c4.metric("Gasto total", f"${total_gasto:,.0f}")

    st.divider()

    # ================= CARGA POR PERSONA =================
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

    # ================= DISTRIBUCIÓN DE TAREAS =================
    st.subheader("📌 Distribución de tareas")

    estados = {}
    for ev in eventos:
        for t in ev["tareas"]:
            estados[t["estado"]] = estados.get(t["estado"], 0) + 1

    if estados:
        df_estado = pd.DataFrame(
            {"Estado": list(estados.keys()), "Cantidad": list(estados.values())}
        )
        st.bar_chart(df_estado.set_index("Estado"), height=300)

    st.divider()

    # ================= ALERTAS DE SATURACIÓN =================
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

    # ================= EVENTOS EN RIESGO =================
    st.subheader("⚠️ Eventos con riesgo")

    eventos_riesgo = []

    for ev in eventos:
        for t in ev["tareas"]:
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

        area = st.selectbox(
            "Área solicitante", areas_sol if areas_sol else ["Sin áreas"]
        )

        if st.form_submit_button("Crear"):
            insertar_evento(str(uuid.uuid4())[:8], ev, resp, "En proceso", area)
            st.success("Evento creado")
            st.rerun()

# ------------------ TAREAS ------------------
with tabs[2]:
    eventos = eventos_data["registros"]

    opciones = [f"{e['evento']} ({e['responsable']})" for e in eventos]

    if not opciones:
        st.info("No hay eventos")
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

        # USUARIO COMPLETO
        usuario = (
            obtener_usuario(st.session_state.user)
            if st.session_state.user != "ADMIN"
            else {"nombre": "ADMIN", "puesto": "Admin"}
        )

        # USUARIO ACTUAL
        asignado_por = usuario["nombre"]

        st.text_input("Asignado por", asignado_por, disabled=True)

        # LISTA DE PERSONAS
        personas = obtener_nombres_equipo()

        if not personas:
            st.warning("No hay equipo registrado")
            st.stop()

        asignado_a = st.selectbox("Asignar a", personas, key="resp")

        # FORM
        desc = st.text_input("Descripción", key="desc")
        hrs = st.number_input("Horas", min_value=1, key="hrs")

        fecha = st.date_input("Entrega", key="fecha")

        estado = st.selectbox(
            "Estatus",
            ["En proceso", "Pausado", "Revisión", "Revisión final"],
            key="estado",
        )

        # BOTÓN ASIGNAR
        if st.button("Asignar", key="btn_tarea"):
            # Evitar autoasignación
            if asignado_a == asignado_por:
                st.warning("No puedes asignarte a ti mismo")
                st.stop()

            # Validación básica
            if not asignado_a:
                st.error("Selecciona a quién asignar")
                st.stop()

            carga_actual = calcular_carga_dia(asignado_a, eventos)

            dias = calcular_dias_habiles(date.today(), fecha)
            carga_nueva = hrs / dias

            if carga_actual + carga_nueva > 8:
                st.error("Excede capacidad diaria")
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
                        "fecha_asignacion": str(date.today()),
                        "fecha_limite": str(fecha),
                        "evento": ev_sel["evento"],
                    }
                )
                st.success("Tarea asignada")
                st.rerun()

        # ================= TABLERO =================
        st.divider()
        st.subheader("📋 Tablero de tareas")

        tareas = obtener_tareas_por_evento(ev_sel["id_ev"])

        estados = ["En proceso", "Pausado", "Revisión", "Revisión final", "Entregado"]

        cols = st.columns(len(estados))

        for i, estado_col in enumerate(estados):
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

                        # PERMISOS
                        puede_editar = usuario["puesto"] in [
                            "Jefe",
                            "Coordinador",
                            "Admin",
                        ]
                        puede_cerrar = t["quien"] == usuario["nombre"]

                        # CAMBIO DE ESTADO
                        if puede_editar:
                            nuevo_estado = st.selectbox(
                                "Mover a",
                                estados,
                                index=estados.index(t["estado"]),
                                key=f"move_{t['id_tarea']}",
                            )

                            if nuevo_estado != t["estado"]:
                                actualizar_estado_tarea(t["id_tarea"], nuevo_estado)
                                st.rerun()
                        else:
                            st.caption(f"Estado: {t['estado']}")

                        c1, c2 = st.columns(2)

                        # DONE
                        if (puede_editar or puede_cerrar) and t[
                            "estado"
                        ] != "Entregado":
                            if c2.button("✅ Done", key=f"done_{t['id_tarea']}"):
                                actualizar_estado_tarea(t["id_tarea"], "Entregado")
                                st.rerun()

                        # SOLO LECTURA
                        if not (puede_editar or puede_cerrar):
                            st.caption("🔒 Solo lectura")
# ------------------ CARGA ------------------

with tabs[3]:
    data = []
    for n in obtener_nombres_equipo():
        data.append(
            {"Persona": n, "Carga": calcular_carga_dia(n, eventos_data["registros"])}
        )
    st.table(pd.DataFrame(data))

# ------------------ GASTOS ------------------

with tabs[4]:
    st.header("💰 Gestión de Gastos")

    eventos = eventos_data["registros"]

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
                    "fecha": str(date.today()),
                }
            )
            st.success("Gasto registrado")
            st.rerun()

        st.divider()

        gastos = obtener_gastos_por_evento(ev_sel["id_ev"])

        if gastos:
            df = pd.DataFrame(gastos)
            st.dataframe(df, width="stretch")

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

    # ================= EQUIPO =================
    with sub1:
        equipo = obtener_equipo_detalle()

        opciones_jefe = ["Sin jefe"] + [m["nombre"] for m in equipo]

        jefe_nombre = st.selectbox("Jefe directo", opciones_jefe)

        # Convertir a ID
        if jefe_nombre == "Sin jefe":
            jefe_id = None
        else:
            jefe_id = next(m["id"] for m in equipo if m["nombre"] == jefe_nombre)

        st.subheader("Agregar miembro")
        st.subheader("Crear acceso")

        new_user = st.text_input("Usuario")
        new_pass = st.text_input("Contraseña", type="password")

        rol = st.selectbox("Rol", ["Admin", "Jefe", "Coordinador", "Auxiliar"])

        nombre = st.text_input("Nombre", key="adm_nom")

        puesto = st.selectbox(
            "Puesto",
            [
                "Global",
                "Gerente",
                "Subgerente",
                "Jefe",
                "Coordinador",
                "Auxiliar",
            ],
            key="adm_puesto",
        )

        areas_equipo = obtener_areas_equipo()
        if "Global" not in areas_equipo:
            areas_equipo.insert(0, "Global")

        area = st.selectbox(
            "Área interna",
            areas_equipo if areas_equipo else ["Sin áreas"],
            key="adm_area",
        )

        if st.button("Agregar miembro", key="btn_add_user"):
            insertar_miembro(nombre, puesto, area, jefe_id)
            crear_usuario(new_user, new_pass, nombre, puesto)
            st.success("Miembro agregado")
            st.rerun()

        st.divider()
        st.subheader("Equipo actual")
        st.dataframe(pd.DataFrame(obtener_equipo_detalle()), width="stretch")

    # ================= AREAS SOLICITANTES =================
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
            st.dataframe(df, width="stretch")
        else:
            st.info("Sin áreas registradas")

    # ================= CATALOGO =================
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
        st.dataframe(pd.DataFrame(obtener_catalogo()), width="stretch")

    # ================= ACCESOS =================
    with sub4:
        # SOLO ADMINS
        if st.session_state.rol != "Admin":
            st.warning("Solo administradores")
            st.stop()

        st.subheader("🔐 Gestión de accesos")

        st.markdown("### Crear nuevo acceso")

        nombre_user = st.text_input("Nombre completo", key="acc_nom")

        username = st.text_input("Usuario", key="acc_user")

        password = st.text_input(
            "Contraseña",
            type="password",
            key="acc_pass",
        )

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
        # AREA GLOBAL PARA ADMINS
        if rol == "Admin":
            area = "Global"
            puesto = "Global"

            st.info("Los administradores usan área y puesto Global")

        else:
            puesto = st.selectbox(
                "Puesto",
                [
                    "Gerente",
                    "Subgerente",
                    "Jefe",
                    "Coordinador",
                    "Auxiliar",
                ],
                key="acc_puesto",
            )

            areas_equipo = obtener_areas_equipo()

            area = st.selectbox(
                "Área",
                areas_equipo,
                key="acc_area",
            )

        if st.button("Crear acceso", key="btn_access"):
            try:
                # CREAR ACCESO
                crear_usuario(
                    username,
                    password,
                    nombre_user,
                    rol,
                )
                # CREAR EN EQUIPO
                insertar_miembro(
                    nombre_user,
                    puesto,
                    area,
                    None,
                )

                st.success("Acceso creado")
                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    st.subheader("Usuarios registrados")

    usuarios = obtener_usuarios()

    if usuarios:
        df_users = pd.DataFrame(usuarios)
        st.dataframe(df_users, width="stretch")
    else:
        st.info("Sin usuarios registrados")
# ------------------ HISTORIAL ------------------

with tabs[6]:
    st.header("📜 Historial")

    t1, t2, t3 = st.tabs(["Tareas", "Eventos", "Gastos"])

    # ================= TAREAS =================
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

            # Fecha segura
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date

            f1, f2 = st.columns(2)

            fecha_min = df["Fecha"].min() if "Fecha" in df.columns else None
            fecha_max = df["Fecha"].max() if "Fecha" in df.columns else None

            rango = f1.date_input(
                "Filtrar fechas",
                [fecha_min, fecha_max] if fecha_min and fecha_max else None,
                key="hist_f_tareas",
            )

            responsables = f2.multiselect(
                "Responsables",
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

            st.dataframe(df_f, width="stretch")
            st.metric("Total tareas", len(df_f))

        else:
            st.info("Sin historial")

    # ================= EVENTOS =================
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

            st.dataframe(df_f, width="stretch")
            st.metric("Total eventos", len(df_f))

        else:
            st.info("Sin historial")

    # ================= GASTOS =================
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

            st.dataframe(df_f, width="stretch")
            st.metric("Total gasto", f"${df_f['Importe'].sum():,.0f}")

        else:
            st.info("Sin historial")
