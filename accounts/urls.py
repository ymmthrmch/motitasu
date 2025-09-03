from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import CustomLoginView, SignupView

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='accounts:login'), name='logout'),
    path('signup/', SignupView.as_view(), name='signup'),
]