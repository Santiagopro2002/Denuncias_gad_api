from django.shortcuts import render

# Create your views here.
import json
import uuid

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

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
# Helpers JWT (igual que el tuyo)
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
    #return OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", None))
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# =========================================================
# Tools (function calling)
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
            "properties": {
                "borrador_id": {"type": "string", "description": "UUID del borrador"},
            },
            "required": ["borrador_id"],
        },
    },
    {
        "type": "function",
        "name": "update_borrador",
        "description": "Actualiza parcialmente campos del borrador (tipo, descripcion, referencia, latitud, longitud, direccion_texto).",
        "parameters": {
            "type": "object",
            "properties": {
                "borrador_id": {"type": "string"},
                "tipo_denuncia_id": {"type": "integer"},
                "descripcion": {"type": "string"},
                "referencia": {"type": "string"},
                "latitud": {"type": "number"},
                "longitud": {"type": "number"},
                "direccion_texto": {"type": "string"},
            },
            "required": ["borrador_id"],
        },
    },
    {
        "type": "function",
        "name": "finalizar_denuncia",
        "description": "Finaliza: crea la denuncia en la tabla denuncias (origen=chat) usando el borrador. Devuelve denuncia_id. Solo si están completos los campos.",
        "parameters": {
            "type": "object",
            "properties": {
                "borrador_id": {"type": "string"},
                "confirmacion": {
                    "type": "boolean",
                    "description": "Debe ser true solo si el usuario ya confirmó que desea enviar.",
                },
            },
            "required": ["borrador_id", "confirmacion"],
        },
    },
]


def _execute_tool(uid: str, tool_name: str, args: dict):
    """
    Ejecuta lógica de tools en tu backend.
    Retorna dict serializable.
    """
    if tool_name == "get_tipos_denuncia":
        qs = TiposDenuncia.objects.filter(activo=True).order_by("nombre")
        return {
            "tipos": [{"id": int(x.id), "nombre": x.nombre} for x in qs]
        }

    if tool_name == "get_borrador":
        borrador_id = args["borrador_id"]
        try:
            b = DenunciaBorradores.objects.get(id=borrador_id, ciudadano_id=uid)
        except DenunciaBorradores.DoesNotExist:
            return {"error": "borrador_no_existe"}
        return {"borrador_id": str(b.id), "datos": b.datos_json or {}, "listo_para_enviar": bool(b.listo_para_enviar)}

    if tool_name == "update_borrador":
        borrador_id = args["borrador_id"]
        try:
            b = DenunciaBorradores.objects.get(id=borrador_id, ciudadano_id=uid)
        except DenunciaBorradores.DoesNotExist:
            return {"error": "borrador_no_existe"}

        data = b.datos_json or {}
        # merge solo lo enviado
        for k in ["tipo_denuncia_id", "descripcion", "referencia", "latitud", "longitud", "direccion_texto"]:
            if k in args and args[k] is not None:
                data[k] = args[k]

        # marca origen chat
        data["origen"] = "chat"

        b.datos_json = data
        b.updated_at = timezone.now()
        b.save(update_fields=["datos_json", "updated_at"])

        # verificar completitud mínima
        ok = (
            bool(data.get("tipo_denuncia_id"))
            and bool(data.get("descripcion"))
            and data.get("latitud") is not None
            and data.get("longitud") is not None
        )
        if ok:
            b.listo_para_enviar = True
            b.save(update_fields=["listo_para_enviar"])

        return {"updated": True, "listo_para_enviar": ok, "datos": data}

    if tool_name == "finalizar_denuncia":
        borrador_id = args["borrador_id"]
        confirm = bool(args.get("confirmacion"))

        if not confirm:
            return {"error": "no_confirmado"}

        try:
            b = DenunciaBorradores.objects.select_for_update().get(id=borrador_id, ciudadano_id=uid)
        except DenunciaBorradores.DoesNotExist:
            return {"error": "borrador_no_existe"}

        data = b.datos_json or {}
        # validación mínima
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

        # vincular conversación si existe
        if b.conversacion_id:
            try:
                conv = b.conversacion
                conv.denuncia_id = d.id
                conv.updated_at = now
                conv.save(update_fields=["denuncia_id", "updated_at"])
            except Exception:
                pass

        b.delete()
        return {"ok": True, "denuncia_id": str(d.id)}

    return {"error": "tool_desconocida"}


