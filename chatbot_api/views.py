import json
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from openai import OpenAI

from db.models import (
    Ciudadanos,
    TiposDenuncia,
    ChatConversaciones,
    ChatMensajes,
    DenunciaBorradores,
    Denuncias,
)

# =========================================================
# Helpers JWT
# =========================================================
def get_claim(request, key: str, default=None):
    token = getattr(request, "auth", None)
    if token is None:
        return default
    try:
        return token.get(key, default)
    except Exception:
        return default


# =========================================================
# OpenAI client
# =========================================================
def _client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# =========================================================
# Tools (Responses API format)
# =========================================================
TOOLS = [
    {
        "type": "function",
        "name": "get_tipos_denuncia",
        "description": "Devuelve los tipos de denuncia disponibles (id, nombre).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "get_borrador",
        "description": "Devuelve el borrador actual (datos_json) para verificar qué falta.",
        "parameters": {
            "type": "object",
            "properties": {"borrador_id": {"type": "string"}},
            "required": ["borrador_id"],
        },
    },
    {
        "type": "function",
        "name": "update_borrador",
        "description": "Actualiza parcialmente campos del borrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "borrador_id": {"type": "string"},
                "tipo_denuncia_id": {"type": "integer"},
                "descripcion": {"type": "string"},
                "referencia": {"type": "string"},
                "direccion_texto": {"type": "string"},
                "latitud": {"type": "number"},
                "longitud": {"type": "number"},
            },
            "required": ["borrador_id"],
        },
    },
    {
        "type": "function",
        "name": "finalizar_denuncia",
        "description": "Finaliza: crea la denuncia (origen=chat) usando el borrador. Devuelve denuncia_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "borrador_id": {"type": "string"},
                "confirmacion": {"type": "boolean"},
            },
            "required": ["borrador_id", "confirmacion"],
        },
    },
]


# =========================================================
# Instrucciones del asistente
# =========================================================
INSTRUCTIONS = """
Eres un asistente del GAD Municipal de Salcedo para ayudar a ciudadanos a redactar denuncias municipales.
Tu objetivo: recolectar datos para una denuncia: tipo_denuncia_id, descripcion, latitud, longitud, y opcional referencia/direccion_texto.
Haz preguntas cortas, una por una, para completar campos faltantes.

Reglas:
- Si el usuario pregunta algo NO relacionado a denuncias municipales o uso de la app, responde: "Solo puedo ayudarte con denuncias municipales y uso de la app."
- Antes de finalizar, confirma: "¿Deseas enviar la denuncia ahora? (sí/no)".
- Solo llama a finalizar_denuncia cuando el usuario confirme explícitamente "sí".
- No inventes latitud/longitud: si no existen, pide que el usuario envíe ubicación.
""".strip()


# =========================================================
# Extractores (para evitar ciclos)
# =========================================================
_re_tipo = re.compile(r"(?:^|\b)tipo\s*:\s*([^\n\.]+)", re.IGNORECASE)
_re_desc = re.compile(r"(?:^|\b)(?:descripcion|descripción)\s*:\s*(.+)", re.IGNORECASE)
_re_latlng = re.compile(
    r"(?:lat(?:itud)?)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*.*?(?:lon(?:gitud)?|lng)\s*[:=]?\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE | re.DOTALL,
)
_re_ref = re.compile(r"(?:^|\b)referencia\s*:\s*(.+)", re.IGNORECASE)
_re_dir = re.compile(r"(?:^|\b)(?:direccion|dirección)\s*:\s*(.+)", re.IGNORECASE)


def _match_tipo_to_id(nombre: str):
    """
    Intenta mapear texto de tipo -> TiposDenuncia.id por coincidencia simple.
    """
    if not nombre:
        return None
    n = nombre.strip().lower()

    qs = TiposDenuncia.objects.filter(activo=True)
    for t in qs:
        if t.nombre and t.nombre.strip().lower() in n or n in t.nombre.strip().lower():
            return int(t.id)

    # heurística mínima (puedes ampliar luego)
    if "basura" in n or "aseo" in n:
        t = TiposDenuncia.objects.filter(activo=True, nombre__icontains="basura").first()
        if t:
            return int(t.id)

    return None


def _extract_fields_from_text(text: str):
    """
    Extrae campos si vienen explícitos en el texto.
    """
    out = {}

    m = _re_tipo.search(text)
    if m:
        out["tipo_texto"] = m.group(1).strip()

    m = _re_desc.search(text)
    if m:
        out["descripcion"] = m.group(1).strip()

    m = _re_latlng.search(text)
    if m:
        out["latitud"] = float(m.group(1))
        out["longitud"] = float(m.group(2))

    m = _re_ref.search(text)
    if m:
        out["referencia"] = m.group(1).strip()

    m = _re_dir.search(text)
    if m:
        out["direccion_texto"] = m.group(1).strip()

    return out


