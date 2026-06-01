from enum import Enum


class EstadoTarea(str, Enum):
    EN_PROCESO = "En proceso"
    ENTREGADO = "Entregado"
    PAUSADO = "Pausado"
    REVISION = "Revisión"
    REVISION_FINAL = "Revisión final"


class Mensajes:
    SIN_HISTORIAL = "Sin historial"
    SIN_AREAS = "Sin áreas"
    EVENTO_CREADO = "Evento creado"


class Labels:
    FILTRAR_FECHAS = "Filtrar fechas"
    RESPONSABLE = "Responsable"
    AREA_SOLICITANTE = "Área solicitante"
