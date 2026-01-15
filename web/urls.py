from django.urls import path, include
from django.contrib.auth.views import LogoutView

from .forms import *
from .views import permission_denied_view, page_not_found_view, server_error_view, CustomLoginView
from .views import *


app_name = 'web'

urlpatterns = [
    path('', home_view, name='home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', LogoutView.as_view(next_page='web:login'), name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),

    path('funcionarios/', FuncionariosListView.as_view(), name='funcionario_list'),
    path('funcionarios/create/', FuncionariosCreateView.as_view(), name='funcionario_create'),
    path('funcionarios/<int:pk>/', FuncionariosDetailView.as_view(), name='funcionario_detail'),
    path('funcionarios/<int:pk>/update/', FuncionariosUpdateView.as_view(), name='funcionario_update'),
    path('funcionarios/<int:pk>/delete/', FuncionariosDeleteView.as_view(), name='funcionario_delete'),
    
    path('departamentos/', DepartamentosListView.as_view(), name='departamento_list'),
    path('departamentos/create/', DepartamentosCreateView.as_view(), name='departamento_create'),
    path('departamentos/<int:pk>/', DepartamentosDetailView.as_view(), name='departamento_detail'),
    path('departamentos/<int:pk>/update/', DepartamentosUpdateView.as_view(), name='departamento_update'),
    path('departamentos/<int:pk>/delete/', DepartamentosDeleteView.as_view(), name='departamento_delete'),

    path('webusers/', WebUserListView.as_view(), name='webuser_list'),
    path('webusers/create/', WebUserCreateView.as_view(), name='webuser_create'),
    path('webusers/<int:pk>/', WebUserDetailView.as_view(), name='webuser_detail'),
    path('webusers/<int:pk>/edit/', WebUserUpdateView.as_view(), name='webuser_update'),
    path('webusers/<int:pk>/delete/', WebUserDeleteView.as_view(), name='webuser_delete'),

    path('grupos/', GrupoListView.as_view(), name='grupo_list'),
    path('grupos/create/', GrupoCreateView.as_view(), name='grupo_create'),
    path('grupos/<int:pk>/', GrupoDetailView.as_view(), name='grupo_detail'),
    path('grupos/<int:pk>/update/', GrupoUpdateView.as_view(), name='grupo_update'),
    path('grupos/<int:pk>/delete/', GrupoDeleteView.as_view(), name='grupo_delete'),

    path('menus/', MenuListView.as_view(), name='menu_list'),
    path('menus/create/', MenuCreateView.as_view(), name='menu_create'),
    path('menus/<int:pk>/update/', MenuUpdateView.as_view(), name='menu_update'),
    path('menus/<int:pk>/delete/', MenuDeleteView.as_view(), name='menu_delete'),

    path('faqs/', FaqListView.as_view(), name='faq_list'),
    path('faqs/create/', FaqCreateView.as_view(), name='faq_create'),
    path('faqs/<int:pk>/', FaqDetailView.as_view(), name='faq_detail'),
    path('faqs/<int:pk>/update/', FaqUpdateView.as_view(), name='faq_update'),
    path('faqs/<int:pk>/delete/', FaqDeleteView.as_view(), name='faq_delete'),

    path('denuncias/', DenunciaListView.as_view(), name='denuncia_list'),
    path('denuncias/mis-denuncias/', MisDenunciasListView.as_view(), name='mis_denuncias'),
    path('denuncias/<int:pk>/', DenunciaDetailView.as_view(), name='denuncia_detail'),
    path('denuncias/<int:pk>/respuestas/create/', crear_respuesta_denuncia, name='denuncia_respuesta_create'),
    path('denuncias/<int:pk>/update/', DenunciaUpdateView.as_view(), name='denuncia_update'),
    path('denuncias/<int:pk>/delete/', DenunciaDeleteView.as_view(), name='denuncia_delete'),

    path('tipo-denuncia-departamento/', TipoDenunciaDepartamentoListView.as_view(), name='tipo_denuncia_departamento_list'),
    path('tipo-denuncia-departamento/create/', TipoDenunciaDepartamentoCreateView.as_view(), name='tipo_denuncia_departamento_create'),
    path('tipo-denuncia-departamento/<int:pk>/', TipoDenunciaDepartamentoDetailView.as_view(), name='tipo_denuncia_departamento_detail'),
    path('tipo-denuncia-departamento/<int:pk>/update/', TipoDenunciaDepartamentoUpdateView.as_view(), name='tipo_denuncia_departamento_update'),
    path('tipo-denuncia-departamento/<int:pk>/delete/', TipoDenunciaDepartamentoDeleteView.as_view(), name='tipo_denuncia_departamento_delete'),

    path('tipos-denuncia/', TiposDenunciaListView.as_view(), name='tipos_denuncia_list'),
    path('tipos-denuncia/create/', TiposDenunciaCreateView.as_view(), name='tipos_denuncia_create'),
    path('tipos-denuncia/<int:pk>/', TiposDenunciaDetailView.as_view(), name='tipos_denuncia_detail'),
    path('tipos-denuncia/<int:pk>/update/', TiposDenunciaUpdateView.as_view(), name='tipos_denuncia_update'),
    path('tipos-denuncia/<int:pk>/delete/', TiposDenunciaDeleteView.as_view(), name='tipos_denuncia_delete'),
]
