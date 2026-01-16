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
from .forms import CrudMessageMixin
from openai import OpenAI
from django.conf import settings
from chartkick.django import PieChart, BarChart, ColumnChart, LineChart

api_key = getattr(settings, 'OPENAI_API_KEY', None)
client = OpenAI(api_key=api_key)

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
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            is_funcionario = Funcionarios.objects.filter(web_user=request.user).exists()
            if is_funcionario:
                return redirect('web:dashboard')
            else:
                return redirect('web:mis_denuncias')
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.is_authenticated:
            is_funcionario = Funcionarios.objects.filter(web_user=self.request.user).exists()
            if is_funcionario:
                return reverse_lazy('web:dashboard')
            else:
                return reverse_lazy('web:mis_denuncias')
        return reverse_lazy('web:home')

def home_view(request):
    """Vista para la página de inicio"""
    if request.user.is_authenticated:
        return redirect('web:dashboard')
    from db.models import Faq
    faqs = Faq.objects.filter(visible=True)
    return render(request, 'home.html', {'faqs': faqs})


@login_required
def get_user_data_ajax(request, user_id):
    """Vista AJAX que devuelve los datos del usuario para autocompletar el formulario"""
    from django.http import JsonResponse
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({
            'success': True,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or '',
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado'})

    
def dashboard_view(request):
    """Vista para el panel de control con KPIs"""
    from django.db.models import Count, Q
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models.functions import TruncWeek, TruncMonth
    # Importar los gráficos necesarios
    from chartkick.django import PieChart, BarChart, ColumnChart, LineChart

    funcionario = Funcionarios.objects.filter(web_user=request.user).first()

    if not funcionario:
        return render(request, 'errors/403.html', status=403)

    current_user_department = funcionario.departamento if funcionario else None

    # Filtrar todo por el departamento del usuario si existe
    denuncias_qs = Denuncias.objects.all()
    funcionarios_qs = Funcionarios.objects.all()
    departamentos_qs = Departamentos.objects.all()

    if current_user_department:
        denuncias_qs = denuncias_qs.filter(asignado_departamento=current_user_department)
        funcionarios_qs = funcionarios_qs.filter(departamento=current_user_department)
        departamentos_qs = departamentos_qs.filter(pk=current_user_department.pk)
    
    # Período de últimos 30 días
    fecha_hace_30_dias = timezone.now() - timedelta(days=30)

    # Útlima semana a partir de hoy
    fecha_hace_7_dias = timezone.now() - timedelta(days=7)
    
    # KPI 1: Total de Denuncias
    total_denuncias = denuncias_qs.count()
    denuncias_este_mes = denuncias_qs.filter(created_at__gte=fecha_hace_30_dias).count()
    
    # KPI 2: Estados de Denuncias
    denuncias_pendientes = denuncias_qs.filter(estado='pendiente').count()
    denuncias_en_proceso = denuncias_qs.filter(estado='en_proceso').count()
    denuncias_resueltas = denuncias_qs.filter(estado='resuelto').count()

    chart_kpi2 = ColumnChart({
        'Pendientes': denuncias_pendientes,
        'En Proceso': denuncias_en_proceso,
        'Resueltas': denuncias_resueltas,
    },
    title="Denuncias por estado",
    download={'filename': 'chart_kpi2'}
    )
    
    # KPI 3: Total de Ciudadanos (global)
    total_ciudadanos = Ciudadanos.objects.count()
    ciudadanos_este_mes = Ciudadanos.objects.filter(created_at__gte=fecha_hace_30_dias).count()
    
    # KPI 4: Total de Funcionarios (filtrados por departamento si aplica)
    total_funcionarios = funcionarios_qs.count()
    funcionarios_activos = funcionarios_qs.filter(activo=True).count()
    
    # KPI 5: Total de Departamentos (filtrado si aplica)
    total_departamentos = departamentos_qs.count()
    departamentos_activos = departamentos_qs.filter(activo=True).count()
    
    # KPI 6: Promedio de denuncias por departamento
    promedio_denuncias_depto = total_denuncias / max(departamentos_activos, 1)
    
    # KPI 7: Denuncias por tipo (filtradas)
    denuncias_por_tipo = denuncias_qs.values('tipo_denuncia__nombre').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    chart_kpi7 = PieChart(
        dict((item['tipo_denuncia__nombre'], item['count']) for item in denuncias_por_tipo),
        title="Denuncias por tipo",
        download={'filename': 'chart_kpi7'},
        donut=True
        )
    
    # KPI 8: Departamentos con más denuncias (filtradas)
    departamentos_con_denuncias = denuncias_qs.filter(
        asignado_departamento__isnull=False
    ).values('asignado_departamento__nombre').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # KPI 9: Número de denuncias por día de la última semana
    denuncias_ultima_semana = denuncias_qs.filter(
        created_at__gte=fecha_hace_7_dias
    ).extra({
        'dia': "DATE(created_at)"
    }).values('dia').annotate(
        count=Count('id')
    ).order_by('dia')

    kpi9_chart_data = {item['dia'].strftime('%Y-%m-%d'): item['count'] for item in denuncias_ultima_semana}
    chart_kpi9 = LineChart(
        kpi9_chart_data,
        title="Denuncias en la última semana",
        xtitle="Día",
        ytitle="Cantidad",
        download={'filename': 'chart_kpi9'}
    )
    
    # 1. Diagrama de barra por numero de denuncias por departamento
    denuncias_por_departamento_data = denuncias_qs.filter(
        asignado_departamento__isnull=False
    ).values('asignado_departamento__nombre', 'asignado_departamento__color_hex').annotate(
        count=Count('id')
    ).order_by('-count')
    
    dept_data = {}
    dept_colors = []
    
    for item in denuncias_por_departamento_data:
        dept_data[item['asignado_departamento__nombre']] = item['count']
        # Usar color del departamento o un default si no tiene
        dept_colors.append(item['asignado_departamento__color_hex'] or "#0d6efd")

    chart_denuncias_departamento = BarChart(
        dept_data,
        title="Número de Denuncias por Departamento",
        xtitle="Cantidad",
        ytitle="Departamento",
        colors=dept_colors
    )

    # 2. Diagrama de barras por ciudadano con más denuncias (Top 10)
    ciudadanos_top_data = denuncias_qs.values(
        'ciudadano__nombres', 'ciudadano__apellidos'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    chart_ciudadanos_top = BarChart(
        {f"{item['ciudadano__nombres']} {item['ciudadano__apellidos']}": item['count'] for item in ciudadanos_top_data},
        title="Ciudadanos con más Denuncias (Top 10)",
        xtitle="Cantidad",
        ytitle="Ciudadano"
    )

    # 3. Denuncias por semana
    denuncias_semana_data = denuncias_qs.annotate(
        semana=TruncWeek('created_at')
    ).values('semana').annotate(
        count=Count('id')
    ).order_by('semana')[:3]
    
    chart_denuncias_semana = LineChart(
        {item['semana'].strftime('%Y-%m-%d'): item['count'] for item in denuncias_semana_data},
        title="Denuncias por Semana",
        xtitle="Semana",
        ytitle="Cantidad",
        download={'filename': 'chart_denuncias_semana'}
    )

    # 4. Denuncias por mes
    denuncias_mes_data = denuncias_qs.annotate(
        mes=TruncMonth('created_at')
    ).values('mes').annotate(
        count=Count('id')
    ).order_by('mes')[:5]

    chart_denuncias_mes = LineChart(
        {item['mes'].strftime('%Y-%m'): item['count'] for item in denuncias_mes_data},
        title="Denuncias por Mes",
        xtitle="Mes",
        ytitle="Cantidad"
    )

    # 5. Pastel donde se vea el total de denuncias resueltas vs pendientes
    chart_estado_denuncias = PieChart(
        {
            'Resueltas': denuncias_resueltas,
            'Pendientes': denuncias_pendientes,
            'En Proceso': denuncias_en_proceso
        },
        title="Estado de Denuncias (Resueltas vs Pendientes)",
        donut=True
    )
    
    # Tasa de resolución
    if total_denuncias > 0:
        tasa_resolucion = (denuncias_resueltas / total_denuncias) * 100
    else:
        tasa_resolucion = 0
    
    # Denuncias con coordenadas para el mapa
    denuncias_mapa = denuncias_qs.select_related(
        'ciudadano', 'tipo_denuncia', 'asignado_departamento'
    )[:100]  # Limitar a 100 para rendimiento
    
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
        'chart_denuncias_departamento': chart_denuncias_departamento,
        'chart_ciudadanos_top': chart_ciudadanos_top,
        'chart_denuncias_semana': chart_denuncias_semana,
        'chart_denuncias_mes': chart_denuncias_mes,
        'chart_estado_denuncias': chart_estado_denuncias,        'funcionarios_activos': funcionarios_activos,
        'total_departamentos': total_departamentos,
        'departamentos_activos': departamentos_activos,
        'promedio_denuncias_depto': round(promedio_denuncias_depto, 2),
        'denuncias_por_tipo': denuncias_por_tipo,
        'departamentos_con_denuncias': departamentos_con_denuncias,
        'tasa_resolucion': round(tasa_resolucion, 1),
        'denuncias_mapa': denuncias_mapa,
        'chart_kpi2': chart_kpi2,
        'chart_kpi7': chart_kpi7,
        'chart_kpi9': chart_kpi9,
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

class GrupoCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Group
    form_class = GrupoForm
    template_name = 'grupos/grupo_form.html'
    success_url = reverse_lazy('web:grupo_list')
    permission_required = 'auth.add_group'
    login_url = 'web:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        if form:
            if form.is_bound:
                selected_ids = [str(pk) for pk in form.data.getlist('permissions')]
            else:
                selected_ids = []
            context['selected_ids'] = selected_ids
        return context

class GrupoUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Group
    form_class = GrupoForm
    template_name = 'grupos/grupo_form.html'
    success_url = reverse_lazy('web:grupo_list')
    permission_required = 'auth.change_group'
    login_url = 'web:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        if form:
            if form.is_bound:
                selected_ids = form.data.getlist('permissions')
            else:
                selected_ids = list(form.instance.permissions.values_list('id', flat=True)) if form.instance.pk else []
            context['selected_ids'] = [str(pk) for pk in selected_ids]
        return context

class GrupoDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Group
    template_name = 'grupos/grupo_detail.html'
    context_object_name = 'grupo'
    permission_required = 'auth.view_group'
    login_url = 'web:login'

class GrupoDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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

class FaqCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
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

class FaqUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Faq
    form_class = FaqForm
    template_name = 'faqs/faq_form.html'
    success_url = reverse_lazy('web:faq_list')
    permission_required = 'db.change_faq'
    login_url = 'web:login'

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)

class FaqDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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

        funcionario = Funcionarios.objects.filter(web_user=self.request.user).first()

        user_is_superuser = self.request.user.is_superuser
        user_has_funcionario = funcionario is not None

        # Restricción por usuario:
        # 1. Superusuarios: Ven todo
        # 2. Funcionarios: Ven solo lo asignado
        # 3. Otros (sin rol): No ven nada
        if user_is_superuser or not user_has_funcionario:
            pass
        elif user_has_funcionario:
            qs = qs.filter(
                Q(asignado_funcionario__web_user=self.request.user)
                | Q(denunciaasignaciones__funcionario__web_user=self.request.user,
                    denunciaasignaciones__activo=True)
            ).distinct()
        else:
            qs = Denuncias.objects.none()

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

class DenunciaUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
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

class DenunciaDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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

class TipoDenunciaDepartamentoCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
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

class TipoDenunciaDepartamentoUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
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

class TipoDenunciaDepartamentoDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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

class TiposDenunciaCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
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

class TiposDenunciaUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
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

class TiposDenunciaDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
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

            if funcionario is None:
                queryset = Denuncias.objects.all().distinct().select_related(
                    'ciudadano',
                    'tipo_denuncia',
                    'asignado_departamento',
                    'asignado_funcionario'
                ).order_by('-created_at')
            else:
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

from django.views.decorators.http import require_POST
import json
import re
@login_required
@require_POST
def llm_response(request, denuncia_id):
    import logging
    from django.http import JsonResponse
    logger = logging.getLogger(__name__)
    
    if not api_key:
        logger.error("OPENAI_API_KEY no encontrada en settings.")
        return JsonResponse({'error': 'Servicio de IA no configurado (Falta API Key)'}, status=503)

    
    try:
        denuncia = Denuncias.objects.select_related(
            'tipo_denuncia',
            'asignado_departamento',
            'asignado_funcionario__web_user'
        ).get(id=denuncia_id)

        if denuncia.estado == 'pendiente':
            denuncia.estado = 'en_proceso'
            denuncia.save()

        prompt = f"""
            Eres un asistente especializado en gestión de denuncias ciudadanas
            para la Municipalidad de Salcedo, Cotopaxi, Ecuador.

            Analiza la siguiente denuncia y responde EXCLUSIVAMENTE en JSON válido
            sin texto adicional, sin markdown, sin comentarios.

            Formato requerido:
            {{
            "resumen": "string",
            "sugerencias_accion": "string"
            }}

            Datos de la denuncia:
            - Ciudadano: {f"{denuncia.ciudadano.nombres} {denuncia.ciudadano.apellidos}" if denuncia.ciudadano else 'Desconocido'}
            - Descripción: {denuncia.descripcion}
            - Referencia: {denuncia.referencia}
            - Tipo: {denuncia.tipo_denuncia.nombre}
            - Estado: {denuncia.estado}
            - Departamento: {denuncia.asignado_departamento.nombre if denuncia.asignado_departamento else 'No asignado'}
            - Funcionario: {denuncia.asignado_funcionario.web_user.get_full_name() if denuncia.asignado_funcionario else 'No asignado'}

            Responde al ciudadano en español, Con un tono empático y cercano para que el ciudadano se sienta escuchado.
            Asegúrate de que el JSON esté correctamente formateado. 

            """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente útil que responde siempre en JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )

        raw_text = response.choices[0].message.content.strip()

        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            if raw_text:
                return JsonResponse({"response": raw_text})
            raise ValueError("La respuesta no contiene JSON válido ni texto recuperable")

        data = json.loads(match.group())
        
        formatted_response = f"RESUMEN:\n{data.get('resumen', '')}\n\nSUERENCIAS DE ACCIÓN:\n{data.get('sugerencias_accion', '')}"
        
        return JsonResponse({"success": True, "response": formatted_response})

    except Denuncias.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Denuncia no encontrada"},
            status=404
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Error al decodificar JSON del modelo"},
            status=500
        )

    except Exception as e:
            return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )
    
