"""
有給休暇残日数管理クラス
"""

from datetime import date, timedelta
from dataclasses import dataclass
from typing import List, Tuple
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from zoneinfo import ZoneInfo

from timeclock.models import PaidLeaveRecord
from .paid_leave_calculator import PaidLeaveCalculator


@dataclass
class DetailedBalanceInfo:
    """詳細残日数情報"""
    total_balance: int           # 合計残日数
    balance_by_grant_date: List['GrantDateBalance']  # 付与日別残日数
    upcoming_expirations: List['ExpirationInfo']    # 近い時効情報


@dataclass
class GrantDateBalance:
    """付与日別残日数"""
    grant_date: date            # 付与日
    original_days: int          # 元の付与日数
    used_days: int              # 使用済み日数
    remaining_days: int         # 残り日数
    expiry_date: date          # 有効期限
    days_until_expiry: int     # 時効まで日数


@dataclass
class ExpirationInfo:
    """時効情報"""
    grant_date: date           # 付与日
    expiry_date: date         # 時効日
    remaining_days: int       # 時効対象の残日数
    days_until_expiry: int    # 時効まで日数


class PaidLeaveBalanceManager:
    """有給残日数の管理と更新処理を担当"""
    
    def __init__(self, user):
        """
        Args:
            user: Userモデルのインスタンス
        """
        self.user = user
        self.calculator = PaidLeaveCalculator(user)
    
    def get_current_balance(self) -> int:
        """
        現在の有給残日数を計算
        
        Returns:
            int: 現在の有給残日数
            
        Rules:
            - データベースから最新の有給残日数を計算
            - 付与記録・使用記録・時効記録・取消記録を考慮
        """
        # 付与日数の合計
        granted_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant'
        ).aggregate(total=Sum('days'))['total'] or 0
        
        # 使用日数の合計
        used_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='use'
        ).aggregate(total=Sum('days'))['total'] or 0
        
        # 時効日数の合計
        expired_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='expire'
        ).aggregate(total=Sum('days'))['total'] or 0
        
        # 取消日数の合計
        cancelled_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='cancel'
        ).aggregate(total=Sum('days'))['total'] or 0
        
        # 残日数計算
        balance = granted_days - used_days - expired_days - cancelled_days
        return max(0, balance)  # マイナスにはならない
    
    def get_detailed_balance_info(self) -> DetailedBalanceInfo:
        """
        詳細な残日数情報を取得
        
        Returns:
            DetailedBalanceInfo: 付与年度別の残日数詳細
            
        Rules:
            - 各付与年度の残日数を計算
            - 時効が近い順に並べる
            - 同一日の複数付与は合算して処理
        """
        # 付与記録を取得（同一日の場合は合算）
        grant_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            expired = False
        ).order_by('grant_date')
        
        balance_by_grant_date = []
        total_balance = 0
        jst = ZoneInfo(settings.TIME_ZONE)
        today = timezone.now().astimezone(jst).date()
        
        # 同一grant_dateをグループ化
        grant_groups = {}
        for grant_record in grant_records:
            grant_date = grant_record.grant_date
            if grant_date not in grant_groups:
                grant_groups[grant_date] = {
                    'total_days': 0,
                    'expiry_date': grant_record.expiry_date,
                }
            grant_groups[grant_date]['total_days'] += grant_record.days
        
        # 各付与日グループごとに処理
        for grant_date, grant_info in sorted(grant_groups.items()):
            # この付与日の使用日数
            used_days = PaidLeaveRecord.objects.filter(
                user=self.user,
                record_type='use',
                grant_date=grant_date
            ).aggregate(total=Sum('days'))['total'] or 0
            
            # 残日数計算（同一日の複数付与を合算）
            total_grant_days = grant_info['total_days']
            remaining_days = total_grant_days - used_days
            remaining_days = max(0, remaining_days)
            
            # 時効まで日数
            days_until_expiry = (grant_info['expiry_date'] - today).days
            
            # 付与日別残日数情報を作成
            grant_balance = GrantDateBalance(
                grant_date=grant_date,
                original_days=total_grant_days,  # 同一日の合計付与日数
                used_days=used_days,
                remaining_days=remaining_days,
                expiry_date=grant_info['expiry_date'],
                days_until_expiry=days_until_expiry
            )
            balance_by_grant_date.append(grant_balance)
            total_balance += remaining_days
        
        # 近い時効情報を作成（30日以内）
        upcoming_expirations = []
        for balance in balance_by_grant_date:
            if balance.days_until_expiry <= 30 and balance.remaining_days > 0:
                expiration_info = ExpirationInfo(
                    grant_date=balance.grant_date,
                    expiry_date=balance.expiry_date,
                    remaining_days=balance.remaining_days,
                    days_until_expiry=balance.days_until_expiry
                )
                upcoming_expirations.append(expiration_info)
        
        return DetailedBalanceInfo(
            total_balance=total_balance,
            balance_by_grant_date=balance_by_grant_date,
            upcoming_expirations=upcoming_expirations
        )
    
    def update_user_balance(self) -> int:
        """
        ユーザーモデルの残日数を最新値に更新
        
        Returns:
            int: 更新後の残日数
            
        Rules:
            - 計算した残日数をuser.current_paid_leaveに保存
        """
        new_balance = self.get_current_balance()
        self.user.current_paid_leave = new_balance
        self.user.save(update_fields=['current_paid_leave'])
        return new_balance
    