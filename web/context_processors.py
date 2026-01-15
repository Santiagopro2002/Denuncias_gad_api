from .models import Menus

def menu_context(request):
    """
    Context processor que agrega los menús principales al contexto de todos los templates
    filtrando por si el usuario pertenece a uno de los grupos permitidos.
    """
    if not request.user.is_authenticated:

        return {'menus_principales': []}

    user_group_ids = set(request.user.groups.values_list('id', flat=True))
    is_superuser = request.user.is_superuser

    menus_principales = Menus.objects.filter(padre__isnull=True).prefetch_related('permisos', 'submenus__permisos').order_by('orden')
    
    menus_visibles = []

    for menu in menus_principales:
        permisos_menu = menu.permisos.all()
        acceso_menu = False
        
        if is_superuser:
            acceso_menu = True
        elif not permisos_menu.exists():
            acceso_menu = True
        else:
            for grupo in permisos_menu:
                if grupo.id in user_group_ids:
                    acceso_menu = True
                    break
        
        if not acceso_menu:
            continue

        submenus_visibles = []
        for submenu in menu.submenus.all().order_by('orden'):
            permisos_submenu = submenu.permisos.all()
            acceso_submenu = False
            
            if is_superuser:
                acceso_submenu = True
            elif not permisos_submenu.exists():
                acceso_submenu = True
            else:
                for grupo in permisos_submenu:
                    if grupo.id in user_group_ids:
                        acceso_submenu = True
                        break
            
            if acceso_submenu:
                submenus_visibles.append(submenu)
        
        menu.submenus_list = submenus_visibles
        menus_visibles.append(menu)

    return {
        'menus_principales': menus_visibles
    }