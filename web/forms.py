from django.urls import reverse_lazy
from db.models import *
from .models import Menus
from django import forms
from django.views.generic.edit import (CreateView, UpdateView, DeleteView)
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from django.contrib import messages


# Definir PermissionRequiredMixin personalizado aquí para evitar imports circulares
from django.contrib.auth.mixins import PermissionRequiredMixin as DjangoPermissionRequiredMixin
from django.shortcuts import render

ESTADO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('en_proceso', 'En Proceso'),
    ('resuelto', 'Resuelto'),
]

class PermissionRequiredMixin(DjangoPermissionRequiredMixin):
    """Override del PermissionRequiredMixin que renderiza un template personalizado"""
    
    def handle_no_permission(self):
        """Renderiza la página de error 403 personalizada en lugar de lanzar excepción"""
        return render(self.request, 'errors/403.html', status=403)


class CrudMessageMixin:
    """Mixin para agregar mensajes automáticos en operaciones CRUD con izitoast"""
    
    def get_create_message(self, obj):
        """Mensaje personalizado para creación"""
        return f"{self.model._meta.verbose_name} creado correctamente"
    
    def get_update_message(self, obj):
        """Mensaje personalizado para actualización"""
        return f"{self.model._meta.verbose_name} actualizado correctamente"
    
    def get_delete_message(self, obj):
        """Mensaje personalizado para eliminación"""
        return f"{self.model._meta.verbose_name} eliminado correctamente"
    
    def form_valid(self, form):
        """Interceptar form_valid para agregar mensaje en Create y Update"""
        response = super().form_valid(form)
        
        # Determinar el tipo de operación
        is_create = not self.object.pk or self.object.pk == form.instance.pk
        
        if isinstance(self, CreateView):
            message = self.get_create_message(self.object)
            messages.success(self.request, message)
        elif isinstance(self, UpdateView):
            message = self.get_update_message(self.object)
            messages.success(self.request, message)
        
        return response
    
    def delete(self, request, *args, **kwargs):
        """Interceptar delete para agregar mensaje en Delete"""
        obj = self.get_object()
        message = self.get_delete_message(obj)
        messages.success(request, message)
        return super().delete(request, *args, **kwargs)

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menus
        fields = ['nombre', 'url', 'icono', 'padre', 'orden', 'permisos']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del menú'}),
            'url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'URL o nombre de la ruta (e.g. web:home)'}),
            'icono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Clase de icono (bi bi-house)'}),
            'padre': ModelSelect2Widget(
                model=Menus,
                search_fields=['nombre__icontains'],
                attrs={'class': 'form-control'}
            ),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'permisos': ModelSelect2MultipleWidget(
                model=Permission,
                search_fields=['name__icontains'],
                attrs={'class': 'form-control'}
            ),
        }
        labels = {
            'nombre': 'Nombre del Menú',
            'url': 'URL / Ruta',
            'icono': 'Icono (Bootstrap Icons)',
            'padre': 'Menú Padre',
            'orden': 'Orden de visualización',
            'permisos': 'Roles permitidos (Vacío = Todos)',
        }
        help_texts = {
            'permisos': 'Escribe para buscar permisos.',
            'url': 'Puede usar rutas nombradas de Django (ej: web:dashboard) o URLs absolutas.',
            'padre': 'Deje en blanco si es un menú principal.',
        }

class GrupoForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del grupo'}),
            'permissions': ModelSelect2MultipleWidget(
                model=Permission,
                search_fields=['name__icontains'],
                attrs={'class': 'form-control'}
            ),
        }
        labels = {
            'name': 'Nombre del Grupo',
            'permissions': 'Permisos',
        }

