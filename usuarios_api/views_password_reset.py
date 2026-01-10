# usuarios_api/views_password_reset.py
import random, uuid
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from rest_framework.views import APIView
from rest_framework.response import Response

from db.models import PasswordResetTokens, Usuarios, Ciudadanos


def gen_codigo_6():
    return f"{random.randint(0, 999999):06d}"


class ResetEnviarCodigoView(APIView):
    def post(self, request):
        cedula = (request.data.get("cedula") or "").strip()
        correo = (request.data.get("correo") or "").strip().lower()

        if not cedula or not correo:
            return Response({"detail": "cedula y correo son obligatorios"}, status=400)

        # 1) Buscar ciudadano por cédula
        try:
            ciudadano = Ciudadanos.objects.get(cedula=cedula)
        except Ciudadanos.DoesNotExist:
            return Response({"detail": "Si los datos son correctos, enviamos el código"}, status=200)

        # En tu modelo: Ciudadanos.usuario (OneToOne con Usuarios)
        usuario_id = ciudadano.usuario_id

        # 2) Confirmar correo y activo
        try:
            usuario = Usuarios.objects.get(id=usuario_id, correo=correo, activo=True)
        except Usuarios.DoesNotExist:
            return Response({"detail": "Si los datos son correctos, enviamos el código"}, status=200)

        # 3) Crear token
        codigo = gen_codigo_6()
        expira = timezone.now() + timedelta(minutes=10)
        now = timezone.now()

        token = PasswordResetTokens.objects.create(
            id=uuid.uuid4(),      # ✅ evita IntegrityError
            usuario=usuario,      # ✅ tu campo FK se llama "usuario"
            codigo_6=codigo,
            expira_en=expira,
            usado=False,
            created_at=now,       # ✅ tu modelo no tiene default en Django
            updated_at=now,
        )

        return Response({
            "detail": "Código enviado",
            "reset_id": str(token.id),
            "expira_en_min": 10,
            "dev_codigo": codigo,  # SOLO DEV
        }, status=200)


class ResetVerificarCodigoView(APIView):
    def post(self, request):
        reset_id = (request.data.get("reset_id") or "").strip()
        codigo = (request.data.get("codigo") or "").strip()

        if not reset_id or not codigo:
            return Response({"detail": "reset_id y codigo son obligatorios"}, status=400)

        try:
            token = PasswordResetTokens.objects.get(id=reset_id)
        except PasswordResetTokens.DoesNotExist:
            return Response({"detail": "Código inválido"}, status=400)

        if token.usado:
            return Response({"detail": "Código ya fue usado"}, status=400)

        if timezone.now() > token.expira_en:
            return Response({"detail": "Código expirado"}, status=400)

        if token.codigo_6 != codigo:
            return Response({"detail": "Código inválido"}, status=400)

        return Response({"detail": "Código verificado"}, status=200)


class ResetCambiarPasswordView(APIView):
    def post(self, request):
        reset_id = (request.data.get("reset_id") or "").strip()
        p1 = (request.data.get("password") or "").strip()
        p2 = (request.data.get("password2") or "").strip()

        if not reset_id or not p1 or not p2:
            return Response({"detail": "reset_id y passwords son obligatorios"}, status=400)

        if p1 != p2:
            return Response({"detail": "Las contraseñas no coinciden"}, status=400)

        if len(p1) < 6:
            return Response({"detail": "Mínimo 6 caracteres"}, status=400)

        try:
            token = PasswordResetTokens.objects.get(id=reset_id)
        except PasswordResetTokens.DoesNotExist:
            return Response({"detail": "Token inválido"}, status=400)

        if token.usado:
            return Response({"detail": "Token ya usado"}, status=400)

        if timezone.now() > token.expira_en:
            return Response({"detail": "Token expirado"}, status=400)

        # ✅ Actualizar password
        Usuarios.objects.filter(id=token.usuario_id).update(
            password_hash=make_password(p1)
        )

        token.usado = True
        token.updated_at = timezone.now()
        token.save(update_fields=["usado", "updated_at"])

        return Response({"detail": "Contraseña actualizada"}, status=200)
