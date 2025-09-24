from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from functools import wraps


class AdminRequiredMixin(UserPassesTestMixin):
    """管理者権限が必要なビューに使用するMixin"""
    
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        )
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("この機能を利用するには管理者権限が必要です。")
        return super().handle_no_permission()


def admin_required(view_func):
    """管理者権限が必要な関数ベースビュー用デコレータ"""
    
    def check_admin(user):
        return user.is_authenticated and (user.is_staff or user.is_superuser)
    
    return user_passes_test(check_admin)(view_func)


def admin_required_api(view_func):
    """管理者権限が必要なAPI用デコレータ（JSON レスポンス）"""
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'ログインが必要です。'
            }, status=401)
        
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({
                'success': False,
                'message': 'この操作には管理者権限が必要です。'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def log_admin_action(action, description, target_user=None):
    """管理者操作をログに記録するヘルパー関数"""
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # ビューを実行
            response = view_func(request, *args, **kwargs)
            
            # 成功した場合のみログを記録
            if hasattr(response, 'status_code') and response.status_code < 400:
                from .models import AdminActionLog
                
                # target_userの解決
                resolved_target_user = None
                if target_user:
                    if callable(target_user):
                        resolved_target_user = target_user(request, *args, **kwargs)
                    else:
                        resolved_target_user = target_user
                
                # ログを記録
                AdminActionLog.objects.create(
                    admin_user=request.user,
                    action=action,
                    target_user=resolved_target_user,
                    description=description if callable(description) 
                               else description.format(**kwargs)
                )
            
            return response
        
        return wrapper
    return decorator