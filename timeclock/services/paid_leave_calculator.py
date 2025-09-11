"""
有給休暇計算モジュール

有給休暇の付与計算、出勤率計算、判定処理を担当
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
from django.db.models import Sum
from django.db import models
import math

from ..models import User
from timeclock.models import TimeRecord, PaidLeaveRecord


# 定数定義
ATTENDANCE_RATE_THRESHOLD = 0.8  # 出勤率80%基準
EXPIRY_YEARS = 2  # 有効期限年数
MONTHS_TO_FIRST_GRANT = 6  # 初回付与までの月数

# 付与日数テーブル
GRANT_DAYS_TABLE: Dict[int, Dict[int, int]] = {
    # 週5日以上勤務者（通常労働者）
    5: {1: 10, 2: 11, 3: 12, 4: 14, 5: 16, 6: 18, 7: 20},
    6: {1: 10, 2: 11, 3: 12, 4: 14, 5: 16, 6: 18, 7: 20},
    7: {1: 10, 2: 11, 3: 12, 4: 14, 5: 16, 6: 18, 7: 20},
    # 週4日勤務者
    4: {1: 7, 2: 8, 3: 9, 4: 10, 5: 12, 6: 13, 7: 15},
    # 週3日勤務者
    3: {1: 5, 2: 6, 3: 6, 4: 8, 5: 9, 6: 10, 7: 11},
    # 週2日勤務者
    2: {1: 3, 2: 4, 3: 4, 4: 5, 5: 6, 6: 6, 7: 7},
    # 週1日勤務者
    1: {1: 1, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3}
}

# 7回目以降の付与日数上限
GRANT_DAYS_MAX = {
    5: 20, 6: 20, 7: 20,  # 週5日以上
    4: 15,  # 週4日
    3: 11,  # 週3日
    2: 7,   # 週2日
    1: 3   # 週1日
}


@dataclass
class PaidLeaveJudgment:
    """有給付与判定結果"""
    user: User               # ユーザー
    grant_count: int              # 付与回数
    judgment_date: date           # 判定日
    period_start: date            # 判定期間開始日
    period_end: date              # 判定期間終了日
    required_work_days: int       # 所定労働日数
    attendance_days: int          # 出勤日数
    attendance_rate: float        # 出勤率
    is_eligible: bool             # 付与可否
    grant_days: int               # 付与日数
    expiry_date: date            # 有効期限
    description: str              # 判定理由


@dataclass
class NextGrantInfo:
    """次回付与情報（ユーザー向け表示用）"""
    next_grant_date: date         # 次回付与日
    days_until_grant: int         # 付与日まで残り日数
    current_attendance_days: int   # 現時点の出勤日数
    required_attendance_days: int  # 必要出勤日数（80%基準）
    remaining_attendance_needed: int # あと何日出勤が必要か
    expected_grant_days: int      # 予定付与日数


class PaidLeaveCalculator:
    """有給休暇計算クラス"""
    
    def __init__(self, user):
        """
        Args:
            user: Userモデルのインスタンス
        """
        self.user = user
    
    def _add_months_with_adjustment(self, base_date: date, months: int, years: int = 0) -> date:
        """
        月数と年数を加算し、存在しない日付の場合は月末に調整
        
        Args:
            base_date: 基準日
            months: 加算する月数
            years: 加算する年数
            
        Returns:
            date: 調整済みの日付
        """
        try:
            return base_date + relativedelta(months=months, years=years)
        except ValueError:
            # 存在しない日付の場合は月末に調整
            temp_date = base_date + relativedelta(months=months, years=years)
            return date(temp_date.year, temp_date.month, 1) + relativedelta(months=1) - timedelta(days=1)
        
    def calculate_grant_date(self, grant_count: int) -> date:
        """
        指定回数目の付与日を計算
        
        Args:
            grant_count: 付与回数（1回目、2回目...）
            
        Returns:
            date: 付与日
            
        Rules:
            - 1回目：入社日の6か月後
            - 2回目以降：1回目付与日のn年後
            - 月単位計算、存在しない日は月末に調整
        """
        if grant_count < 1:
            raise ValueError("付与回数は1以上である必要があります")
            
        hire_date = self.user.hire_date
        
        if grant_count == 1:
            # 初回は入社日の6か月後
            grant_date = self._add_months_with_adjustment(hire_date, MONTHS_TO_FIRST_GRANT)
        else:
            # 2回目以降は入社日から（6か月 + (grant_count-1)年）後
            grant_date = self._add_months_with_adjustment(hire_date, MONTHS_TO_FIRST_GRANT, grant_count-1)
            
        return grant_date
        
    def calculate_judgment_period(self, grant_count: int) -> Tuple[date, date]:
        """
        判定対象期間を計算
        
        Args:
            grant_count: 付与回数
            
        Returns:
            tuple[date, date]: (開始日, 終了日)
            
        Rules:
            - 1回目：入社日 〜 付与日前日
            - 2回目以降：前回付与日 〜 今回付与日前日
        """
        if grant_count < 1:
            raise ValueError("付与回数は1以上である必要があります")
            
        grant_date = self.calculate_grant_date(grant_count)
        
        if grant_count == 1:
            # 初回は入社日から付与日前日まで
            start_date = self.user.hire_date
        else:
            # 2回目以降は前回付与日から今回付与日前日まで
            start_date = self.calculate_grant_date(grant_count - 1)
            
        end_date = grant_date - timedelta(days=1)
        return start_date, end_date
        
    def calculate_required_work_days(self, start_date: date, end_date: date, weekly_work_days: int) -> int:
        """
        所定労働日数を計算
        
        Args:
            start_date: 期間開始日
            end_date: 期間終了日
            weekly_work_days: 週所定労働日数
            
        Returns:
            int: 所定労働日数（小数点以下切り捨て）
            
        Rules:
            - 計算式：(期間日数 ÷ 7) × 週所定労働日数
            - 小数点以下切り捨て
            - 期間日数は開始日と終了日を含む（+1日）
        """
        if weekly_work_days < 0 or weekly_work_days > 7:
            raise ValueError("週所定労働日数は0-7の範囲である必要があります")
            
        period_days = (end_date - start_date).days + 1  # 開始日を含む、終了日を含む
        if period_days <= 0:
            raise ValueError("終了日は開始日以降である必要があります")
            
        work_days = (period_days / 7) * weekly_work_days
        return int(work_days)  # 小数点以下切り捨て
        
    def calculate_attendance_days(self, start_date: date, end_date: date) -> int:
        """
        出勤日数を計算（実出勤 + 有給取得）
        
        Args:
            start_date: 期間開始日
            end_date: 期間終了日
            
        Returns:
            int: 出勤日数
            
        Rules:
            - 実出勤日数 + 有給休暇取得日数
        """
        # 実出勤日数を計算（clock_inレコード数）
        actual_work_days = TimeRecord.objects.filter(
            user=self.user,
            clock_type='clock_in',
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).count()
        
        # 有給取得日数を計算
        paid_leave_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='use',
            used_date__gte=start_date,
            used_date__lte=end_date
        ).aggregate(total=models.Sum('days'))['total'] or 0
        
        return actual_work_days + paid_leave_days
        
    def calculate_attendance_rate(self, attendance_days: int, required_work_days: int) -> float:
        """
        出勤率を計算
        
        Args:
            attendance_days: 出勤日数
            required_work_days: 所定労働日数
            
        Returns:
            float: 出勤率（0.0〜1.0）
            
        Raises:
            ZeroDivisionError: required_work_days が 0 の場合
        """
        if required_work_days == 0:
            raise ZeroDivisionError("所定労働日数が0のため出勤率を計算できません")
            
        return attendance_days / required_work_days
        
    def calculate_attendance(self, start_date: date, end_date: date) -> tuple[int, float]:
        """
        出勤日数を計算（実出勤 + 有給取得）
        出勤率を計算（出勤日数/所定労働日数）

        Args:
            start_date: 期間開始日
            end_date: 期間終了日
              
        Returns:
            tuple[int, float]: (出勤日数, 出勤率（0.0〜1.0）)
              
        Rules:
            - 実出勤日数 + 有給休暇取得日数
            - 出勤率 = 出勤日数 ÷ 所定労働日数

        Raises:
            ValueError: start_dateよりend_dateが過去の場合
        """
        if start_date > end_date:
            raise ValueError("開始日が終了日より後です")
            
        # 出勤日数を計算
        attendance_days = self.calculate_attendance_days(start_date, end_date)
        
        # 所定労働日数を計算
        required_work_days = self.calculate_required_work_days(
            start_date, end_date, self.user.weekly_work_days
        )
        
        # 出勤率を計算
        if required_work_days == 0:
            attendance_rate = 0.0
        else:
            attendance_rate = self.calculate_attendance_rate(attendance_days, required_work_days)
            
        return attendance_days, attendance_rate
        
    def determine_grant_days(self, grant_count: int, weekly_work_days: int) -> int:
        """
        付与日数を決定
        
        Args:
            grant_count: 付与回数
            weekly_work_days: 週所定労働日数
            
        Returns:
            int: 付与日数
            
        Rules:
            - 勤続年数と週所定労働日数から付与日数テーブルを参照
            - 週5日以上は通常労働者テーブル
            - 週4日以下は比例付与テーブル
        """
        if weekly_work_days < 1 or weekly_work_days > 7:
            raise ValueError("週所定労働日数は1-7の範囲である必要があります")
        
        # 週5日以上の場合、週5日のテーブルを使用
        table_key = min(weekly_work_days, 5)
        grant_table = GRANT_DAYS_TABLE.get(table_key, {})
        
        # 7回目以降は上限値を使用
        if grant_count >= 7:
            return GRANT_DAYS_MAX.get(table_key, 0)
        
        return grant_table.get(grant_count, 0)
            
    def judge_grant_eligibility(self, grant_count: int) -> PaidLeaveJudgment:
        """
        付与可否を総合判定
        
        Args:
            grant_count: 付与回数
            
        Returns:
            PaidLeaveJudgment: 判定結果
            
        Rules:
            - 在籍状況チェック
            - 出勤率80%以上チェック
            - その他必要条件のチェック
        """
        # 判定期間を取得
        period_start, period_end = self.calculate_judgment_period(grant_count)

        # 判定日は期間終了日の翌日
        judgment_date = period_end + timedelta(days=1) 
        
        # 週労働日数を取得
        weekly_work_days = self.user.weekly_work_days
        
        # 所定労働日数を計算
        required_work_days = self.calculate_required_work_days(
            period_start, period_end, weekly_work_days
        )
        
        # 週0日勤務の場合は付与対象外
        if required_work_days == 0:
            return PaidLeaveJudgment(
                grant_count=grant_count,
                judgment_date=judgment_date,
                period_start=period_start,
                period_end=period_end,
                required_work_days=required_work_days,
                attendance_days=0,
                attendance_rate=0.0,
                is_eligible=False,
                grant_days=0,
                expiry_date=judgment_date,
                description="週所定労働日数が0のため付与対象外"
            )
            
        # 出勤日数、出勤率を計算
        attendance_days, attendance_rate = self.calculate_attendance(period_start, period_end)
        
        # 付与日数を決定
        grant_days = self.determine_grant_days(grant_count, weekly_work_days)
        
        # 有効期限を計算
        expiry_date = self.calculate_expiry_date(judgment_date)
        
        # 出勤率がしきい値以上かチェック
        is_eligible = attendance_rate >= ATTENDANCE_RATE_THRESHOLD
        
        if is_eligible:
            description = "付与条件を満たしています"
        else:
            description = "出勤率が80%未満のため付与なし"
            grant_days = 0

        return PaidLeaveJudgment(
            user=self.user,
            grant_count=grant_count,
            judgment_date=judgment_date,
            period_start=period_start,
            period_end=period_end,
            required_work_days=required_work_days,
            attendance_days=attendance_days,
            attendance_rate=attendance_rate,
            is_eligible=is_eligible,
            grant_days=grant_days,
            expiry_date=expiry_date,
            description=description
        )
        
    def calculate_expiry_date(self, grant_date: date) -> date:
        """
        有効期限を計算
        
        Args:
            grant_date: 付与日
            
        Returns:
            date: 有効期限（付与日から2年後）
            
        Rules:
            - 付与日から2年後の同日
            - 存在しない日は月末に調整
        """
        return self._add_months_with_adjustment(grant_date, 0, EXPIRY_YEARS)
    
    def should_rejudge(self, modified_record_date: date, modification_date: date) -> bool:
        """
        再判定が必要かを判断
        
        Args:
            modified_record_date: 修正された記録の日付
            modification_date: 修正が行われた日
            
        Returns:
            bool: 再判定が必要な場合True
            
        Rules:
            - 修正された記録の日付が直近付与日より過去の場合に再判定
            - ルール文書の再判定例に準拠
        """
        # 直近付与日を取得
        latest_grant_date = self.user.get_latest_grant_date(modification_date)
        
        if latest_grant_date is None:
            # まだ付与日がない場合は再判定不要
            return False
        
        # 修正された記録の日付が直近付与日より過去の場合に再判定
        return modified_record_date < latest_grant_date
    
    def find_affected_grants(self, modified_record_date: date) -> Optional[int]:
        """
        修正により影響を受ける付与回を特定
        
        Args:
            modified_record_date: 修正された記録の日付
            
        Returns:
            Optional[int]: 影響を受ける付与回（影響がない場合はNone）
            
        Rules:
            - 修正された記録の日付が判定対象期間に含まれる付与回を特定
            - 複数の期間に該当する場合は最も直近の付与回を返す
        """
        # 最大20回まで確認（直近から過去へ）
        for grant_count in range(20, 0, -1):
            try:
                period_start, period_end = self.calculate_judgment_period(grant_count)
                
                # 修正された記録の日付が判定期間に含まれるかチェック
                if period_start <= modified_record_date <= period_end:
                    return grant_count
                    
            except ValueError:
                # 付与日計算でエラーが発生した場合はその回はスキップ
                continue
        
        return None
    
    def get_next_grant_info(self, reference_date: date = None) -> NextGrantInfo:
        """
        次回付与情報を取得（ユーザー向け情報表示用）
        
        Args:
            reference_date: 基準日（Noneの場合は今日）
            
        Returns:
            NextGrantInfo: 次回付与の詳細情報
            
        Rules:
            - 次回付与日、必要出勤日数、予定付与日数を計算
            - 現在の出勤状況も含める
        """
        if reference_date is None:
            reference_date = date.today()
        
        # 次回の付与回数を特定
        next_grant_count = 1
        for i in range(1, 21):  # 最大20回まで確認
            try:
                grant_date = self.calculate_grant_date(i)
                if grant_date > reference_date:
                    next_grant_count = i
                    break
            except ValueError:
                break
        else:
            # 20回まで全て過去の場合、最後の回を使用
            next_grant_count = 20
        
        # 次回付与日
        next_grant_date = self.calculate_grant_date(next_grant_count)
        
        # 付与日までの残り日数
        days_until_grant = (next_grant_date - reference_date).days
        
        # 判定期間
        period_start, period_end = self.calculate_judgment_period(next_grant_count)
        
        # 現時点の出勤日数
        current_attendance_days = self.calculate_attendance_days(
            period_start, min(period_end, reference_date)
        )
        
        # 全判定期間の所定労働日数
        total_required_work_days = self.calculate_required_work_days(
            period_start, period_end, self.user.weekly_work_days
        )
        
        # 必要出勤日数（しきい値基準）
        required_attendance_days = int(math.ceil(total_required_work_days * ATTENDANCE_RATE_THRESHOLD))
        
        # あと何日出勤が必要か
        remaining_attendance_needed = max(0, required_attendance_days - current_attendance_days)
        
        # 予定付与日数
        expected_grant_days = self.determine_grant_days(next_grant_count, self.user.weekly_work_days)
        
        return NextGrantInfo(
            next_grant_date=next_grant_date,
            days_until_grant=days_until_grant,
            current_attendance_days=current_attendance_days,
            required_attendance_days=required_attendance_days,
            remaining_attendance_needed=remaining_attendance_needed,
            expected_grant_days=expected_grant_days
        )
    