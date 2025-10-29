"""リーダーボード用ユーティリティ関数"""

from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo


def get_year_month_from_request(request, now, method='GET'):
    """
    リクエストから年月を取得し、バリデーションする
    
    Args:
        request: HTTPリクエスト
        now: 現在時刻（timezone aware datetime）
        method: パラメーター取得方法 ('GET' or 'POST')
    
    Returns:
        tuple: (year, month, error_response)
               成功時: (int, int, None)
               エラー時: (None, None, JsonResponse)
    """
    try:
        if method == 'GET':
            year = int(request.GET.get('year', now.year))
            month = int(request.GET.get('month', now.month))
        else:  # POST
            year = int(request.POST.get('year', now.year))
            month = int(request.POST.get('month', now.month))
            
        # 月の範囲チェック
        if not (1 <= month <= 12):
            raise ValueError("月は1-12の範囲で指定してください")
            
        return year, month, None
        
    except (ValueError, TypeError) as e:
        return None, None, JsonResponse({
            'success': False,
            'status': 'invalid_params',
            'error': f'パラメーターエラー: {str(e)}'
        })


def check_join_period(year, month, now):
    """
    参加期間（毎月1日〜10日）かどうかを判定
    
    Args:
        year: 対象年
        month: 対象月
        now: 現在時刻（timezone aware datetime）
    
    Returns:
        tuple: (is_current_month, is_join_period)
               is_current_month: 現在の年月かどうか
               is_join_period: 参加期間内かどうか
    """
    is_current_month = year == now.year and month == now.month
    is_join_period = is_current_month and 1 <= now.day <= 31
    return is_current_month, is_join_period


def get_prev_next_month(year, month):
    """
    前月・次月の年月を計算
    
    Args:
        year: 基準年
        month: 基準月
    
    Returns:
        tuple: (prev_month_dict, next_month_dict)
               各辞書: {'year': int, 'month': int}
    """
    if month == 1:
        prev_month = {'year': year - 1, 'month': 12}
        next_month = {'year': year, 'month': 2}
    elif month == 12:
        prev_month = {'year': year, 'month': 11}
        next_month = {'year': year + 1, 'month': 1}
    else:
        prev_month = {'year': year, 'month': month - 1}
        next_month = {'year': year, 'month': month + 1}
    
    return prev_month, next_month


def get_jst_now():
    """
    日本標準時の現在時刻を取得
    
    Returns:
        datetime: JST（Asia/Tokyo）の現在時刻
    """
    jst = ZoneInfo(settings.TIME_ZONE)
    return timezone.now().astimezone(jst)


def format_leaderboard_error(status, error_message, **extra_data):
    """
    リーダーボード用の統一されたエラーレスポンスを作成
    
    Args:
        status: エラーステータス
        error_message: エラーメッセージ
        **extra_data: 追加データ
    
    Returns:
        dict: JsonResponseに渡すデータ
    """
    response_data = {
        'success': False,
        'status': status,
        'error': error_message
    }
    response_data.update(extra_data)
    return response_data


def format_leaderboard_success(status, message=None, **extra_data):
    """
    リーダーボード用の統一された成功レスポンスを作成
    
    Args:
        status: 成功ステータス
        message: 成功メッセージ（オプション）
        **extra_data: 追加データ
    
    Returns:
        dict: JsonResponseに渡すデータ
    """
    response_data = {
        'success': True,
        'status': status
    }
    if message:
        response_data['message'] = message
    response_data.update(extra_data)
    return response_data