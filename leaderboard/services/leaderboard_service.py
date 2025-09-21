from datetime import timedelta, date
import calendar
from typing import Optional, Dict, Any
from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo

from ..models import LeaderboardEntry
from timeclock.services import WorkTimeService


class LeaderboardService:
    """リーダーボード関連のビジネスロジックを管理するサービス"""
    
    def __init__(self, user=None):
        self.user = user
        self.jst = ZoneInfo(settings.TIME_ZONE)
    
    def update_user_stats(self, user=None, year: int = None, month: int = None) -> tuple[Optional[LeaderboardEntry], Optional[Dict[str, Any]]]:
        """
        ユーザーの統計情報を更新する
        
        Args:
            user: ユーザーオブジェクト（Noneの場合はインスタンスのuserを使用）
            year: 年（Noneの場合は現在の年）
            month: 月（Noneの場合は現在の月）
        
        Returns:
            (entry, error_response): 成功時は(entry, None)、失敗時は(None, error_dict)
        """
        user = user or self.user
        if not user:
            return None, {
                'success': False,
                'status': 'error',
                'error': 'ユーザーが指定されていません'
            }
        
        now = timezone.now().astimezone(self.jst)
        today = now.date()
        year = year or now.year
        month = month or now.month
        
        # エントリの取得
        try:
            entry = LeaderboardEntry.objects.get(
                user=user,
                year=year,
                month=month
            )
        except LeaderboardEntry.DoesNotExist:
            return None, {
                'success': False,
                'status': 'not_joined',
                'error': 'ランキングに参加していません。',
                'year': year,
                'month': month,
            }
        except Exception as e:
            return None, {
                'success': False,
                'status': 'error',
                'error': str(e)
            }
        
        # WorkTimeServiceを使用して労働時間データを取得
        service = WorkTimeService(user)
        
        # last_updatedの翌日から更新開始
        update_date = entry.last_updated.astimezone(self.jst).date() + timedelta(days=1)
        cached_data = entry.cached_daily_minutes or {}
        
        # 月末日を計算
        last_day_of_month = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day_of_month)
        
        # 今日か月末のどちらか早い方まで更新
        end_date = min(today, month_end)
        
        # 指定期間の日付を更新
        while update_date <= end_date:
            # 月が異なる場合はスキップ（念のため）
            if update_date.year != year or update_date.month != month:
                update_date += timedelta(days=1)
                continue
                
            daily_summary = service.get_daily_summary(update_date)
            if daily_summary['work_hours'] > 0:
                # 日付をキーとして分数を保存
                minutes = int(daily_summary['work_time'].total_seconds() / 60)
                cached_data[str(update_date.day)] = minutes
            
            update_date += timedelta(days=1)
        
        # 合計時間を計算
        total_minutes = sum(cached_data.values())
        
        # エントリを更新
        entry.cached_daily_minutes = cached_data
        entry.total_minutes = total_minutes
        entry.save()
        
        return entry, {
                'success': True,
                'status': 'updated_users_stats',
                'message': '更新されました。'
            }
    
    def update_leaderboard(self, year: int, month: int) -> Dict[str,Any]:
        """
        指定された年月のランキングを更新する
        
        Args:
            year: 年
            month: 月
        """
        try:
            # 指定年月の全エントリを労働時間の降順で取得
            all_entries = LeaderboardEntry.objects.filter(
                year=year,
                month=month
            ).order_by('-total_minutes')
            
            # ランキングを更新
            for index, entry in enumerate(all_entries, start=1):
                entry.rank = index
                entry.save(update_fields=['rank'])

            return {
                'success':True,
                'status':'updated_leaderboard',
                'message': 'ランキングを更新しました。'
            }
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'error': str(e)
            }
    
    def get_user_rank_info(self, user=None, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        ユーザーのランキング情報を取得する
        
        Args:
            user: ユーザーオブジェクト
            year: 年
            month: 月
        
        Returns:
            ランキング情報の辞書
        """
        user = user or self.user
        now = timezone.now().astimezone(self.jst)
        year = year or now.year
        month = month or now.month
        
        try:
            entry = LeaderboardEntry.objects.get(
                user=user,
                year=year,
                month=month
            )
            
            # 参加者総数を取得
            total_participants = LeaderboardEntry.objects.filter(
                year=year,
                month=month
            ).count()
            
            return {
                'joined': True,
                'rank': entry.rank,
                'total_minutes': entry.total_minutes,
                'total_hours_display': entry.total_hours_display,
                'total_participants': total_participants,
                'last_updated': entry.last_updated.isoformat()
            }
        except LeaderboardEntry.DoesNotExist:
            return {
                'joined': False,
                'rank': None,
                'total_minutes': 0,
                'total_participants': 0
            }