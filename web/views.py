from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib.auth.models import Group
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from db.models import *
from .models import Menus
from django import forms
from django.views.generic.edit import (CreateView, UpdateView, DeleteView)
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from .forms import *
from django.contrib.auth.decorators import login_required, permission_required

def get_uuid():
    """Genera un UUID4 como cadena"""
    import uuid
    return str(uuid.uuid4())

# Vistas personalizadas para errores
def permission_denied_view(request, exception=None):
    """Vista personalizada para manejar errores de permisos (403)"""
    return render(request, 'errors/403.html', status=403)

def page_not_found_view(request, exception=None):
    """Vista personalizada para manejar errores de página no encontrada (404)"""
    return render(request, 'errors/404.html', status=404)

def server_error_view(request):
    """Vista personalizada para manejar errores del servidor (500)"""
    return render(request, 'errors/500.html', status=500)

# Vista personalizada para login con redirección de usuarios autenticados
class CustomLoginView(LoginView):
    """LoginView personalizado que redirige usuarios autenticados al dashboard"""
    template_name = 'registration/login.html'
    next_page = 'web:dashboard'
    
    def get(self, request, *args, **kwargs):
        """Redirecciona a dashboard si el usuario ya está autenticado"""
        if request.user.is_authenticated:
            return redirect('web:dashboard')
        return super().get(request, *args, **kwargs)

def home_view(request):
    """Vista para la página de inicio"""
    if request.user.is_authenticated:
        return redirect('web:dashboard')
    from db.models import Faq
    faqs = Faq.objects.filter(visible=True)
    return render(request, 'home.html', {'faqs': faqs})

    
def dashboard_view(request):
    """Vista para el panel de control con KPIs"""
    from django.db.models import Count, Q
    from datetime import timedelta
    from django.utils import timezone
    
    # Período de últimos 30 días
    fecha_hace_30_dias = timezone.now() - timedelta(days=30)
    
    # KPI 1: Total de Denuncias
    total_denuncias = Denuncias.objects.count()
    denuncias_este_mes = Denuncias.objects.filter(created_at__gte=fecha_hace_30_dias).count()
    
    # KPI 2: Estados de Denuncias
    denuncias_pendientes = Denuncias.objects.filter(estado='pendiente').count()
    denuncias_en_proceso = Denuncias.objects.filter(estado='en_proceso').count()
    denuncias_resueltas = Denuncias.objects.filter(estado='resuelto').count()
    
    # KPI 3: Total de Ciudadanos
    total_ciudadanos = Ciudadanos.objects.count()
    ciudadanos_este_mes = Ciudadanos.objects.filter(created_at__gte=fecha_hace_30_dias).count()
    
    # KPI 4: Total de Funcionarios
    total_funcionarios = Funcionarios.objects.count()
    funcionarios_activos = Funcionarios.objects.filter(activo=True).count()
    
    # KPI 5: Total de Departamentos
    total_departamentos = Departamentos.objects.count()
    departamentos_activos = Departamentos.objects.filter(activo=True).count()
    
    # KPI 6: Promedio de denuncias por departamento
    promedio_denuncias_depto = total_denuncias / max(departamentos_activos, 1)
    
    # KPI 7: Denuncias por tipo
    denuncias_por_tipo = Denuncias.objects.values('tipo_denuncia__nombre').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # KPI 8: Departamentos con más denuncias
    departamentos_con_denuncias = Denuncias.objects.filter(
        asignado_departamento__isnull=False
    ).values('asignado_departamento__nombre').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Tasa de resolución
    if total_denuncias > 0:
        tasa_resolucion = (denuncias_resueltas / total_denuncias) * 100
    else:
        tasa_resolucion = 0
    
    # Denuncias con coordenadas para el mapa
    denuncias_mapa = Denuncias.objects.select_related(
        'ciudadano', 'tipo_denuncia', 'asignado_departamento'
    ).all()[:100]  # Limitar a 100 para rendimiento
    
    context = {
        'total_denuncias': total_denuncias,
        'denuncias_este_mes': denuncias_este_mes,
        'denuncias_pendientes': denuncias_pendientes,
        'denuncias_en_proceso': denuncias_en_proceso,
        'denuncias_resueltas': denuncias_resueltas,
        'total_ciudadanos': total_ciudadanos,
        'ciudadanos_este_mes': ciudadanos_este_mes,
        'total_funcionarios': total_funcionarios,
        'funcionarios_activos': funcionarios_activos,
        'total_departamentos': total_departamentos,
        'departamentos_activos': departamentos_activos,
        'promedio_denuncias_depto': round(promedio_denuncias_depto, 2),
        'denuncias_por_tipo': denuncias_por_tipo,
        'departamentos_con_denuncias': departamentos_con_denuncias,
        'tasa_resolucion': round(tasa_resolucion, 1),
        'denuncias_mapa': denuncias_mapa,
    }
    
    return render(request, 'dashboard.html', context)