class FuncionarioForm(forms.ModelForm):
    web_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label='Usuario Web',
        widget=ModelSelect2Widget(
            model=User,
            search_fields=['username__icontains', 'email__icontains'],
            attrs={'id': 'id_web_user', 'data-placeholder': 'Buscar usuario...', 'class': 'form-control'}
        )
    )
    
    departamento = forms.ModelChoiceField(
        queryset=Departamentos.objects.filter(activo=True),
        label='Departamento',
        widget=ModelSelect2Widget(
            model=Departamentos,
            search_fields=['nombre__icontains'],
            attrs={'data-placeholder': 'Buscar departamento...', 'class': 'form-control'}
        ),
        required=False
    )
    
    class Meta:
        model = Funcionarios
        fields = ['web_user', 'cedula', 'nombres', 'apellidos', 'telefono', 'departamento', 'cargo', 'activo']
        widgets = {
            'cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese la cédula'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese los nombres', 'readonly': 'readonly'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese los apellidos', 'readonly': 'readonly'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el teléfono'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el cargo'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar web_user: solo mostrar los que no tienen funcionario asignado
        users_sin_funcionario = User.objects.exclude(funcionarios__isnull=False).order_by('username')
        
        # Si es una edición, incluir el usuario actual del funcionario
        if self.instance and self.instance.pk:
            current_user = self.instance.web_user
            if current_user:
                users_sin_funcionario = users_sin_funcionario | User.objects.filter(pk=current_user.pk)
            self.fields['web_user'].disabled = True
            self.fields['web_user'].help_text = "No se puede cambiar el usuario una vez creado el funcionario."
        
        self.fields['web_user'].queryset = users_sin_funcionario.order_by('username')
        
        # Departamentos activos
        self.fields['departamento'].queryset = Departamentos.objects.filter(activo=True).order_by('nombre')

    def save(self, commit=True):
        instance = super().save(commit=False)
        now = timezone.now()
        if not instance.pk:  # Si es un nuevo registro
            instance.created_at = now
        instance.updated_at = now
        if commit:
            instance.save()
        return instance

class FuncionariosCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Funcionarios
    form_class = FuncionarioForm
    template_name = 'funcionarios/funcionario_form.html'
    success_url = '/web/funcionarios/'
    permission_required = 'db.add_funcionarios'
    login_url = 'web:login'
    permission_denied_message = 'No tienes permiso para crear funcionarios'

    

class FuncionariosDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Funcionarios
    template_name = 'funcionarios/funcionario_detail.html'
    success_url = '/web/funcionarios/'
    permission_required = 'db.view_funcionarios'
    login_url = 'web:login'

class FuncionariosUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Funcionarios
    form_class = FuncionarioForm
    template_name = 'funcionarios/funcionario_form.html'
    success_url = '/web/funcionarios/'
    permission_required = 'db.change_funcionarios'
    login_url = 'web:login'

class FuncionariosDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Funcionarios
    template_name = 'funcionarios/funcionario_confirm_delete.html'
    success_url = '/web/funcionarios/'
    permission_required = 'db.delete_funcionarios'
    login_url = 'web:login'

class FuncionariosListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Funcionarios
    template_name = 'funcionarios/funcionario_list.html'
    context_object_name = 'funcionarios'
    paginate_by = 10
    permission_required = 'db.view_funcionarios'
    login_url = 'web:login'
    def get_queryset(self):
        return Funcionarios.objects.all().order_by('web_user__email')


class DepartamentoForm(forms.ModelForm):
    class Meta:
        model = Departamentos
        fields = ['nombre', 'activo', 'color_hex']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre del departamento'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'color_hex': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        now = timezone.now()
        if not instance.pk:  # Si es un nuevo registro
            instance.created_at = now
        instance.updated_at = now
        if commit:
            instance.save()
        return instance


class DepartamentosCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Departamentos
    form_class = DepartamentoForm
    template_name = 'departamentos/departamento_form.html'
    success_url = '/web/departamentos/'
    permission_required = 'db.add_departamentos'
    login_url = 'web:login'

class DepartamentosDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Departamentos
    template_name = 'departamentos/departamento_detail.html'
    permission_required = 'db.view_departamentos'
    login_url = 'web:login'

class DepartamentosUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Departamentos
    form_class = DepartamentoForm
    template_name = 'departamentos/departamento_form.html'
    success_url = '/web/departamentos/'
    permission_required = 'db.change_departamentos'
    login_url = 'web:login'

class DepartamentosDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Departamentos
    template_name = 'departamentos/departamento_confirm_delete.html'
    success_url = '/web/departamentos/'
    permission_required = 'db.delete_departamentos'
    login_url = 'web:login'

class DepartamentosListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Departamentos
    template_name = 'departamentos/departamento_list.html'
    context_object_name = 'departamentos'
    paginate_by = 5
    permission_required = 'db.view_departamentos'
    login_url = 'web:login'
    def get_queryset(self):
        return Departamentos.objects.all().order_by('nombre')

class WebUserForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=ModelSelect2MultipleWidget(
            model=Group,
            search_fields=['name__icontains'],
            attrs={'class': 'form-control', 'multiple': 'multiple', 'data-placeholder': 'Buscar grupos...'}
        )
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco para no cambiar'}),
        help_text='Dejar en blanco para mantener la contraseña actual'
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions',
            'last_login', 'date_joined'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el usuario'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el correo'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el apellido'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'user_permissions': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'last_login': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'date_joined': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajustes: queryset para selects múltiples y deshabilitar campos no editables
        self.fields['groups'].queryset = Group.objects.all()
        self.fields['user_permissions'].queryset = Permission.objects.all()
        # No permitir editar timestamps desde el formulario
        if 'last_login' in self.fields:
            self.fields['last_login'].disabled = True
        if 'date_joined' in self.fields:
            self.fields['date_joined'].disabled = True
        # En edición, no mostrar campo password en Meta, solo lo tenemos aquí
        if self.instance and self.instance.pk:
            self.fields['password'].initial = ''

class WebUserCreateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = WebUserForm
    template_name = 'webusers/webuser_form.html'
    success_url = reverse_lazy('web:webuser_list')
    permission_required = 'auth.add_user'
    login_url = 'web:login'
    
    def form_valid(self, form):
        user = form.save(commit=False)
        password = form.cleaned_data.get('password')
        # Al crear, la contraseña es obligatoria
        if password:
            user.set_password(password)
        user.save()
        form.save_m2m()
        return super().form_valid(form)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # asegurar queryset y atributos en la vista también
        form.fields['groups'].queryset = Group.objects.all()
        form.fields['user_permissions'].queryset = Permission.objects.all()
        if 'last_login' in form.fields:
            form.fields['last_login'].disabled = True
        if 'date_joined' in form.fields:
            form.fields['date_joined'].disabled = True
        # En creación, password es requerida
        form.fields['password'].required = True
        form.fields['password'].help_text = ''
        return form

class WebUserDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = User
    template_name = 'webusers/webuser_detail.html'
    context_object_name = 'web_user_detail'
    success_url = reverse_lazy('web:webuser_list')
    permission_required = 'auth.view_user'
    login_url = 'web:login'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = self.object.groups.all()
        context['permissions'] = self.object.user_permissions.all()
        return context

class WebUserUpdateView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = WebUserForm
    template_name = 'webusers/webuser_form.html'
    context_object_name = 'web_user_update'
    success_url = reverse_lazy('web:webuser_list')
    permission_required = 'auth.change_user'
    login_url = 'web:login'
    
    def form_valid(self, form):
        user = form.save(commit=False)
        password = form.cleaned_data.get('password')
        # Si se proporcionó una contraseña, actualizarla de forma segura
        if password:
            user.set_password(password)
        user.save()
        # Guardar relaciones many-to-many
        form.save_m2m()
        return super().form_valid(form)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # asegurar queryset y atributos en la vista también
        form.fields['groups'].queryset = Group.objects.all()
        form.fields['user_permissions'].queryset = Permission.objects.all()
        if 'last_login' in form.fields:
            form.fields['last_login'].disabled = True
        if 'date_joined' in form.fields:
            form.fields['date_joined'].disabled = True
        # En edición, password es opcional
        form.fields['password'].help_text = 'Dejar en blanco para no cambiar la contraseña'
        return form

class WebUserDeleteView(CrudMessageMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    template_name = 'webusers/webuser_confirm_delete.html'
    context_object_name = 'web_user_delete'
    success_url = reverse_lazy('web:webuser_list')
    permission_required = 'auth.delete_user'
    login_url = 'web:login'

class WebUserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'webusers/webuser_list.html'
    context_object_name = 'webusers'
    paginate_by = 10
    permission_required = 'auth.view_user'
    login_url = 'web:login'
    def get_queryset(self):
        user_qs = User.objects.all().order_by('username').prefetch_related('funcionarios_set')
        return user_qs


class FaqForm(forms.ModelForm):
    class Meta:
        model = Faq
        fields = ['pregunta', 'respuesta', 'visible']
        widgets = {
            'pregunta': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Escriba la pregunta aquí'}),
            'respuesta': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Escriba la respuesta detallada'}),
            'visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'pregunta': 'Pregunta Frecuente',
            'respuesta': 'Respuesta',
            'visible': 'Visible para el público',
        }


class DenunciaForm(forms.ModelForm):
    class Meta:
        model = Denuncias
        fields = ['estado', 'asignado_departamento', 'asignado_funcionario', 'descripcion', 'tipo_denuncia', 'referencia', 'direccion_texto']
        widgets = {
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'referencia': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'direccion_texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'estado': forms.Select(attrs={'class': 'form-select'}, choices=ESTADO_CHOICES),
            'asignado_departamento': ModelSelect2Widget(
                model=Departamentos,
                search_fields=['nombre__icontains'],
                attrs={'class': 'form-control'}
            ),
            'asignado_funcionario': ModelSelect2Widget(
                model=Funcionarios,
                search_fields=['nombres__icontains', 'apellidos__icontains', 'cedula__icontains'],
                attrs={'class': 'form-control'}
            ),
            'tipo_denuncia': ModelSelect2Widget(
                model=TiposDenuncia,
                search_fields=['nombre__icontains'],
                attrs={'class': 'form-control'}
            ),
        }

class DenunciaRespuestaForm(forms.ModelForm):
    class Meta:
        model = DenunciaRespuestas
        fields = ['mensaje']
        widgets = {
            'mensaje': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Escriba su respuesta aquí...'})
        }

class DenunciaAsignacionForm(forms.ModelForm):
    class Meta:
        model = DenunciaAsignaciones
        fields = ['funcionario']
        widgets = {
            'funcionario': ModelSelect2Widget(
                model=Funcionarios,
                search_fields=['nombres__icontains', 'apellidos__icontains', 'cedula__icontains'],
                attrs={'class': 'form-control'}
            )
        }

class TipoDenunciaDepartamentoForm(forms.ModelForm):
    class Meta:
        model = TipoDenunciaDepartamento
        fields = ['tipo_denuncia', 'departamento']
        widgets = {
            'tipo_denuncia': ModelSelect2Widget(
                model=TiposDenuncia,
                search_fields=['nombre__icontains'],
                attrs={'class': 'form-control'}
            ),
            'departamento': ModelSelect2Widget(
                model=Departamentos,
                search_fields=['nombre__icontains'],
                attrs={'class': 'form-control'}
            )
        }
        labels = {
            'tipo_denuncia': 'Tipo de Denuncia',
            'departamento': 'Departamento Asignado'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar tipos de denuncia activos
        self.fields['tipo_denuncia'].queryset = TiposDenuncia.objects.filter(activo=True)
        # Solo mostrar departamentos activos
        self.fields['departamento'].queryset = Departamentos.objects.filter(activo=True)

class TiposDenunciaForm(forms.ModelForm):
    class Meta:
        model = TiposDenuncia
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Baches en la vía'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descripción del tipo de denuncia'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'nombre': 'Nombre del Tipo de Denuncia',
            'descripcion': 'Descripción',
            'activo': 'Activo'
        }
        help_texts = {
            'activo': 'Marca esta casilla si este tipo de denuncia debe estar disponible para los ciudadanos.'
        }