# =========================================================
# Prompts / instrucciones (NO hardcode feo, pero sí reglas)
# =========================================================
INSTRUCTIONS = """
Eres un asistente del GAD Municipal de Salcedo para ayudar a ciudadanos a redactar denuncias municipales.
Tu objetivo: recolectar datos para una denuncia: tipo_denuncia_id, descripcion, latitud, longitud, y opcional referencia/direccion_texto.
Debes hacer preguntas cortas, una por una, para completar los campos faltantes.

Reglas:
- Si el usuario pregunta algo NO relacionado a denuncias municipales o uso de la app, responde: "Solo puedo ayudarte con denuncias municipales y uso de la app."
- Antes de finalizar, confirma con el usuario: "¿Deseas enviar la denuncia ahora? (sí/no)".
- Solo llama a finalizar_denuncia cuando el usuario confirme explícitamente "sí".
- Usa herramientas (tools) para leer tipos y guardar datos en el borrador.
- No inventes latitud/longitud: si no existen, pide que el usuario envíe su ubicación o que la app la comparta.
""".strip()


def _to_openai_input_messages(conv_id: str):
    """
    Convierte historial DB -> formato input del Responses API.
    Mantiene últimos ~30 mensajes para no crecer infinito.
    """
    qs = ChatMensajes.objects.filter(conversacion_id=conv_id).order_by("created_at")
    msgs = list(qs)[-30:]

    out = []
    for m in msgs:
        role = "user" if m.emisor == "usuario" else "assistant"
        out.append({"role": role, "content": m.mensaje})
    return out


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
            # mensaje inicial del bot
            ChatMensajes.objects.create(
                id=uuid.uuid4(),
                conversacion_id=conv.id,
                emisor="bot",
                mensaje="Hola 👋 Soy tu asistente. ¿Qué deseas denunciar hoy? (Ej: basura, alumbrado, vías...)",
                created_at=now,
            )

        return Response(
            {"conversacion_id": str(conv.id), "borrador_id": str(borr.id)},
            status=201
        )


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

        try:
            conv = ChatConversaciones.objects.get(id=conv_id, ciudadano_id=uid)
        except ChatConversaciones.DoesNotExist:
            return Response({"detail": "Conversación no existe"}, status=404)

        # buscar borrador ligado a la conversación
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

        # construir input para OpenAI
        history = _to_openai_input_messages(conv_id)
        # añadimos contexto mínimo (borrador_id) para que el modelo sepa qué actualizar
        # OJO: esto NO es "texto quemado de respuestas", es metadata de operación.
        history.append({
            "role": "user",
            "content": f"(contexto interno: borrador_id={borr.id})"
        })

        client = _client()

        # 1) Primera llamada: el modelo puede pedir tool calls
        resp = client.responses.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-5"),
            instructions=INSTRUCTIONS,
            tools=TOOLS,
            input=history,
        )

        input_list = history + resp.output  # acumulamos

        # 2) Ejecutar tool calls si aparecen
        tool_outputs = []
        for item in resp.output:
            if getattr(item, "type", None) == "function_call":
                name = item.name
                args = json.loads(item.arguments or "{}")
                result = _execute_tool(str(uid), name, args)
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })

        # 3) Si hubo tools, segunda llamada para obtener texto final
        if tool_outputs:
            input_list.extend(tool_outputs)
            resp2 = client.responses.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-5"),
                instructions=INSTRUCTIONS,
                tools=TOOLS,
                input=input_list,
            )
            bot_text = resp2.output_text.strip()
        else:
            bot_text = (resp.output_text or "").strip()

        if not bot_text:
            bot_text = "Listo. ¿Me confirmas el tipo de denuncia y una breve descripción?"

        # guardar mensaje bot
        ChatMensajes.objects.create(
            id=uuid.uuid4(),
            conversacion_id=conv_id,
            emisor="bot",
            mensaje=bot_text,
            created_at=timezone.now(),
        )

        # refrescar borrador para mandar snapshot a Flutter
        borr.refresh_from_db()
        datos = borr.datos_json or {}

        return Response(
            {
                "respuesta": bot_text,
                "conversacion_id": str(conv_id),
                "borrador": {
                    "id": str(borr.id),
                    "listo_para_enviar": bool(borr.listo_para_enviar),
                    "datos": datos,
                },
                # si se finalizó, el borrador se borra, entonces aquí no habrá;
                # pero en este MVP lo detectas por un mensaje del bot y haces reload de "Mis denuncias".
            },
            status=200
        )