# --- Vistas para Grupos ---
class GrupoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Group
    template_name = 'grupos/grupo_list.html'
    context_object_name = 'grupos'
    permission_required = 'auth.view_group'
    login_url = 'web:login'
    ordering = ['name']
    paginate_by = 15

class GrupoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Group
    form_class = GrupoForm
    template_name = 'grupos/grupo_form.html'
    success_url = reverse_lazy('web:grupo_list')
    permission_required = 'auth.add_group'
    login_url = 'web:login'

class GrupoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Group
    form_class = GrupoForm
    template_name = 'grupos/grupo_form.html'
    success_url = reverse_lazy('web:grupo_list')
    permission_required = 'auth.change_group'
    login_url = 'web:login'

class GrupoDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Group
    template_name = 'grupos/grupo_detail.html'
    context_object_name = 'grupo'
    permission_required = 'auth.view_group'
    login_url = 'web:login'

class GrupoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Group
    template_name = 'grupos/grupo_confirm_delete.html'
    success_url = reverse_lazy('web:grupo_list')
    permission_required = 'auth.delete_group'
    login_url = 'web:login'

# --- Vistas para Menus (Solo Superusuarios) ---
class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        return render(self.request, 'errors/403.html', status=403)

class MenuListView(LoginRequiredMixin, SuperUserRequiredMixin, ListView):
    model = Menus
    template_name = 'menus/menu_list.html'
    context_object_name = 'menus'
    ordering = ['padre', 'orden']
    login_url = 'web:login'
    paginate_by = 5
    
    def get_queryset(self):
        return Menus.objects.all().order_by('padre__id', 'orden')

class MenuCreateView(LoginRequiredMixin, SuperUserRequiredMixin, CreateView):
    model = Menus
    form_class = MenuForm
    template_name = 'menus/menu_form.html'
    success_url = reverse_lazy('web:menu_list')
    login_url = 'web:login'


class MenuUpdateView(LoginRequiredMixin, SuperUserRequiredMixin, UpdateView):
    model = Menus
    form_class = MenuForm
    template_name = 'menus/menu_form.html'
    success_url = reverse_lazy('web:menu_list')
    login_url = 'web:login'

class MenuDeleteView(LoginRequiredMixin, SuperUserRequiredMixin, DeleteView):
    model = Menus
    template_name = 'menus/menu_confirm_delete.html'
    success_url = reverse_lazy('web:menu_list')
    login_url = 'web:login'


# --- Vistas para FAQs ---
class FaqListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Faq
    template_name = 'faqs/faq_list.html'
    context_object_name = 'faqs'
    permission_required = 'db.view_faq'
    login_url = 'web:login'
    ordering = ['-created_at']
    paginate_by = 15

class FaqCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Faq
    form_class = FaqForm
    template_name = 'faqs/faq_form.html'
    success_url = reverse_lazy('web:faq_list')
    permission_required = 'db.add_faq'
    login_url = 'web:login'

    def form_valid(self, form):
        if not form.instance.pk:
             form.instance.created_at = timezone.now()
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class FaqUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Faq
    form_class = FaqForm
    template_name = 'faqs/faq_form.html'
    success_url = reverse_lazy('web:faq_list')
    permission_required = 'db.change_faq'
    login_url = 'web:login'

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class FaqDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Faq
    template_name = 'faqs/faq_confirm_delete.html'
    success_url = reverse_lazy('web:faq_list')
    permission_required = 'db.delete_faq'
    login_url = 'web:login'

class FaqDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Faq
    template_name = 'faqs/faq_detail.html'
    context_object_name = 'faq'
    permission_required = 'db.view_faq'
    login_url = 'web:login'


