# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Auditoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey('Usuarios', models.DO_NOTHING, blank=True, null=True)
    accion = models.CharField(max_length=100)
    tabla_afectada = models.CharField(max_length=100, blank=True, null=True)
    registro_id = models.TextField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    ip_origen = models.CharField(max_length=45, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auditoria'


class ChatConversaciones(models.Model):
    id = models.UUIDField(primary_key=True)
    ciudadano = models.ForeignKey('Ciudadanos', models.DO_NOTHING)
    denuncia = models.ForeignKey('Denuncias', models.DO_NOTHING, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'chat_conversaciones'


class ChatMensajes(models.Model):
    id = models.UUIDField(primary_key=True)
    conversacion = models.ForeignKey(ChatConversaciones, models.DO_NOTHING)
    emisor = models.CharField(max_length=10)
    mensaje = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'chat_mensajes'


class CiudadanoDocumentos(models.Model):
    id = models.UUIDField(primary_key=True)
    ciudadano = models.ForeignKey('Ciudadanos', models.DO_NOTHING)
    tipo_documento = models.CharField(max_length=50)
    url_frontal = models.TextField(blank=True, null=True)
    url_trasera = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'ciudadano_documentos'


class Ciudadanos(models.Model):
    usuario = models.OneToOneField('Usuarios', models.DO_NOTHING, primary_key=True)
    cedula = models.CharField(unique=True, max_length=15)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    foto_perfil_url = models.TextField(blank=True, null=True)
    firma_url = models.TextField(blank=True, null=True)
    firma_base64 = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'ciudadanos'


class DenunciaAsignaciones(models.Model):
    id = models.UUIDField(primary_key=True)
    denuncia = models.ForeignKey('Denuncias', models.DO_NOTHING)
    funcionario = models.ForeignKey('Funcionarios', models.DO_NOTHING)
    asignado_en = models.DateTimeField()
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'denuncia_asignaciones'


class DenunciaBorradores(models.Model):
    id = models.UUIDField(primary_key=True)
    ciudadano = models.ForeignKey(Ciudadanos, models.DO_NOTHING)
    conversacion = models.OneToOneField(ChatConversaciones, models.DO_NOTHING, blank=True, null=True)
    datos_json = models.JSONField()
    listo_para_enviar = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncia_borradores'


class DenunciaEvidencias(models.Model):
    id = models.UUIDField(primary_key=True)
    denuncia = models.ForeignKey('Denuncias', models.DO_NOTHING)
    tipo = models.TextField()  # This field type is a guess.
    url_archivo = models.TextField()
    nombre_archivo = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncia_evidencias'


class DenunciaFirmas(models.Model):
    id = models.UUIDField(primary_key=True)
    denuncia = models.OneToOneField('Denuncias', models.DO_NOTHING)
    firma_url = models.TextField(blank=True, null=True)
    firma_base64 = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncia_firmas'


class DenunciaHistorial(models.Model):
    id = models.UUIDField(primary_key=True)
    denuncia = models.ForeignKey('Denuncias', models.DO_NOTHING)
    estado_anterior = models.TextField(blank=True, null=True)  # This field type is a guess.
    estado_nuevo = models.TextField()  # This field type is a guess.
    comentario = models.TextField(blank=True, null=True)
    cambiado_por_funcionario = models.ForeignKey('Funcionarios', models.DO_NOTHING, db_column='cambiado_por_funcionario', blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncia_historial'


class DenunciaRespuestas(models.Model):
    id = models.UUIDField(primary_key=True)
    denuncia = models.ForeignKey('Denuncias', models.DO_NOTHING)
    funcionario = models.ForeignKey('Funcionarios', models.DO_NOTHING, blank=True, null=True)
    mensaje = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncia_respuestas'


class Denuncias(models.Model):
    id = models.UUIDField(primary_key=True)
    ciudadano = models.ForeignKey(Ciudadanos, models.DO_NOTHING)
    tipo_denuncia = models.ForeignKey('TiposDenuncia', models.DO_NOTHING)
    descripcion = models.TextField()
    referencia = models.TextField(blank=True, null=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    direccion_texto = models.TextField(blank=True, null=True)
    origen = models.TextField()  # This field type is a guess.
    estado = models.TextField()  # This field type is a guess.
    asignado_departamento = models.ForeignKey('Departamentos', models.DO_NOTHING, blank=True, null=True)
    asignado_funcionario = models.ForeignKey('Funcionarios', models.DO_NOTHING, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'denuncias'


class Departamentos(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(unique=True, max_length=120)
    activo = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'departamentos'


class Faq(models.Model):
    id = models.BigAutoField(primary_key=True)
    pregunta = models.TextField()
    respuesta = models.TextField()
    visible = models.BooleanField()
    creado_por = models.ForeignKey('Usuarios', models.DO_NOTHING, db_column='creado_por', blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'faq'


class FuncionarioRoles(models.Model):
    pk = models.CompositePrimaryKey('funcionario_id', 'rol_id')
    funcionario = models.ForeignKey('Funcionarios', models.DO_NOTHING)
    rol = models.ForeignKey('Roles', models.DO_NOTHING)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funcionario_roles'
        unique_together = (('funcionario', 'rol'),)


class Funcionarios(models.Model):
    usuario = models.OneToOneField('Usuarios', models.DO_NOTHING, primary_key=True)
    cedula = models.CharField(unique=True, max_length=15)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    departamento = models.ForeignKey(Departamentos, models.DO_NOTHING, blank=True, null=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)
    activo = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funcionarios'


class Notificaciones(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey('Usuarios', models.DO_NOTHING)
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=30)
    leido = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'notificaciones'


class PasswordResetTokens(models.Model):
    id = models.UUIDField(primary_key=True)
    usuario = models.ForeignKey('Usuarios', models.DO_NOTHING)
    codigo_6 = models.CharField(max_length=6)
    expira_en = models.DateTimeField()
    usado = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'password_reset_tokens'


class Roles(models.Model):
    id = models.UUIDField(primary_key=True)
    nombre = models.CharField(unique=True, max_length=40)
    descripcion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'roles'


class TipoDenunciaDepartamento(models.Model):
    tipo_denuncia = models.OneToOneField('TiposDenuncia', models.DO_NOTHING, primary_key=True)
    departamento = models.ForeignKey(Departamentos, models.DO_NOTHING)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'tipo_denuncia_departamento'


class TiposDenuncia(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(unique=True, max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'tipos_denuncia'


class Usuarios(models.Model):
    id = models.UUIDField(primary_key=True)
    tipo = models.TextField()  # This field type is a guess.
    correo = models.CharField(unique=True, max_length=150)
    password_hash = models.TextField()
    activo = models.BooleanField()
    correo_verificado = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'usuarios'
