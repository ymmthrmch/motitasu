from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


class MonthlyTargetInline(admin.TabularInline):
    from timeclock.models import MonthlyTarget
    model = MonthlyTarget
    extra = 1
    fields = ('year', 'month', 'target_income')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'name', 'hourly_wage', 'is_staff', 'is_active', 'created_at', 'last_login')
    list_filter = ('is_staff', 'is_active', 'created_at')
    search_fields = ('email', 'name')
    ordering = ('-created_at',)
    inlines = [MonthlyTargetInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('個人情報'), {'fields': ('name', 'hourly_wage', 'hire_date', 'weekly_work_days', 'current_paid_leave')}),
        (_('権限'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('重要な日付'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'last_login')