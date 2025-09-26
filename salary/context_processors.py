from .models import SkillApplication


def admin_menu_context(request):
    """管理者メニュー用のコンテキスト情報を提供"""
    if not request.user.is_authenticated:
        return {}
    
    if not (request.user.is_staff or request.user.is_superuser):
        return {}
    
    # 承認待ち申告数を取得
    pending_count = SkillApplication.objects.filter(status='pending').count()
    
    return {
        'pending_applications_count': pending_count,
    }