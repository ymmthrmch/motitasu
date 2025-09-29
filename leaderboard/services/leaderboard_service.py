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
        
        # キャッシュデータから最新の日付を取得して更新開始日を決定
        cached_data = entry.cached_daily_minutes or {}
        if cached_data:
            # キャッシュデータの最新日の翌日から更新
            latest_cached_day = max(int(day) for day in cached_data.keys())
            update_date = date(year, month, latest_cached_day) + timedelta(days=1)
        else:
            # キャッシュデータがない場合は月初から
            update_date = date(year, month, 1)
        
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
            
            # 同順位処理を実装したランキング更新
            current_rank = 1
            previous_minutes = None
            
            for index, entry in enumerate(all_entries):
                # 前の人と同じ労働時間の場合は同じ順位
                if previous_minutes is not None and entry.total_minutes == previous_minutes:
                    # 同じ順位を保持
                    pass
                else:
                    # 新しい順位を設定（現在のインデックス + 1）
                    current_rank = index + 1
                
                entry.rank = current_rank
                entry.save(update_fields=['rank'])
                previous_minutes = entry.total_minutes

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
    
    def recalculate_user_stats_from_scratch(self, user=None, year: int = None, month: int = None) -> tuple[Optional[LeaderboardEntry], Optional[Dict[str, Any]]]:
        """
        キャッシュを使わずに月初から労働時間を完全再計算してキャッシュを保存
        
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
        
        # 月初から完全再計算
        month_start = date(year, month, 1)
        
        # 月末日を計算
        last_day_of_month = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day_of_month)
        
        # 今日か月末のどちらか早い方まで計算
        end_date = min(today, month_end)
        
        # キャッシュデータを初期化
        cached_data = {}
        
        # 月初から指定期間の日付を計算
        current_date = month_start
        while current_date <= end_date:
            daily_summary = service.get_daily_summary(current_date)
            if daily_summary['work_hours'] > 0:
                # 日付をキーとして分数を保存
                minutes = int(daily_summary['work_time'].total_seconds() / 60)
                cached_data[str(current_date.day)] = minutes
            
            current_date += timedelta(days=1)
        
        # 合計時間を計算
        total_minutes = sum(cached_data.values())
        
        # エントリを更新（last_updatedも現在時刻で更新）
        entry.cached_daily_minutes = cached_data
        entry.total_minutes = total_minutes
        entry.last_updated = now
        entry.save()
        
        return entry, {
            'success': True,
            'status': 'recalculated_from_scratch',
            'message': f'{user.name}の労働時間を完全再計算しました。'
        }