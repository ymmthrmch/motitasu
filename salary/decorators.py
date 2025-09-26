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
    """管理者権限が必要なAPI用デコレータ（JSON レスポンス）
    関数ベースビューとクラスベースビューの両方に対応
    """
    
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        # 関数ベースビューかクラスベースビューかを判定
        if len(args) > 0 and hasattr(args[0], 'META'):
            # 関数ベースビュー: 第1引数がrequest
            request = args[0]
        elif len(args) > 1 and hasattr(args[1], 'META'):
            # クラスベースビュー: 第1引数がself、第2引数がrequest
            request = args[1]
        else:
            return JsonResponse({
                'success': False,
                'message': 'リクエストオブジェクトが見つかりません。'
            }, status=500)
        
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
        
        return view_func(*args, **kwargs)
    
    return wrapper


def log_admin_action(action):
    """クラスベースビュー用の管理者操作ログデコレータ"""
    
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # 元のメソッドを実行
            response = method(self, *args, **kwargs)
            
            # 成功した場合のみログを記録
            if hasattr(response, 'status_code') and response.status_code < 400:
                from .models import AdminActionLog
                
                # オブジェクト名を取得（CreateView, UpdateViewの場合）
                obj_name = getattr(self, 'object', None)
                if obj_name and hasattr(obj_name, 'name'):
                    obj_name = obj_name.name
                else:
                    obj_name = "オブジェクト"
                
                # アクション別の説明文を生成
                action_descriptions = {
                    'skill_create': f'スキル「{obj_name}」を作成しました',
                    'skill_edit': f'スキル「{obj_name}」を更新しました',
                    'grade_create': f'グレード「{obj_name}」を作成しました',
                    'grade_edit': f'グレード「{obj_name}」を更新しました',
                }
                
                description = action_descriptions.get(action, f"操作: {action}")
                
                # ログを記録
                AdminActionLog.objects.create(
                    admin_user=self.request.user,
                    action=action,
                    description=description
                )
            
            return response
        
        return wrapper
    return decorator