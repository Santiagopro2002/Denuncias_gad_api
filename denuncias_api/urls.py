from django.urls import path

# Denuncias finales
from .views import CrearDenunciaView, MisDenunciasView

# Borradores con temporizador (MVP)
from .views_borradores import (
    BorradoresCreateView,
    BorradoresMiosView,
    BorradoresUpdateDeleteView,
    BorradoresFinalizarManualView,
)
from .views import CrearDenunciaView, MisDenunciasView, MapaDenunciasView

urlpatterns = [

    path("", CrearDenunciaView.as_view(), name="crear_denuncia"),
    path("mias/", MisDenunciasView.as_view(), name="mis_denuncias"),
    path("mapa/", MapaDenunciasView.as_view(), name="denuncias_mapa"),
    path("borradores/", BorradoresCreateView.as_view(), name="borrador_create"),
    path("borradores/mios/", BorradoresMiosView.as_view(), name="borrador_mios"),
    path("borradores/<uuid:borrador_id>/",BorradoresUpdateDeleteView.as_view(),name="borrador_put_delete"),
    path("borradores/<uuid:borrador_id>/finalizar/",BorradoresFinalizarManualView.as_view(),name="borrador_finalizar"),

]