# --- Vistas para Denuncias (Consolidadas) ---
class DenunciaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Denuncias
    template_name = 'denuncias/denuncia_list.html'
    context_object_name = 'denuncias'
    permission_required = 'db.view_denuncias'
    login_url = 'web:login'
    ordering = ['-created_at']
    paginate_by = 20

    def get_queryset(self):
        """Listado con filtros básicos de búsqueda."""
        from django.db.models import Q

        qs = Denuncias.objects.select_related(
            'ciudadano', 'tipo_denuncia', 'asignado_departamento', 'asignado_funcionario'
        )

        # Restricción por usuario (no superuser)
        if not self.request.user.is_superuser:
            qs = qs.filter(
                Q(asignado_funcionario__web_user=self.request.user)
                | Q(denunciaasignaciones__funcionario__web_user=self.request.user,
                    denunciaasignaciones__activo=True)
            ).distinct()

        # Filtros GET
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo_denuncia_id=tipo)

        departamento = self.request.GET.get('departamento')
        if departamento:
            qs = qs.filter(asignado_departamento_id=departamento)

        funcionario = self.request.GET.get('funcionario')
        if funcionario:
            qs = qs.filter(asignado_funcionario_id=funcionario)

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(ciudadano__nombres__icontains=q)
                | Q(ciudadano__apellidos__icontains=q)
                | Q(ciudadano__cedula__icontains=q)
                | Q(descripcion__icontains=q)
                | Q(referencia__icontains=q)
            )

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'estado_actual': self.request.GET.get('estado', ''),
                'tipo_actual': self.request.GET.get('tipo', ''),
                'departamento_actual': self.request.GET.get('departamento', ''),
                'funcionario_actual': self.request.GET.get('funcionario', ''),
                'q': self.request.GET.get('q', ''),
                'tipos_denuncia': TiposDenuncia.objects.filter(activo=True),
                'departamentos': Departamentos.objects.filter(activo=True),
                'funcionarios': Funcionarios.objects.filter(activo=True),
            }
        )
        return context

class DenunciaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Denuncias
    template_name = 'denuncias/denuncia_detail.html'
    context_object_name = 'denuncia'
    permission_required = 'db.view_denuncias'
    login_url = 'web:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        denuncia = self.object
        
        # Traer toda la información relacionada
        context['asignaciones'] = DenunciaAsignaciones.objects.filter(denuncia=denuncia).select_related('funcionario').order_by('-asignado_en')
        context['evidencias'] = DenunciaEvidencias.objects.filter(denuncia=denuncia).order_by('-created_at')
        
        # Paginar historial: 10 elementos por página
        historial_queryset = DenunciaHistorial.objects.filter(denuncia=denuncia).select_related('cambiado_por_funcionario').order_by('-created_at')
        paginator = Paginator(historial_queryset, 3)
        page_number = self.request.GET.get('historial_page')
        try:
            historial_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            historial_page = paginator.page(1)
        
        context['historial'] = historial_page
        context['historial_paginator'] = paginator

        respuestas_queryset = DenunciaRespuestas.objects.filter(denuncia=denuncia).select_related('funcionario').order_by('-created_at')

        context['respuestas'] = respuestas_queryset
        
        # Intentar obtener firma si existe (OneToOne)
        try:
            context['firma'] = denuncia.denunciafirmas
        except DenunciaFirmas.DoesNotExist:
            context['firma'] = None
            
        return context

class DenunciaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Denuncias
    form_class = DenunciaForm
    template_name = 'denuncias/denuncia_form.html'
    context_object_name = 'denuncia'
    success_url = reverse_lazy('web:denuncia_list')
    permission_required = 'db.change_denuncias'
    login_url = 'web:login'

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        estado_anterior = Denuncias.objects.get(pk=self.object.pk).estado
        if estado_anterior != form.instance.estado:
            DenunciaHistorial.objects.create(
                **{
                    "id": get_uuid(),
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": form.instance.estado,
                    "comentario": "Actualización",
                    "cambiado_por_funcionario": self.request.user.funcionarios if hasattr(self.request.user, 'funcionarios') else None,
                    "created_at": timezone.now(),
                    "denuncia_id": self.object.id
                }
            )
        return super().form_valid(form)

class DenunciaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Denuncias
    template_name = 'denuncias/denuncia_confirm_delete.html'
    success_url = reverse_lazy('web:denuncia_list')
    permission_required = 'db.delete_denuncias'
    login_url = 'web:login'


# --- Crear respuesta para una denuncia ---
@login_required
@permission_required('db.add_denunciarespuestas', raise_exception=True)
def crear_respuesta_denuncia(request, pk):
    """Crea una nueva respuesta en el hilo de la denuncia."""
    if request.method != 'POST':
        return redirect('web:denuncia_detail', pk=pk)

    denuncia = get_object_or_404(Denuncias, pk=pk)
    form = DenunciaRespuestaForm(request.POST)
    if form.is_valid():
        DenunciaHistorial.objects.create(
            **{
                "id": get_uuid(),
                "estado_anterior": denuncia.estado,
                "estado_nuevo": denuncia.estado,
                "comentario": "Nueva respuesta añadida.",
                "cambiado_por_funcionario": Funcionarios.objects.get(user=request.user) if hasattr(request.user, 'funcionarios') else None,
                "created_at": timezone.now(),
                "denuncia_id": denuncia.id
            }
            )
        DenunciaRespuestas.objects.create(
            id=get_uuid(),
            denuncia=denuncia,
            funcionario=request.user.funcionarios if hasattr(request.user, 'funcionarios') else None,
            mensaje=form.cleaned_data['mensaje'],
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
    # Volver al detalle de la denuncia (mantener paginación por defecto)
    return redirect('web:denuncia_detail', pk=pk)


# ==================== TipoDenunciaDepartamento Views ====================
class TipoDenunciaDepartamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = TipoDenunciaDepartamento
    template_name = 'tipo_denuncia_departamento/tipo_denuncia_departamento_list.html'
    context_object_name = 'asignaciones'
    permission_required = 'db.view_tipodenunciadepartamento'
    login_url = 'web:login'
    paginate_by = 15

    def get_queryset(self):
        return TipoDenunciaDepartamento.objects.select_related('tipo_denuncia', 'departamento').all()

class TipoDenunciaDepartamentoDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = TipoDenunciaDepartamento
    template_name = 'tipo_denuncia_departamento/tipo_denuncia_departamento_detail.html'
    context_object_name = 'asignacion'
    permission_required = 'db.view_tipodenunciadepartamento'
    login_url = 'web:login'

    def get_queryset(self):
        return TipoDenunciaDepartamento.objects.select_related('tipo_denuncia', 'departamento')

class TipoDenunciaDepartamentoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TipoDenunciaDepartamento
    form_class = TipoDenunciaDepartamentoForm
    template_name = 'tipo_denuncia_departamento/tipo_denuncia_departamento_form.html'
    success_url = reverse_lazy('web:tipo_denuncia_departamento_list')
    permission_required = 'db.add_tipodenunciadepartamento'
    login_url = 'web:login'

    def form_valid(self, form):
        form.instance.created_at = timezone.now()
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class TipoDenunciaDepartamentoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TipoDenunciaDepartamento
    form_class = TipoDenunciaDepartamentoForm
    template_name = 'tipo_denuncia_departamento/tipo_denuncia_departamento_form.html'
    success_url = reverse_lazy('web:tipo_denuncia_departamento_list')
    permission_required = 'db.change_tipodenunciadepartamento'
    login_url = 'web:login'
    context_object_name = 'asignacion'

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class TipoDenunciaDepartamentoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TipoDenunciaDepartamento
    template_name = 'tipo_denuncia_departamento/tipo_denuncia_departamento_confirm_delete.html'
    success_url = reverse_lazy('web:tipo_denuncia_departamento_list')
    permission_required = 'db.delete_tipodenunciadepartamento'
    login_url = 'web:login'
    context_object_name = 'asignacion'


# ==================== TiposDenuncia Views ====================
class TiposDenunciaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = TiposDenuncia
    template_name = 'tipos_denuncia/tipos_denuncia_list.html'
    context_object_name = 'tipos_denuncia'
    permission_required = 'db.view_tiposdenuncia'
    login_url = 'web:login'
    ordering = ['-created_at']
    paginate_by = 15

class TiposDenunciaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = TiposDenuncia
    template_name = 'tipos_denuncia/tipos_denuncia_detail.html'
    context_object_name = 'tipo_denuncia'
    permission_required = 'db.view_tiposdenuncia'
    login_url = 'web:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener el departamento asignado si existe
        try:
            asignacion = TipoDenunciaDepartamento.objects.select_related('departamento').get(tipo_denuncia=self.object)
            context['departamento_asignado'] = asignacion.departamento
        except TipoDenunciaDepartamento.DoesNotExist:
            context['departamento_asignado'] = None
        
        # Contar denuncias de este tipo
        context['total_denuncias'] = Denuncias.objects.filter(tipo_denuncia=self.object).count()
        return context

class TiposDenunciaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TiposDenuncia
    form_class = TiposDenunciaForm
    template_name = 'tipos_denuncia/tipos_denuncia_form.html'
    success_url = reverse_lazy('web:tipos_denuncia_list')
    permission_required = 'db.add_tiposdenuncia'
    login_url = 'web:login'

    def form_valid(self, form):
        form.instance.created_at = timezone.now()
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class TiposDenunciaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TiposDenuncia
    form_class = TiposDenunciaForm
    template_name = 'tipos_denuncia/tipos_denuncia_form.html'
    success_url = reverse_lazy('web:tipos_denuncia_list')
    permission_required = 'db.change_tiposdenuncia'
    login_url = 'web:login'
    context_object_name = 'tipo_denuncia'

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class TiposDenunciaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TiposDenuncia
    template_name = 'tipos_denuncia/tipos_denuncia_confirm_delete.html'
    success_url = reverse_lazy('web:tipos_denuncia_list')
    permission_required = 'db.delete_tiposdenuncia'
    login_url = 'web:login'
    context_object_name = 'tipo_denuncia'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Verificar si tiene denuncias asociadas
        context['total_denuncias'] = Denuncias.objects.filter(tipo_denuncia=self.object).count()
        return context


class MisDenunciasListView(LoginRequiredMixin, ListView):
    """Vista para que un funcionario vea sus denuncias asignadas"""
    model = Denuncias
    template_name = 'denuncias/mis_denuncias_list.html'
    context_object_name = 'denuncias'
    paginate_by = 10
    login_url = 'web:login'
    
    def get_queryset(self):
        """Filtra las denuncias asignadas al funcionario actual"""
        try:
            # Obtener el funcionario asociado al usuario actual
            funcionario = Funcionarios.objects.get(web_user=self.request.user)
            
            # Filtrar denuncias asignadas directamente al funcionario
            # o a través de asignaciones activas
            from django.db.models import Q
            
            queryset = Denuncias.objects.filter(
                Q(asignado_funcionario=funcionario) |
                Q(denunciaasignaciones__funcionario=funcionario, denunciaasignaciones__activo=True)
            ).distinct().select_related(
                'ciudadano',
                'tipo_denuncia',
                'asignado_departamento',
                'asignado_funcionario'
            ).order_by('-created_at')
            
            # Filtros adicionales por parámetros GET
            estado = self.request.GET.get('estado')
            if estado:
                queryset = queryset.filter(estado=estado)
            
            tipo_denuncia = self.request.GET.get('tipo_denuncia')
            if tipo_denuncia:
                queryset = queryset.filter(tipo_denuncia_id=tipo_denuncia)
            
            return queryset
            
        except Funcionarios.DoesNotExist:
            # Si el usuario no es un funcionario, retornar queryset vacío
            return Denuncias.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            funcionario = Funcionarios.objects.get(web_user=self.request.user)
            context['funcionario'] = funcionario
            
            # Estadísticas de las denuncias del funcionario
            queryset = self.get_queryset()
            context['total_denuncias'] = queryset.count()
            context['denuncias_pendientes'] = queryset.filter(estado='pendiente').count()
            context['denuncias_en_proceso'] = queryset.filter(estado='en_proceso').count()
            context['denuncias_resueltas'] = queryset.filter(estado='resuelto').count()
            
            # Tipos de denuncia para filtro
            context['tipos_denuncia'] = TiposDenuncia.objects.filter(activo=True)
            
            # Estado actual seleccionado en filtro
            context['estado_actual'] = self.request.GET.get('estado', '')
            context['tipo_denuncia_actual'] = self.request.GET.get('tipo_denuncia', '')
            
        except Funcionarios.DoesNotExist:
            context['funcionario'] = None
            context['es_funcionario'] = False
            
        return context
