from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from .models import Message, Reaction
from zoneinfo import ZoneInfo

@login_required
def message_list(request):
    """メッセージ一覧表示・投稿処理"""
    
    if request.method == 'POST':
        # メッセージ投稿処理
        content = request.POST.get('content', '').strip()
        show_name = request.POST.get('show_name') == 'on'  # チェックボックスの値
        
        if content:
            Message.objects.create(
                user=request.user, 
                content=content,
                show_name=show_name
            )
            messages.success(request, 'メッセージを投稿しました。')
        else:
            messages.error(request, 'メッセージ内容を入力してください。')
        return redirect('bulletin_board:message_list')
    
    # メッセージ一覧取得（ページング対応）
    message_list = Message.objects.select_related('user').prefetch_related('reactions')
    paginator = Paginator(message_list, 20)  # 20件ずつ表示
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 各メッセージのリアクション情報を整理
    for message in page_obj:
        message.reaction_summary = get_reaction_summary(message)
        if request.user.is_authenticated:
            message.user_reactions = get_user_reactions(message, request.user)
    
    context = {
        'page_obj': page_obj,
        'reaction_choices': Reaction.REACTION_CHOICES,
    }
    
    return render(request, 'bulletin_board/message_list.html', context)

def message_detail(request, message_id):
    """メッセージ詳細（現在は未実装）"""
    # 将来的に実装する可能性があるため、URLは定義しておく
    return redirect('bulletin_board:message_list')

@login_required
@require_POST
def toggle_reaction(request):
    """リアクションの切り替え（Ajax API）"""
    
    try:
        message_id = request.POST.get('message_id')
        reaction_type = request.POST.get('reaction_type')
        
        message = Message.objects.get(id=message_id)
        
        # 既存リアクションを確認
        reaction, created = Reaction.objects.get_or_create(
            user=request.user,
            message=message,
            reaction_type=reaction_type
        )
        
        if not created:
            reaction.delete()
            action = 'removed'
        else:
            action = 'added'
        
        # 更新後のリアクション数を取得
        reaction_count = message.reactions.filter(reaction_type=reaction_type).count()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'reaction_count': reaction_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def get_reaction_users(request, message_id, reaction_type):
    """特定リアクションをしたユーザー一覧を取得"""
    
    try:
        message = Message.objects.get(id=message_id)
        reactions = message.reactions.filter(reaction_type=reaction_type).select_related('user')
        
        jst = ZoneInfo(settings.TIME_ZONE)
        user_list = [
            {
                'name': reaction.user.name,
                'created_at': reaction.created_at.astimezone(jst).strftime('%Y-%m-%d %H:%M')
            }
            for reaction in reactions
        ]
        
        return JsonResponse({
            'success': True,
            'users': user_list,
            'emoji': dict(Reaction.REACTION_CHOICES)[reaction_type]
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_POST
def toggle_pin(request):
    """ピン留めの切り替え（Ajax API）"""
    
    try:
        message_id = request.POST.get('message_id')
        action = request.POST.get('action')  # 'pin' or 'unpin'
        
        message = Message.objects.get(id=message_id, user=request.user)  # 自分の投稿のみ
        jst = ZoneInfo(settings.TIME_ZONE)
        
        if action == 'pin':
            duration = int(request.POST.get('duration', 24))  # デフォルト24時間
            if duration not in [12, 24, 168]:
                duration = 24
            
            message.pin_message(duration)
            return JsonResponse({
                'success': True,
                'action': 'pinned',
                'duration': duration,
                'expires_at': message.pin_expires_at.astimezone(jst).isoformat()
            })
            
        elif action == 'unpin':
            message.unpin_message()
            return JsonResponse({
                'success': True,
                'action': 'unpinned'
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            })
        
    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'メッセージが見つからないか、編集権限がありません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def get_pin_status(request, message_id):
    """ピン留め状態を取得"""
    
    try:
        message = Message.objects.get(id=message_id)
        jst = ZoneInfo(settings.TIME_ZONE)
        
        return JsonResponse({
            'success': True,
            'is_pinned': message.is_pinned,
            'pin_duration_hours': message.pin_duration_hours,
            'pinned_at': message.pinned_at.astimezone(jst).isoformat() if message.pinned_at else None,
            'pin_expires_at': message.pin_expires_at.astimezone(jst).isoformat() if message.pin_expires_at else None,
            'remaining_seconds': message.get_pin_remaining_time(),
            'is_expired': message.is_pin_expired()
        })
        
    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'メッセージが見つかりません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_POST
def delete_message(request):
    """メッセージの削除（Ajax API）"""
    
    try:
        message_id = request.POST.get('message_id')
        
        message = Message.objects.get(id=message_id, user=request.user)  # 自分の投稿のみ
        message.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'メッセージを削除しました。'
        })
        
    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'メッセージが見つからないか、削除権限がありません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ヘルパー関数
def get_reaction_summary(message):
    """メッセージのリアクション数を取得"""
    reaction_counts = message.get_reaction_counts()
    summary = {}
    for reaction in reaction_counts:
        summary[reaction['reaction_type']] = reaction['count']
    return summary

def get_user_reactions(message, user):
    """ユーザーがしたリアクションの一覧を取得"""
    user_reactions = message.reactions.filter(user=user)
    return [reaction.reaction_type for reaction in user_reactions]