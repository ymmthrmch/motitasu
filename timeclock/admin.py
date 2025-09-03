from django.contrib import admin
from .models import TimeRecord

@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'clock_type', 'timestamp', 'created_at']
    list_filter = ['clock_type', 'timestamp', 'user']
    search_fields = ['user__username', 'user__email']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
