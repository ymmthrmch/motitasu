from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
from unittest.mock import patch

from timeclock.models import PaidLeaveRecord, TimeRecord
from timeclock.services.paid_leave_service import PaidLeaveService
from timeclock.management.commands.process_paid_leaves import Command

User = get_user_model()


class PaidLeaveAutoGrantTest(TestCase):
    """有給休暇自動付与の基本テスト"""
    
    def setUp(self):
        """テスト共通設定"""
        self.jst = pytz.timezone('Asia/Tokyo')
        self.command = Command()
        
    def create_test_user(self, name, email, hire_date, weekly_work_days=5):
        """テストユーザー作成"""
        user = User.objects.create_user(
            name=name,
            email=email,
            password='motitasu'
        )
        user.hire_date = hire_date
        user.weekly_work_days = weekly_work_days
        user.current_paid_leave = 0
        user.save()
        return user
    
    def create_daily_attendance(self, user, work_date):
        """指定日の出勤記録を作成"""
        clock_in = self.jst.localize(
            datetime.combine(work_date, datetime.min.time().replace(hour=9))
        )
        clock_out = self.jst.localize(
            datetime.combine(work_date, datetime.min.time().replace(hour=18))
        )
        
        TimeRecord.objects.create(
            user=user,
            clock_type='clock_in',
            timestamp=clock_in
        )
        TimeRecord.objects.create(
            user=user,
            clock_type='clock_out',
            timestamp=clock_out
        )
    
    def test_6months_80percent_grant(self):
        """6ヶ月勤続、80%出勤率で10日付与"""
        # 6ヶ月前に雇用開始
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('山田太郎', 'yamada@example.com', hire_date, 5)
        
        # 6ヶ月間の出勤記録（週5日中4日出勤で80%）
        current = hire_date
        work_day_count = 0
        
        while current < date(2025, 9, 1):  # 6ヶ月後まで
            if current.weekday() < 5:  # 月-金
                work_day_count += 1
                if work_day_count % 5 != 0:  # 5日に4日出勤（80%）
                    self.create_daily_attendance(user, current)
            current += timedelta(days=1)
        
        # 9月1日時点で付与処理実行
        grant_date = date(2025, 9, 1)
        mock_datetime = self.jst.localize(
            datetime.combine(grant_date, datetime.min.time())
        )
        
        with patch('django.utils.timezone.now', return_value=mock_datetime):
            self.command.handle(dry_run=False, fix_inconsistencies=False)
        
        # 結果確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)
        
        # 付与記録確認
        grant_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='grant'
        ).first()
        
        self.assertIsNotNone(grant_record)
        self.assertEqual(grant_record.days, 10)
        self.assertEqual(grant_record.grant_date, grant_date)
        
        # 有効期限は2年後
        expected_expiry = grant_date + relativedelta(years=2)
        self.assertEqual(grant_record.expiry_date, expected_expiry)
    
    def test_6months_79percent_no_grant(self):
        """6ヶ月勤続、79%出勤率で付与なし"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('佐藤花子', 'sato@example.com', hire_date, 5)
        
        # 6ヶ月間の出勤記録（79%）
        current = hire_date
        work_day_count = 0
        
        while current < date(2025, 9, 1):
            if current.weekday() < 5:
                work_day_count += 1
                # 約79%の出勤率
                if work_day_count <= int(work_day_count * 0.79):
                    self.create_daily_attendance(user, current)
            current += timedelta(days=1)
        
        # 付与処理実行
        grant_date = date(2025, 9, 1)
        mock_datetime = self.jst.localize(
            datetime.combine(grant_date, datetime.min.time())
        )
        
        with patch('django.utils.timezone.now', return_value=mock_datetime):
            self.command.handle(dry_run=False, fix_inconsistencies=False)
        
        # 結果確認：付与されないはず
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
        
        grant_count = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='grant'
        ).count()
        self.assertEqual(grant_count, 0)
    
    def test_parttime_week4_6months(self):
        """パート週4日、6ヶ月勤続で7日付与"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('鈴木次郎', 'suzuki@example.com', hire_date, 4)
        
        # 6ヶ月間の出勤記録（週4日中3日出勤で75%、ただし週4日勤務者なので要調整）
        current = hire_date
        work_day_count = 0
        
        while current < date(2025, 9, 1):
            if current.weekday() < 4:  # 月-木（週4日勤務）
                work_day_count += 1
                if work_day_count % 5 != 0:  # 5日に4日出勤（80%）
                    self.create_daily_attendance(user, current)
            current += timedelta(days=1)
        
        # 付与処理実行
        grant_date = date(2025, 9, 1)
        mock_datetime = self.jst.localize(
            datetime.combine(grant_date, datetime.min.time())
        )
        
        with patch('django.utils.timezone.now', return_value=mock_datetime):
            self.command.handle(dry_run=False, fix_inconsistencies=False)
        
        # 結果確認：7日付与
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 7)
    
    def test_expiry_after_2years(self):
        """2年後の時効消滅テスト"""
        hire_date = date(2023, 3, 1)
        user = self.create_test_user('田中三郎', 'tanaka3@example.com', hire_date, 5)
        
        # 2年前に10日付与済み
        old_grant_date = date(2023, 9, 1)
        old_expiry_date = old_grant_date + relativedelta(years=2)
        
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=old_grant_date,
            expiry_date=old_expiry_date,
            description='6ヶ月付与'
        )
        
        # 3日使用済み
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=3,
            grant_date=old_grant_date,
            expiry_date=old_expiry_date,
            description='休暇使用'
        )
        
        user.current_paid_leave = 7  # 10 - 3 = 7
        user.save()
        
        # 有効期限当日に時効処理実行
        mock_datetime = self.jst.localize(
            datetime.combine(old_expiry_date, datetime.min.time())
        )
        
        with patch('django.utils.timezone.now', return_value=mock_datetime):
            self.command.handle(dry_run=False, fix_inconsistencies=False)
        
        # 結果確認：7日が時効消滅
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
        
        # 時効レコードの確認
        expire_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='expire'
        ).first()
        
        self.assertIsNotNone(expire_record)
        self.assertEqual(expire_record.days, 7)
    
    def test_service_calculation_accuracy(self):
        """勤続月数計算の正確性テスト"""
        hire_date = date(2024, 1, 15)
        user = self.create_test_user('計算テスト', 'calc@example.com', hire_date, 5)
        
        service = PaidLeaveService(user)
        
        # 様々な日付での勤続月数計算
        test_cases = [
            (date(2024, 7, 14), 5),  # 6ヶ月未満
            (date(2024, 7, 15), 6),  # 6ヶ月ちょうど
            (date(2024, 7, 16), 6),  # 6ヶ月と1日
            (date(2025, 1, 14), 11),  # 1年未満
            (date(2025, 1, 15), 12),  # 1年ちょうど
            (date(2025, 7, 15), 18),  # 1年6ヶ月
        ]
        
        for test_date, expected_months in test_cases:
            with self.subTest(test_date=test_date):
                months = service._calculate_service_months(hire_date, test_date)
                self.assertEqual(months, expected_months,
                    f'日付 {test_date} で勤続月数が {months} だが {expected_months} を期待')