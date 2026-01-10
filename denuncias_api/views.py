from django.shortcuts import render
import uuid
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from db.models import Denuncias, Ciudadanos
from .serializers import DenunciaCreateSerializer


def get_claim(request, key: str, default=None):
    token = getattr(request, "auth", None)
    if token is None:
        return default
    try:
        return token.get(key, default)
    except Exception:
        return default


class CrearDenunciaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uid = get_claim(request, "uid")
        tipo = get_claim(request, "tipo")

        if not uid or tipo != "ciudadano":
            return Response({"detail": "Solo ciudadanos pueden crear denuncias"}, status=403)

        if not Ciudadanos.objects.filter(usuario_id=uid).exists():
            return Response({"detail": "Perfil ciudadano no existe"}, status=400)

        ser = DenunciaCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        now = timezone.now()

        denuncia = Denuncias.objects.create(
            id=uuid.uuid4(),
            ciudadano_id=uid,
            tipo_denuncia_id=v["tipo_denuncia_id"],
            descripcion=v["descripcion"],
            referencia=v.get("referencia"),
            latitud=v["latitud"],
            longitud=v["longitud"],
            direccion_texto=v.get("direccion_texto"),
            origen=v.get("origen", "formulario"),
            estado="pendiente",
            created_at=now,
            updated_at=now,
        )

        return Response(
            {
                "id": str(denuncia.id),
                "estado": str(denuncia.estado),
                "asignado_departamento_id": getattr(denuncia, "asignado_departamento_id", None),
                "created_at": denuncia.created_at,
            },
            status=status.HTTP_201_CREATED
        )


class MisDenunciasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uid = get_claim(request, "uid")
        tipo = get_claim(request, "tipo")

        if not uid or tipo != "ciudadano":
            return Response({"detail": "Solo ciudadanos"}, status=403)

        qs = Denuncias.objects.filter(ciudadano_id=uid).order_by("-created_at")[:100]

        data = []
        for d in qs:
            data.append({
                "id": str(d.id),
                "tipo_denuncia_id": d.tipo_denuncia_id,
                "descripcion": d.descripcion,
                "estado": str(d.estado),
                "latitud": d.latitud,
                "longitud": d.longitud,
                "created_at": d.created_at,
            })

        return Response(data, status=200)


import math
from datetime import timedelta
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


def _to_bool(v):
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "t", "yes", "y", "si")


def _haversine_km(lat1, lon1, lat2, lon2):
    # Radio tierra km
    R = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2) + math.cos(lat1 * p) * math.cos(lat2 * p) * (math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class MapaDenunciasView(APIView):
    """
    GET /api/denuncias/mapa/?lat=-0.93&lng=-78.61&radio_km=2&solo_hoy=true&solo_mias=false&tipo_denuncia_id=1
    Devuelve denuncias para pintar marcadores en el mapa.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uid = get_claim(request, "uid")
        tipo = get_claim(request, "tipo")

        if not uid or tipo != "ciudadano":
            return Response({"detail": "Solo ciudadanos"}, status=403)

        # Query params
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radio_km = request.query_params.get("radio_km", "2")
        solo_hoy = _to_bool(request.query_params.get("solo_hoy"))
        solo_mias = _to_bool(request.query_params.get("solo_mias"))
        tipo_denuncia_id = request.query_params.get("tipo_denuncia_id")
        q = (request.query_params.get("q") or "").strip().lower()

        try:
            radio_km = float(radio_km)
        except Exception:
            radio_km = 2.0

        qs = Denuncias.objects.select_related("tipo_denuncia").all().order_by("-created_at")

        # filtros
        if solo_mias:
            qs = qs.filter(ciudadano_id=uid)

        if tipo_denuncia_id:
            try:
                qs = qs.filter(tipo_denuncia_id=int(tipo_denuncia_id))
            except Exception:
                pass

        if solo_hoy:
            hoy = timezone.localdate()
            qs = qs.filter(created_at__date=hoy)

        if q:
            # búsqueda simple en descripcion/referencia (si existe)
            qs = qs.filter(descripcion__icontains=q) | qs.filter(referencia__icontains=q)

        # filtro por radio (si llega lat/lng)
        use_geo = False
        lat0 = lon0 = None
        if lat is not None and lng is not None:
            try:
                lat0 = float(lat)
                lon0 = float(lng)
                use_geo = True
            except Exception:
                use_geo = False

        items = []
        if use_geo:
            # bounding box para no traer todo
            # 1 grado lat ~ 111km
            dlat = radio_km / 111.0
            # 1 grado lng ~ 111km * cos(lat)
            coslat = math.cos(math.radians(lat0)) if lat0 is not None else 1.0
            dlng = radio_km / (111.0 * coslat) if coslat != 0 else radio_km / 111.0

            qs = qs.filter(
                latitud__gte=lat0 - dlat, latitud__lte=lat0 + dlat,
                longitud__gte=lon0 - dlng, longitud__lte=lon0 + dlng,
            )[:800]  # límite seguro

            for d in qs:
                dist = _haversine_km(lat0, lon0, float(d.latitud), float(d.longitud))
                if dist <= radio_km:
                    items.append(self._to_item(d, uid, dist))
        else:
            # sin geo: devuelve lo más reciente (para pruebas)
            qs = qs[:200]
            for d in qs:
                items.append(self._to_item(d, uid, None))

        return Response(
            {
                "count": len(items),
                "radio_km": radio_km,
                "solo_hoy": solo_hoy,
                "solo_mias": solo_mias,
                "items": items,
            },
            status=200
        )

    def _to_item(self, d, uid, dist_km):
        return {
            "id": str(d.id),
            "tipo_denuncia_id": getattr(d, "tipo_denuncia_id", None),
            "tipo_denuncia_nombre": getattr(getattr(d, "tipo_denuncia", None), "nombre", None),
            "descripcion": d.descripcion,
            "referencia": getattr(d, "referencia", None),
            "estado": str(d.estado),
            "latitud": float(d.latitud),
            "longitud": float(d.longitud),
            "created_at": d.created_at,
            "es_mia": str(d.ciudadano_id) == str(uid),
            "dist_km": dist_km,
        }

