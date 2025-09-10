from django.urls import path
from . import views

app_name = 'bulletin_board'

urlpatterns = [
    path('', views.message_list, name='message_list'),  # メッセージ一覧・投稿
    path('message/<int:message_id>/', views.message_detail, name='message_detail'),  # メッセージ詳細
    path('api/reaction/', views.toggle_reaction, name='toggle_reaction'),  # リアクション切り替えAPI
    path('api/reaction-users/<int:message_id>/<str:reaction_type>/', views.get_reaction_users, name='get_reaction_users'),  # リアクションユーザー一覧API
    path('api/pin/', views.toggle_pin, name='toggle_pin'),  # ピン留め切り替えAPI
    path('api/pin-status/<int:message_id>/', views.get_pin_status, name='get_pin_status'),  # ピン留め状態取得API
]