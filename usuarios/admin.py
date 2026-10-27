from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario

# Register your models here.


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Classroom Boost", {"fields": ("tipo",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Classroom Boost", {"fields": ("tipo",)}),
    )
