from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from zoneinfo import ZoneInfo
from .models import LeaderboardEntry
from .services import LeaderboardService

@login_required
def leaderboard(request):
    jst = ZoneInfo(settings.TIME_ZONE)
    now = timezone.now().astimezone(jst)
    
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    entry = LeaderboardEntry.objects.filter(
        user=request.user,
        years=year,
        month=month
    ).first()

    context = {
            'latest': year == now.year and month == now.month,
            'year': year,
            'month': month,
            'joined': bool(entry),
        }

    if entry:
        context['entry']=entry

    return render(request, 'leaderboard/leaderboard.html', context)

@login_required
@require_POST
def join(request):
    jst = ZoneInfo(settings.TIME_ZONE)
    now = timezone.now().astimezone(jst)
    year=int(now.astimezone(jst).year)
    month=int(now.astimezone(jst).month)
    try:
        entry, created = LeaderboardEntry.objects.get_or_create(
            user=request.user,
            years=year,
            month=month
        )
    except Exception as e:
        return JsonResponse({
            'success': False,
            'status': 'error',
            'error': str(e)
            })
    
    if created:
        return JsonResponse({
            'success': True,
            'status': 'joined',
            'message': 'ランキングに参加しました。',
            'year': year,
            'month': month,
            })
    
    return JsonResponse({
        'success': False,
        'status': 'already_joined',
        'error': '既にランキングに参加しています。',
        'year': year,
        'month': month,
        })    

@login_required
def get_status(request):
    user=request.user
    jst = ZoneInfo(settings.TIME_ZONE)
    now = timezone.now().astimezone(jst)
    year=int(request.GET.get('year',now.year))
    month=int(request.GET.get('month',now.month))
    try:
        entry = LeaderboardEntry.objects.get(
            user=user,
            years=year,
            month=month
        )
    except LeaderboardEntry.DoesNotExist:
        return JsonResponse({
            'success': False,
            'status': 'not_joined',
            'error': 'ランキングに参加していません。',
            'year': year,
            'month': month,
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'status': 'error',
            'error': str(e)
            })

    return JsonResponse({
        'success': True,
        'status': 'got_status',
        'entry': {
            'user': entry.user.name,
            'year': entry.year,
            'month': entry.month,
            'total_minutes': entry.total_minutes,
            'total_hours_display': entry.total_hours_display,
            'rank': entry.rank,
            'joined_at': entry.joined_at.astimezone(jst).isoformat(),
            'last_updated': entry.last_updated.astimezone(jst).isoformat(),
        }
        })

@login_required
@require_POST
def update(request):
    user = request.user
    jst = ZoneInfo(settings.TIME_ZONE)
    now = timezone.now().astimezone(jst)
    year = int(now.year)
    month = int(now.month)
    
    # LeaderboardServiceを使用して統計情報を更新
    service = LeaderboardService(user)
    entry, response = service.update_user_stats(year=year, month=month)
    
    # エラーチェック（成功時もresponseが返るため、successフラグで判定）
    if not response or not response.get('success'):
        return JsonResponse(response or {'success': False, 'error': '不明なエラー'})
    
    # ランキングを更新
    ranking_result = service.update_leaderboard(year, month)
    if not ranking_result.get('success'):
        return JsonResponse(ranking_result)
    
    # 更新後のエントリ情報を取得
    entry.refresh_from_db()
    total_minutes = entry.total_minutes
    rank = entry.rank

    return JsonResponse({
        'success': True,
        'status': 'updated',
        'message': '更新されました。',
        'total_minutes': total_minutes,
        'rank': rank
        })