@require_POST
@login_required
def resolver_denuncia(request, denuncia_id):
    """Marca una denuncia como resuelta."""
    denuncia = Denuncias.objects.select_related(
            'tipo_denuncia',
            'asignado_departamento',
            'asignado_funcionario__web_user'
        ).get(id=denuncia_id)
    
    denuncia.estado = 'resuelto'
    denuncia.save()

    prompt = f"""
            Eres un asistente especializado en gestión de denuncias ciudadanas
            para la Municipalidad de Salcedo, Cotopaxi, Ecuador.

            Datos de la denuncia:
            - Ciudadano: {f"{denuncia.ciudadano.nombres} {denuncia.ciudadano.apellidos}" if denuncia.ciudadano else 'Desconocido'}
            - Descripción: {denuncia.descripcion}
            - Referencia: {denuncia.referencia}
            - Tipo: {denuncia.tipo_denuncia.nombre}
            - Estado: {denuncia.estado}
            - Departamento: {denuncia.asignado_departamento.nombre if denuncia.asignado_departamento else 'No asignado'}
            - Funcionario: {denuncia.asignado_funcionario.web_user.get_full_name() if denuncia.asignado_funcionario else 'No asignado'}

            Responde al ciudadano en español, sin formato, solo texto.
            Tu tono debe ser empático y cercano para que el ciudadano se sienta escuchado, sobre la resolución de su denuncia.

            """
    response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente útil que siempre responde en texto plano."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )

    raw_text = response.choices[0].message.content.strip()



    #Crear respuesta LLM automática
    DenunciaHistorial.objects.create(
            **{
                "id": get_uuid(),
                "estado_anterior": 'en_proceso',
                "estado_nuevo": 'resuelto',
                "comentario": "Denuncia marcada como resuelta.",
                "cambiado_por_funcionario": Funcionarios.objects.get(user=request.user) if hasattr(request.user, 'funcionarios') else None,
                "created_at": timezone.now(),
                "denuncia_id": denuncia.id
            }
        )
    
    DenunciaRespuestas.objects.create(
            id=get_uuid(),
            denuncia=denuncia,
            funcionario=request.user.funcionarios if hasattr(request.user, 'funcionarios') else None,
            mensaje=raw_text,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

    return redirect('web:denuncia_detail', pk=denuncia_id)