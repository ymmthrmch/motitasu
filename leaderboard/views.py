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
        # 参加時に初回の完全計算を実行
        updated_entry, response = service.recalculate_user_stats_from_scratch(year=year, month=month)
        if not response or not response.get('success'):
            # 参加は成功したが計算でエラーが発生した場合
            return JsonResponse(format_leaderboard_error(
                'calculation_error',
                f'参加は完了しましたが、労働時間の計算でエラーが発生しました: {response.get("error", "不明なエラー")}'
            ))
        
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
    entries = LeaderboardEntry.objects.filter(year=year, month=month)
    for leaderboard_entry in entries:
        current_user = leaderboard_entry.user
        service = LeaderboardService(current_user)
        updated_entry, response = service.update_user_stats(year=year, month=month)
        # エラーチェック（成功時もresponseが返るため、successフラグで判定）
        if not response or not response.get('success'):
            return JsonResponse(response or {'success': False, 'error': '不明なエラー'})
        print(f'{current_user.name}の労働時間計算成功')
    
    # ランキングを更新
    service = LeaderboardService()
    ranking_result = service.update_leaderboard(year, month)
    if not ranking_result.get('success'):
        return JsonResponse(ranking_result)
    
    # リクエストユーザーのエントリ情報を取得（参加していない場合の処理も含む）
    try:
        user_entry = LeaderboardEntry.objects.get(user=user, year=year, month=month)
        user_entry.refresh_from_db()
        total_minutes = user_entry.total_minutes
        rank = user_entry.rank
        
        return JsonResponse(format_leaderboard_success(
            'updated',
            '更新されました',
            total_minutes=total_minutes,
            rank=rank
        ))
    except LeaderboardEntry.DoesNotExist:
        # 管理者が参加していない場合でもランキング更新は成功
        return JsonResponse(format_leaderboard_success(
            'updated',
            'ランキングを更新しました（管理者権限）'
        ))

@login_required
@require_POST
def recalculate_from_scratch(request):
    """管理者用：キャッシュを使わずに完全再計算"""
    user = request.user
    
    # 管理者権限チェック
    if not (user.is_staff or user.is_superuser):
        return JsonResponse({
            'success': False,
            'error': '管理者権限が必要です'
        })
    
    now = get_jst_now()
    year = int(now.year)
    month = int(now.month)
    
    try:
        # 該当月の全エントリを取得
        entries = LeaderboardEntry.objects.filter(year=year, month=month)
        success_count = 0
        error_count = 0
        
        for entry in entries:
            service = LeaderboardService(entry.user)
            result_entry, response = service.recalculate_user_stats_from_scratch(
                year=year, 
                month=month
            )
            
            if response and response.get('success'):
                success_count += 1
            else:
                error_count += 1
        
        # ランキングを更新
        service = LeaderboardService()
        ranking_result = service.update_leaderboard(year, month)
        
        if error_count == 0:
            return JsonResponse({
                'success': True,
                'message': f'{success_count}件のエントリを完全再計算しました。ランキングも更新されました。'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'完了: {success_count}件成功、{error_count}件失敗'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'エラーが発生しました: {str(e)}'
        })