# =========================================================
# Tools backend
# =========================================================
def _execute_tool(uid: str, tool_name: str, args: dict):
    if tool_name == "get_tipos_denuncia":
        qs = TiposDenuncia.objects.filter(activo=True).order_by("nombre")
        return {"tipos": [{"id": int(x.id), "nombre": x.nombre} for x in qs]}

    if tool_name == "get_borrador":
        borrador_id = args["borrador_id"]
        b = DenunciaBorradores.objects.filter(id=borrador_id, ciudadano_id=uid).first()
        if not b:
            return {"error": "borrador_no_existe"}
        return {"borrador_id": str(b.id), "datos": b.datos_json or {}, "listo_para_enviar": bool(b.listo_para_enviar)}

    if tool_name == "update_borrador":
        borrador_id = args["borrador_id"]
        b = DenunciaBorradores.objects.filter(id=borrador_id, ciudadano_id=uid).first()
        if not b:
            return {"error": "borrador_no_existe"}

        data = b.datos_json or {}
        for k in ["tipo_denuncia_id", "descripcion", "referencia", "latitud", "longitud", "direccion_texto"]:
            if k in args and args[k] is not None:
                data[k] = args[k]

        data["origen"] = "chat"

        # completitud mínima
        ok = (
            bool(data.get("tipo_denuncia_id"))
            and bool(data.get("descripcion"))
            and data.get("latitud") is not None
            and data.get("longitud") is not None
        )

        b.datos_json = data
        b.listo_para_enviar = bool(ok)
        b.updated_at = timezone.now()
        b.save(update_fields=["datos_json", "listo_para_enviar", "updated_at"])

        return {"updated": True, "listo_para_enviar": bool(ok), "datos": data}

    if tool_name == "finalizar_denuncia":
        borrador_id = args["borrador_id"]
        confirm = bool(args.get("confirmacion"))

        if not confirm:
            return {"error": "no_confirmado"}

        with transaction.atomic():
            b = DenunciaBorradores.objects.select_for_update().filter(id=borrador_id, ciudadano_id=uid).first()
            if not b:
                return {"error": "borrador_no_existe"}

            data = b.datos_json or {}
            tipo_denuncia_id = data.get("tipo_denuncia_id")
            descripcion = data.get("descripcion")
            latitud = data.get("latitud")
            longitud = data.get("longitud")

            if not tipo_denuncia_id or not descripcion or latitud is None or longitud is None:
                return {"error": "borrador_incompleto", "datos": data}

            now = timezone.now()
            d = Denuncias.objects.create(
                id=uuid.uuid4(),
                ciudadano_id=uid,
                tipo_denuncia_id=int(tipo_denuncia_id),
                descripcion=str(descripcion),
                referencia=data.get("referencia"),
                latitud=float(latitud),
                longitud=float(longitud),
                direccion_texto=data.get("direccion_texto"),
                origen="chat",
                estado="pendiente",
                created_at=now,
                updated_at=now,
            )

            # vincular conversación
            if b.conversacion_id:
                ChatConversaciones.objects.filter(id=b.conversacion_id).update(denuncia_id=d.id, updated_at=now)

            # borrar borrador (ya pasó a denuncia)
            b.delete()

        return {"ok": True, "denuncia_id": str(d.id)}

    return {"error": "tool_desconocida"}


# =========================================================
# Historial -> input messages
# =========================================================
def _to_openai_messages(conv_id: str):
    qs = ChatMensajes.objects.filter(conversacion_id=conv_id).order_by("created_at")
    msgs = list(qs)[-30:]
    out = []
    for m in msgs:
        role = "user" if m.emisor == "usuario" else "assistant"
        out.append({"role": role, "content": m.mensaje})
    return out


def _iter_function_calls(resp):
    """
    Itera function_call items de resp.output soportando dict u objeto.
    """
    for item in (resp.output or []):
        if isinstance(item, dict):
            if item.get("type") == "function_call":
                yield {
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                }
        else:
            if getattr(item, "type", None) == "function_call":
                yield {
                    "call_id": getattr(item, "call_id", None),
                    "name": getattr(item, "name", None),
                    "arguments": getattr(item, "arguments", None),
                }


class ChatbotStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uid = get_claim(request, "uid")
        tipo = get_claim(request, "tipo")
        if not uid or tipo != "ciudadano":
            return Response({"detail": "Solo ciudadanos"}, status=403)

        if not Ciudadanos.objects.filter(usuario_id=uid).exists():
            return Response({"detail": "Perfil ciudadano no existe"}, status=400)

        now = timezone.now()
        with transaction.atomic():
            conv = ChatConversaciones.objects.create(
                id=uuid.uuid4(),
                ciudadano_id=uid,
                denuncia_id=None,
                created_at=now,
                updated_at=now,
            )
            borr = DenunciaBorradores.objects.create(
                id=uuid.uuid4(),
                ciudadano_id=uid,
                conversacion_id=conv.id,
                datos_json={"origen": "chat"},
                listo_para_enviar=False,
                created_at=now,
                updated_at=now,
            )
            ChatMensajes.objects.create(
                id=uuid.uuid4(),
                conversacion_id=conv.id,
                emisor="bot",
                mensaje="Hola 👋 ¿Qué deseas denunciar hoy? (Ej: basura, alumbrado, vías...)",
                created_at=now,
            )

        return Response({"conversacion_id": str(conv.id), "borrador_id": str(borr.id)}, status=201)


class ChatbotMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uid = get_claim(request, "uid")
        tipo = get_claim(request, "tipo")
        if not uid or tipo != "ciudadano":
            return Response({"detail": "Solo ciudadanos"}, status=403)

        conv_id = (request.data.get("conversacion_id") or "").strip()
        text = (request.data.get("mensaje") or "").strip()
        if not conv_id or not text:
            return Response({"detail": "conversacion_id y mensaje son obligatorios"}, status=400)

        conv = ChatConversaciones.objects.filter(id=conv_id, ciudadano_id=uid).first()
        if not conv:
            return Response({"detail": "Conversación no existe"}, status=404)

        borr = DenunciaBorradores.objects.filter(conversacion_id=conv_id, ciudadano_id=uid).first()
        if not borr:
            return Response({"detail": "Borrador no encontrado para esta conversación"}, status=404)

        now = timezone.now()

        # guardar mensaje usuario
        ChatMensajes.objects.create(
            id=uuid.uuid4(),
            conversacion_id=conv_id,
            emisor="usuario",
            mensaje=text,
            created_at=now,
        )

        # 0) extracción rápida para evitar bucles
        extracted = _extract_fields_from_text(text)
        update_payload = {"borrador_id": str(borr.id)}

        if "tipo_texto" in extracted:
            tipo_id = _match_tipo_to_id(extracted["tipo_texto"])
            if tipo_id:
                update_payload["tipo_denuncia_id"] = tipo_id

        for k in ["descripcion", "referencia", "direccion_texto", "latitud", "longitud"]:
            if k in extracted:
                update_payload[k] = extracted[k]

        if len(update_payload.keys()) > 1:
            _execute_tool(str(uid), "update_borrador", update_payload)
            borr.refresh_from_db()

        # 1) si ya está listo y el usuario confirma -> finalizar directo (sin LLM)
        texto_norm = text.strip().lower()
        if borr.listo_para_enviar and texto_norm in ("si", "sí", "si.", "sí.", "enviar", "confirmo", "confirmo enviar"):
            r = _execute_tool(str(uid), "finalizar_denuncia", {"borrador_id": str(borr.id), "confirmacion": True})
            if r.get("ok"):
                ChatMensajes.objects.create(
                    id=uuid.uuid4(),
                    conversacion_id=conv_id,
                    emisor="bot",
                    mensaje=f"✅ Denuncia enviada. ID: {r['denuncia_id']}",
                    created_at=timezone.now(),
                )
                return Response(
                    {"respuesta": f"✅ Denuncia enviada. ID: {r['denuncia_id']}", "conversacion_id": str(conv_id), "denuncia_id": r["denuncia_id"]},
                    status=200,
                )

        # 2) LLM (Responses API correcto)
        client = _client()
        history = _to_openai_messages(conv_id)
        history.append({"role": "user", "content": f"(contexto interno: borrador_id={borr.id})"})

        resp = client.responses.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-5"),
            instructions=INSTRUCTIONS,
            tools=TOOLS,
            input=history,
        )

        # 3) loop de tools usando previous_response_id (máx 5 rondas)
        for _ in range(5):
            calls = list(_iter_function_calls(resp))
            if not calls:
                break

            tool_outputs = []
            for c in calls:
                name = c["name"]
                call_id = c["call_id"]
                try:
                    args = json.loads(c["arguments"] or "{}")
                except Exception:
                    args = {}

                result = _execute_tool(str(uid), name, args)

                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })

            resp = client.responses.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-5"),
                instructions=INSTRUCTIONS,
                tools=TOOLS,
                previous_response_id=resp.id,
                input=tool_outputs,
            )

        bot_text = (resp.output_text or "").strip()
        if not bot_text:
            bot_text = "¿Me confirmas el tipo de denuncia y una breve descripción?"

        ChatMensajes.objects.create(
            id=uuid.uuid4(),
            conversacion_id=conv_id,
            emisor="bot",
            mensaje=bot_text,
            created_at=timezone.now(),
        )

        # devolver snapshot borrador
        borr = DenunciaBorradores.objects.filter(conversacion_id=conv_id, ciudadano_id=uid).first()
        datos = (borr.datos_json if borr else {}) or {}

        return Response(
            {
                "respuesta": bot_text,
                "conversacion_id": str(conv_id),
                "borrador": {
                    "id": str(borr.id) if borr else None,
                    "listo_para_enviar": bool(borr.listo_para_enviar) if borr else False,
                    "datos": datos,
                },
            },
            status=200,
        )
