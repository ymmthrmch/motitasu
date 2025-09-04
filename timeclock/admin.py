from django.contrib import admin
from .models import TimeRecord, MonthlyTarget

@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'clock_type', 'timestamp', 'created_at']
    list_filter = ['clock_type', 'timestamp', 'user']
    search_fields = ['user__username', 'user__email']
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
