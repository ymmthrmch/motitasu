from django.urls import path
from . import views

app_name = 'leaderboard'

urlpatterns = [
    path('', views.leaderboard, name='leaderboard'),
    path('api/join/', views.join, name='join'),
    path('api/status/',views.get_status, name='status'),
    path('api/update/',views.update, name='update'),
    path('api/recalculate-from-scratch/', views.recalculate_from_scratch, name='recalculate_from_scratch'),
]