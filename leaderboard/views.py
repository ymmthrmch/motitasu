from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import LeaderboardEntry
from .services import LeaderboardService
from .utils import (
    get_year_month_from_request,
    check_join_period,
    get_prev_next_month,
    get_jst_now,
    format_leaderboard_error,
    format_leaderboard_success
)

@login_required
def leaderboard(request):
    now = get_jst_now()
    
    # 年月パラメーターを取得
    year, month, error_response = get_year_month_from_request(request, now, 'GET')
    if error_response:
        return error_response
    
    # 参加期間かどうかを判定（毎月1日〜10日）
    is_current_month, is_join_period = check_join_period(year, month, now)
    
    # ユーザーのエントリを取得
    entry = LeaderboardEntry.objects.filter(
        user=request.user,
        year=year,
        month=month
    ).first()
    
    # 同じ年月の全エントリを取得してランキング表示
    all_entries = LeaderboardEntry.objects.filter(
        year=year,
        month=month
    ).order_by('rank', '-total_minutes')
    
    context = {
        'year': year,
        'month': month,
        'joined': bool(entry),
        'is_current_month': is_current_month,
        'is_join_period': is_join_period,
        'entry': entry,
        'all_entries': all_entries,
        'current_day': now.day,
    }
    
    # 前月・次月のリンク用データ
    prev_month, next_month = get_prev_next_month(year, month)
    context['prev_month'] = prev_month
    context['next_month'] = next_month

    return render(request, 'leaderboard/leaderboard.html', context)

@login_required
@require_POST
def join(request):
    user = request.user
    now = get_jst_now()
    
    # 年月パラメーターを取得
    year, month, error_response = get_year_month_from_request(request, now, 'POST')
    if error_response:
        return error_response
    
    # 参加期間チェック
    is_current_month, is_join_period = check_join_period(year, month, now)
    if not is_join_period:
        return JsonResponse(format_leaderboard_error(
            'not_join_period',
            '参加期間ではありません（毎月1日〜10日）'
        ))

    try:
        entry, created = LeaderboardEntry.objects.get_or_create(
            user=user,
            year=year,
            month=month
        )
    except Exception as e:
        return JsonResponse(format_leaderboard_error(
            'error',
            str(e)
        ))
    
    if created:
        service = LeaderboardService(user)
        service.update_user_stats(year=year, month=month)
        service.update_leaderboard(year=year, month=month)
        
        return JsonResponse(format_leaderboard_success(
            'joined',
            'ランキングに参加しました',
            year=year,
            month=month
        ))
    
    return JsonResponse(format_leaderboard_error(
        'already_joined',
        '既にランキングに参加済みです',
        year=year,
        month=month
    ))    

@login_required
def get_status(request):
    user = request.user
    now = get_jst_now()
    
    # 年月パラメーターを取得
    year, month, error_response = get_year_month_from_request(request, now, 'GET')
    if error_response:
        return error_response
    try:
        entry = LeaderboardEntry.objects.get(
            user=user,
            year=year,
            month=month
        )
    except LeaderboardEntry.DoesNotExist:
        return JsonResponse(format_leaderboard_error(
            'not_joined',
            'ランキングに参加していません',
            year=year,
            month=month
        ))
    except Exception as e:
        return JsonResponse(format_leaderboard_error(
            'error',
            str(e)
        ))

    return JsonResponse(format_leaderboard_success(
        'got_status',
        entry={
            'user': entry.user.name,
            'year': entry.year,
            'month': entry.month,
            'total_minutes': entry.total_minutes,
            'total_hours_display': entry.total_hours_display,
            'rank': entry.rank,
            'joined_at': entry.joined_at.astimezone(now.tzinfo).isoformat(),
            'last_updated': entry.last_updated.astimezone(now.tzinfo).isoformat(),
        }
    ))

@login_required
@require_POST
def update(request):
    user = request.user
    now = get_jst_now()
    year = int(now.year)
    month = int(now.month)
    
    # LeaderboardServiceを使用して統計情報を更新
    entries = LeaderboardEntry.objects.filter(year=year,month=month)
    for entry in entries:
        current_user = entry.user
        service = LeaderboardService(current_user)
        entry, response = service.update_user_stats(year=year, month=month)
        # エラーチェック（成功時もresponseが返るため、successフラグで判定）
        if not response or not response.get('success'):
            return JsonResponse(response or {'success': False, 'error': '不明なエラー'})
        print(f'{current_user.name}の労働時間計算成功')
    
    # ランキングを更新
    service = LeaderboardService(user)
    ranking_result = service.update_leaderboard(year, month)
    if not ranking_result.get('success'):
        return JsonResponse(ranking_result)
    
    # 更新後のエントリ情報を取得
    entry.refresh_from_db()
    total_minutes = entry.total_minutes
    rank = entry.rank

    return JsonResponse(format_leaderboard_success(
        'updated',
        '更新されました',
        total_minutes=total_minutes,
        rank=rank
    ))