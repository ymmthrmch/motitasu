from django.contrib import admin
from .models import TimeRecord, MonthlyTarget, PaidLeaveRecord

@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'clock_type', 'timestamp', 'created_at']
    list_filter = ['clock_type', 'timestamp', 'user']
    search_fields = ['user__name', 'user__email']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

@admin.register(MonthlyTarget)
class MonthlyTargetAdmin(admin.ModelAdmin):
    list_display = ['user', 'year', 'month', 'target_income', 'created_at']
    list_filter = ['year', 'month', 'user']
    search_fields = ['user__name', 'user__email']
    ordering = ['-year', '-month', 'user']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # 編集時
            return ['user', 'year', 'month']
        return []

@admin.register(PaidLeaveRecord)
class PaidLeaveRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'record_type', 'days', 'grant_date', 'expiry_date', 'used_date', 'created_at']
    list_filter = ['record_type', 'grant_date', 'expiry_date', 'user']
    search_fields = ['user__name', 'user__email', 'description']
    date_hierarchy = 'grant_date'
    ordering = ['-created_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('user', 'record_type', 'days')
        }),
        ('日付情報', {
            'fields': ('grant_date', 'expiry_date', 'used_date')
        }),
        ('詳細', {
            'fields': ('description',)
        }),
    )
