from django.db import models
from db.models import Funcionarios
from django.conf import settings
# Create your models here.

class Menus(models.Model):
    nombre = models.CharField(max_length=100, db_column='nombre')
    url = models.CharField(max_length=200, db_column='url')
    icono = models.CharField(max_length=100, db_column='icono', null=True, blank=True)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, db_column='padre_id', related_name='submenus')
    orden = models.IntegerField(db_column='orden', default=0)
    permisos = models.ManyToManyField('auth.Group', blank=True, db_table='menu_permisos', related_name='menus')

    class Meta:
        db_table = 'menus'
        ordering = ['orden']

    def __str__(self):
        return self.nombre
