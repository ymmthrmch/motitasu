from django.urls import path
from . import views

app_name = 'timeclock'

urlpatterns = [
    path('', views.timeclock, name='timeclock'),
    path('clock/', views.clock_action, name='clock_action'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/current-time/', views.get_current_time, name='get_current_time'),
]