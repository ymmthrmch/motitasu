from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Cron処理API
    path('cron/paid-leave-grants/', views.process_daily_paid_leave_grants, name='cron_paid_leave_grants'),
    path('cron/cleanup-pins/', views.cleanup_expired_pins, name='cron_cleanup_pins'),
    path('cron/health-check/', views.cron_health_check, name='cron_health_check'),
]