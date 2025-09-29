"""
Cron処理をAPIエンドポイントに変換したビュー群
Google Apps Scriptからの定期的なリクエストで実行される
"""

import logging
from datetime import date, datetime
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from zoneinfo import ZoneInfo
import hashlib
import hmac

from timeclock.services.paid_leave_auto_processor import PaidLeaveAutoProcessor
from bulletin_board.models import Message
from leaderboard.models import LeaderboardEntry
from leaderboard.services.leaderboard_service import LeaderboardService

logger = logging.getLogger(__name__)

# 定期処理用のAPIキー（settings.pyで設定される）
CRON_API_SECRET = getattr(settings, 'CRON_API_SECRET', None)


def verify_cron_request(request):
    """
    Google Apps Scriptからのリクエストの認証
    
    リクエストヘッダーにX-Cron-Signatureを含める必要がある
    署名は以下の方法で生成:
    - payload = リクエストボディ + タイムスタンプ(10分以内)
    - signature = HMAC-SHA256(payload, CRON_API_SECRET)
    """
    if not CRON_API_SECRET:
        logger.error("CRON_API_SECRET が設定されていません")
        return False
    
    signature = request.headers.get('X-Cron-Signature')
    timestamp = request.headers.get('X-Cron-Timestamp')
    
    if not signature or not timestamp:
        logger.warning("認証ヘッダーが不足しています")
        return False
    
    try:
        # タイムスタンプチェック（10分以内）
        request_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        current_time = timezone.now()
        time_diff = abs((current_time - request_time).total_seconds())
        
        if time_diff > 600:  # 10分
            logger.warning(f"リクエストが古すぎます: {time_diff}秒前")
            return False
        
        # 署名検証
        payload = request.body.decode('utf-8') + timestamp
        expected_signature = hmac.new(
            CRON_API_SECRET.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("署名が一致しません")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"認証処理でエラーが発生: {e}")
        return False


@csrf_exempt
@require_POST
def process_daily_paid_leave_grants(request):
    """
    日次有給付与処理API
    
    Google Apps Scriptから毎日午前0時（JST）に呼び出される
    """
    if not verify_cron_request(request):
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        # JST基準で今日の日付を取得
        jst = ZoneInfo(settings.TIME_ZONE)
        target_date = timezone.now().astimezone(jst).date()
        
        logger.info(f'API経由で日次有給付与処理を開始: 対象日={target_date}')
        
        # 自動処理プロセッサーを初期化
        auto_processor = PaidLeaveAutoProcessor()
        
        # 有給付与・時効処理を実行
        judgments = auto_processor.process_daily_grants_and_expirations(target_date)
        
        # 処理結果を集計
        if judgments:
            granted_count = sum(1 for j in judgments if j.is_eligible and j.grant_days > 0)
            rejected_count = len(judgments) - granted_count
            
            # 付与された詳細情報をログに記録
            for judgment in judgments:
                if judgment.is_eligible and judgment.grant_days > 0:
                    logger.info(
                        f'有給付与: {judgment.user.name} - {judgment.grant_days}日付与 '
                        f'(出勤率: {judgment.attendance_rate:.1%})'
                    )
            
            logger.info(f'有給付与処理完了: 対象{len(judgments)}件, 付与{granted_count}件')
            
            result = {
                'success': True,
                'target_date': target_date.isoformat(),
                'total_judgments': len(judgments),
                'granted_count': granted_count,
                'rejected_count': rejected_count,
                'message': f'日次有給付与処理が完了しました'
            }
        else:
            logger.info('有給付与処理完了: 対象者なし')
            result = {
                'success': True,
                'target_date': target_date.isoformat(),
                'total_judgments': 0,
                'granted_count': 0,
                'rejected_count': 0,
                'message': '付与対象ユーザーはいませんでした'
            }
        
        # 時効処理の結果を追加
        from timeclock.models import PaidLeaveRecord
        
        expired_records = PaidLeaveRecord.objects.filter(
            record_type='expire',
            used_date=target_date
        )
        
        if expired_records:
            total_expired_days = sum(record.days for record in expired_records)
            affected_users = expired_records.values_list('user__name', flat=True).distinct().count()
            
            result['expiration_info'] = {
                'affected_users': affected_users,
                'expired_days': total_expired_days
            }
            
            logger.info(f'時効処理完了: 対象{affected_users}名, 消滅{total_expired_days}日')
        else:
            result['expiration_info'] = {
                'affected_users': 0,
                'expired_days': 0
            }
            logger.info('時効処理完了: 対象なし')
        
        return JsonResponse(result)
        
    except Exception as e:
        error_msg = f'日次有給付与処理でエラーが発生: {e}'
        logger.error(error_msg, exc_info=True)
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)


@csrf_exempt
@require_POST
def cleanup_expired_pins(request):
    """
    期限切れピン留めメッセージ削除API
    
    Google Apps Scriptから5分ごとに呼び出される
    """
    if not verify_cron_request(request):
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        jst = ZoneInfo(settings.TIME_ZONE)
        now = timezone.now().astimezone(jst)
        
        logger.info('API経由で期限切れピン留め削除処理を開始')
        
        # 期限切れのピン留めメッセージを取得
        expired_messages = Message.objects.filter(
            is_pinned=True,
            pin_expires_at__lte=now
        ).select_related('user')
        
        count = expired_messages.count()
        
        if count == 0:
            logger.info('期限切れピン留め削除処理: 対象なし')
            return JsonResponse({
                'success': True,
                'processed_count': 0,
                'message': '期限切れのピン留めメッセージはありません'
            })
        
        # ピン留めを解除
        processed_count = 0
        for message in expired_messages:
            logger.info(
                f'ピン留め解除: ID={message.id}, 投稿者={message.user.name}, '
                f'期限={message.pin_expires_at.strftime("%Y-%m-%d %H:%M")}'
            )
            message.unpin_message()
            processed_count += 1
        
        logger.info(f'期限切れピン留め削除処理完了: {processed_count}件処理')
        
        return JsonResponse({
            'success': True,
            'processed_count': processed_count,
            'message': f'{processed_count}件の期限切れピン留めを解除しました'
        })
        
    except Exception as e:
        error_msg = f'期限切れピン留め削除処理でエラーが発生: {e}'
        logger.error(error_msg, exc_info=True)
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)


@csrf_exempt
@require_POST
def cron_health_check(request):
    """
    Cron処理の死活監視API
    
    Google Apps Scriptから定期的に呼び出され、システムが正常に動作していることを確認
    """
    if not verify_cron_request(request):
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        jst = ZoneInfo(settings.TIME_ZONE)
        current_time = timezone.now().astimezone(jst)
        
        # データベース接続テスト
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_count = User.objects.count()
        
        return JsonResponse({
            'success': True,
            'timestamp': current_time.isoformat(),
            'database_status': 'connected',
            'user_count': user_count,
            'message': 'システムは正常に動作しています'
        })
        
    except Exception as e:
        error_msg = f'ヘルスチェックでエラーが発生: {e}'
        logger.error(error_msg, exc_info=True)
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)


@csrf_exempt
@require_POST
def recalculate_leaderboards(request):
    """
    ランキングデータ完全再計算API
    
    Google Apps Scriptから日次で呼び出される
    """
    if not verify_cron_request(request):
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        jst = ZoneInfo(settings.TIME_ZONE)
        now = timezone.now().astimezone(jst)
        target_year = now.year
        target_month = now.month
        
        logger.info(f'API経由でランキングデータ完全再計算を開始: {target_year}年{target_month}月')
        
        # 対象年月のエントリを取得
        entries = LeaderboardEntry.objects.filter(
            year=target_year,
            month=target_month
        ).select_related('user')
        
        if not entries:
            result = {
                'success': True,
                'message': f'{target_year}年{target_month}月の参加者はいません',
                'target_year': target_year,
                'target_month': target_month,
                'processed_count': 0,
                'success_count': 0,
                'error_count': 0
            }
            logger.info(f'ランキング再計算完了: 対象なし ({target_year}年{target_month}月)')
            return JsonResponse(result)
        
        success_count = 0
        error_count = 0
        
        # 各エントリを完全再計算
        for entry in entries:
            try:
                service = LeaderboardService(entry.user)
                result_entry, response = service.recalculate_user_stats_from_scratch(
                    year=target_year,
                    month=target_month
                )
                
                if response and response.get('success'):
                    success_count += 1
                    logger.debug(f'ユーザー {entry.user.name} の再計算成功')
                else:
                    error_count += 1
                    error_msg = response.get('error', '不明なエラー') if response else '不明なエラー'
                    logger.error(f'ユーザー {entry.user.name} の再計算失敗: {error_msg}')
                    
            except Exception as e:
                error_count += 1
                logger.error(f'ユーザー {entry.user.name} の再計算エラー: {e}', exc_info=True)
        
        # ランキングを更新
        ranking_updated = False
        if success_count > 0:
            service = LeaderboardService()
            ranking_result = service.update_leaderboard(target_year, target_month)
            
            if ranking_result.get('success'):
                ranking_updated = True
                logger.info(f'ランキング更新完了: {target_year}年{target_month}月')
            else:
                logger.error(f'ランキング更新エラー: {ranking_result}')
        
        # 結果を返却
        result = {
            'success': True,
            'message': f'{target_year}年{target_month}月のランキングデータ完全再計算完了',
            'target_year': target_year,
            'target_month': target_month,
            'processed_count': len(entries),
            'success_count': success_count,
            'error_count': error_count,
            'ranking_updated': ranking_updated
        }
        
        if error_count == 0:
            logger.info(f'ランキングデータ完全再計算完了: {target_year}年{target_month}月, 成功{success_count}件')
        else:
            logger.warning(
                f'ランキングデータ完全再計算完了（エラーあり）: {target_year}年{target_month}月, '
                f'成功{success_count}件, エラー{error_count}件'
            )
        
        return JsonResponse(result)
        
    except Exception as e:
        error_msg = f'ランキングデータ完全再計算でエラーが発生: {e}'
        logger.error(error_msg, exc_info=True)
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)