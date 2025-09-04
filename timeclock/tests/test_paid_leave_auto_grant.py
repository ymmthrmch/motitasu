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


class PaidLeaveAutoGrantTestCase(TestCase):
    """有給休暇自動付与テスト基底クラス"""
    
    def setUp(self):
        """テスト共通設定"""
        self.jst = pytz.timezone('Asia/Tokyo')
        self.command = Command()
        
    def create_test_user(self, name, email, hire_date, weekly_work_days=5):
        """テストユーザー作成ヘルパー"""
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
    
    def create_attendance_records(self, user, start_date, end_date, attendance_rate=1.0):
        """出勤記録作成ヘルパー"""
        current = start_date
        work_day_count = 0
        attended_days = 0
        
        while current <= end_date:
            if current.weekday() < user.weekly_work_days:  # 週労働日数に応じた曜日
                work_day_count += 1
                # 指定された出勤率に応じて出勤記録を作成
                should_attend = attended_days < int(work_day_count * attendance_rate)
                
                if should_attend:
                    clock_in = self.jst.localize(
                        datetime.combine(current, datetime.min.time().replace(hour=9))
                    )
                    clock_out = self.jst.localize(
                        datetime.combine(current, datetime.min.time().replace(hour=18))
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
                    attended_days += 1
            
            current += timedelta(days=1)
        
        return attended_days, work_day_count
    
    def execute_grant_process(self, target_date):
        """指定日付で付与処理を実行"""
        mock_datetime = self.jst.localize(
            datetime.combine(target_date, datetime.min.time())
        )
        
        with patch('django.utils.timezone.now', return_value=mock_datetime):
            self.command.handle(dry_run=False, fix_inconsistencies=False)


class Test1_UnderSixMonths(PaidLeaveAutoGrantTestCase):
    """1. 継続勤務6か月未満のテスト"""
    
    def test_fulltime_5months_100percent(self):
        """正社員、勤務開始後5か月、出勤率100%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('田中太郎', 'tanaka@example.com', hire_date, 5)
        
        # 5ヶ月間の出勤記録（100%）
        end_date = date(2025, 7, 31)  # 5ヶ月未満
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 8月1日に処理実行（まだ6ヶ月未満）
        self.execute_grant_process(date(2025, 8, 1))
        
        # 付与されないことを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
        
        grant_count = PaidLeaveRecord.objects.filter(user=user, record_type='grant').count()
        self.assertEqual(grant_count, 0)
    
    def test_parttime_5months_100percent(self):
        """パート（週3日勤務）、勤務開始後5か月、出勤率100%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('佐藤花子', 'sato@example.com', hire_date, 3)
        
        end_date = date(2025, 7, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        self.execute_grant_process(date(2025, 8, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)


class Test2_SixMonthsToOneYear(PaidLeaveAutoGrantTestCase):
    """2. 継続勤務6か月以上1年未満のテスト"""
    
    def test_fulltime_6months_80percent_grant(self):
        """正社員、勤務6か月、出勤率80%以上"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('山田一郎', 'yamada@example.com', hire_date, 5)
        
        # 6ヶ月間の出勤記録（82%）
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.82)
        
        # 9月1日に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        # 結果確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)
        
        grant_record = PaidLeaveRecord.objects.filter(user=user, record_type='grant').first()
        self.assertIsNotNone(grant_record)
        self.assertEqual(grant_record.days, 10)
        
    def test_fulltime_6months_79percent_no_grant(self):
        """正社員、勤務6か月、出勤率79%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('鈴木次郎', 'suzuki@example.com', hire_date, 5)
        
        # 6ヶ月間の出勤記録（79%）
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.79)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
    
    def test_parttime_week4_6months_90percent(self):
        """パート、週4日勤務、出勤率90%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('高橋美咲', 'takahashi@example.com', hire_date, 4)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.90)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 7)
    
    def test_parttime_week1_6months_100percent(self):
        """パート、週1日勤務、出勤率100%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('伊藤由美', 'ito@example.com', hire_date, 1)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 1)


class Test3_MultipleYearGrants(PaidLeaveAutoGrantTestCase):
    """3. 継続勤務1.5年〜6.5年以上のテスト"""
    
    def test_fulltime_1_5years_100percent(self):
        """正社員、勤務1.5年、出勤率100%"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('渡辺健太', 'watanabe@example.com', hire_date, 5)
        
        # 1.5年間の出勤記録
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 1.5年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 11)
    
    def test_fulltime_2_5years_100percent(self):
        """正社員、勤務2.5年、出勤率100%"""
        hire_date = date(2023, 3, 1)
        user = self.create_test_user('中村和也', 'nakamura@example.com', hire_date, 5)
        
        # 2.5年間の出勤記録
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 2.5年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 12)
    
    def test_fulltime_6years_100percent(self):
        """正社員、勤務6年、出勤率100%"""
        hire_date = date(2019, 3, 1)
        user = self.create_test_user('小林真理', 'kobayashi@example.com', hire_date, 5)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 6年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 20)
    
    def test_fulltime_6_5years_100percent_max(self):
        """正社員、勤務6年6か月、出勤率100%（上限）"""
        hire_date = date(2019, 3, 1)
        user = self.create_test_user('加藤洋子', 'kato@example.com', hire_date, 5)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 6年6ヶ月後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 20)  # 上限20日
    
    def test_parttime_week3_3_5years(self):
        """パート、週3日勤務、勤務3.5年、出勤率100%"""
        hire_date = date(2022, 3, 1)
        user = self.create_test_user('松本大輔', 'matsumoto@example.com', hire_date, 3)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 3.5年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 8)
    
    def test_parttime_week2_5_5years(self):
        """パート、週2日勤務、勤務5.5年、出勤率100%"""
        hire_date = date(2020, 3, 1)
        user = self.create_test_user('森田智子', 'morita@example.com', hire_date, 2)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 5.5年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 6)


class Test4_AttendanceRateCheck(PaidLeaveAutoGrantTestCase):
    """4. 出勤率チェックテスト"""
    
    def test_fulltime_1year_79percent_no_grant(self):
        """正社員、勤務1年、出勤率79%"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('井上正美', 'inoue@example.com', hire_date, 5)
        
        # 1年間の出勤記録（79%）
        end_date = date(2025, 2, 28)
        self.create_attendance_records(user, hire_date, end_date, 0.79)
        
        # 1年後（18ヶ月付与タイミング）で処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
    
    def test_parttime_week4_1year_75percent_no_grant(self):
        """パート、週4日勤務、勤務1年、出勤率75%"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('木村健司', 'kimura@example.com', hire_date, 4)
        
        end_date = date(2025, 2, 28)
        self.create_attendance_records(user, hire_date, end_date, 0.75)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)


class Test5_ExpiryAndCarryover(PaidLeaveAutoGrantTestCase):
    """5. 有効期限・繰越の確認テスト"""
    
    def test_expiry_after_2years_partial_used(self):
        """正社員、10日付与、1年後に残7日、さらに1年後時効"""
        hire_date = date(2023, 3, 1)
        user = self.create_test_user('清水美香', 'shimizu@example.com', hire_date, 5)
        
        # 2年前に10日付与済み
        grant_date = date(2023, 9, 1)
        expiry_date = grant_date + relativedelta(years=2)
        
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=grant_date,
            expiry_date=expiry_date,
            description='6ヶ月付与'
        )
        
        # 3日使用済み
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=3,
            grant_date=grant_date,
            expiry_date=expiry_date,
            description='夏季休暇'
        )
        
        user.current_paid_leave = 7  # 10 - 3 = 7
        user.save()
        
        # 有効期限日に時効処理実行
        self.execute_grant_process(expiry_date)
        
        # 未使用7日が時効消滅
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
        
        expire_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='expire'
        ).first()
        self.assertIsNotNone(expire_record)
        self.assertEqual(expire_record.days, 7)
    
    def test_parttime_week3_expiry_after_use(self):
        """パート、週3日勤務、6日付与、1年後3日使用、さらに1年経過"""
        hire_date = date(2023, 3, 1)
        user = self.create_test_user('岡田裕太', 'okada@example.com', hire_date, 3)
        
        # 2年前に6日付与済み
        grant_date = date(2023, 9, 1)
        expiry_date = grant_date + relativedelta(years=2)
        
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=6,
            grant_date=grant_date,
            expiry_date=expiry_date,
            description='6ヶ月付与'
        )
        
        # 3日使用済み
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=3,
            grant_date=grant_date,
            expiry_date=expiry_date,
            description='家族旅行'
        )
        
        user.current_paid_leave = 3  # 6 - 3 = 3
        user.save()
        
        # 時効処理実行
        self.execute_grant_process(expiry_date)
        
        # 残3日消失
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)


class Test6_BoundaryTests(PaidLeaveAutoGrantTestCase):
    """6. 境界値テスト"""
    
    def test_exactly_6months_exactly_80percent(self):
        """正社員、勤務6か月ちょうど、出勤率80%ちょうど"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('藤田雅人', 'fujita@example.com', hire_date, 5)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.80)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)
    
    def test_exactly_6months_exactly_79_9percent(self):
        """正社員、勤務6か月ちょうど、出勤率79.9%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('原田さくら', 'harada@example.com', hire_date, 5)
        
        end_date = date(2025, 8, 31)
        # 79.9%の出勤率
        attended, total = self.create_attendance_records(user, hire_date, end_date, 0.799)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
    
    def test_parttime_week4_1_5years_minimum_days(self):
        """パート、週4日勤務、勤務1.5年、所定労働日数最小値"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('石川直樹', 'ishikawa@example.com', hire_date, 4)
        
        # 最小限の出勤で80%をクリア
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.81)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 8)


class Test7_UpperLimit(PaidLeaveAutoGrantTestCase):
    """7. 上限確認テスト"""
    
    def test_fulltime_10years_100percent_limit(self):
        """正社員、勤務10年、出勤率100%（上限20日）"""
        hire_date = date(2015, 3, 1)
        user = self.create_test_user('山口直美', 'yamaguchi@example.com', hire_date, 5)
        
        # 10年間の出勤記録
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        # 10年後に付与処理実行
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 20)  # 上限20日


class Test8_ParttimePatterns(PaidLeaveAutoGrantTestCase):
    """8. 非正社員のパターンテスト"""
    
    def test_week2_6months_80percent(self):
        """週2日勤務、勤務0.5年、出勤率80%"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('長谷川修', 'hasegawa@example.com', hire_date, 2)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 0.80)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 3)
    
    def test_week1_3_5years_100percent(self):
        """週1日勤務、勤務3.5年、出勤率100%"""
        hire_date = date(2022, 3, 1)
        user = self.create_test_user('斉藤千代', 'saito@example.com', hire_date, 1)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 2)
    
    def test_week3_6_5years_100percent(self):
        """週3日勤務、勤務6.5年、出勤率100%"""
        hire_date = date(2019, 3, 1)
        user = self.create_test_user('遠藤光男', 'endo@example.com', hire_date, 3)
        
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 11)


class Test9_ComprehensiveScenarios(PaidLeaveAutoGrantTestCase):
    """9. 総合ケーステスト"""
    
    def test_improvement_after_initial_failure(self):
        """正社員、6か月経過、出勤率79%、その後1年経過、80%に改善"""
        hire_date = date(2025, 3, 1)
        user = self.create_test_user('関口美穂', 'sekiguchi@example.com', hire_date, 5)
        
        # 6ヶ月時点で79%の出勤記録
        end_date_first = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date_first, 0.79)
        
        # 初回付与処理（失敗するはず）
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)
        
        # 追加の出勤で80%に改善
        end_date_second = date(2026, 8, 31)
        self.create_attendance_records(user, end_date_first + timedelta(days=1), end_date_second, 1.0)
        
        # 18ヶ月後の処理で付与されるかテスト
        self.execute_grant_process(date(2026, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 11)
    
    def test_parttime_week3_1_5years_minimum_workdays(self):
        """パート、週3日勤務、勤務1.5年、所定労働日数最小値、出勤率100%"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('橋本恵子', 'hashimoto@example.com', hire_date, 3)
        
        # 最小限の勤務日数で100%出勤
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, hire_date, end_date, 1.0)
        
        self.execute_grant_process(date(2025, 9, 1))
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 6)


class Test10_ServiceCalculations(PaidLeaveAutoGrantTestCase):
    """10. サービス計算ロジックテスト"""
    
    def test_service_months_various_dates(self):
        """様々な日付での勤続月数計算"""
        hire_date = date(2024, 1, 15)
        user = self.create_test_user('計算テスト', 'calc@example.com', hire_date, 5)
        
        service = PaidLeaveService(user)
        
        test_cases = [
            (date(2024, 7, 14), 5),   # 6ヶ月未満
            (date(2024, 7, 15), 6),   # 6ヶ月ちょうど
            (date(2024, 7, 16), 6),   # 6ヶ月と1日
            (date(2025, 1, 14), 11),  # 1年未満
            (date(2025, 1, 15), 12),  # 1年ちょうど
            (date(2025, 7, 15), 18),  # 1年6ヶ月
            (date(2030, 7, 15), 78),  # 6年6ヶ月
        ]
        
        for test_date, expected_months in test_cases:
            with self.subTest(test_date=test_date, expected=expected_months):
                months = service._calculate_service_months(hire_date, test_date)
                self.assertEqual(months, expected_months,
                    f'日付 {test_date} で勤続月数が {months} だが {expected_months} を期待')
    
    def test_grant_days_fulltime_all_milestones(self):
        """正社員の全マイルストーン付与日数計算"""
        user = self.create_test_user('正社員テスト', 'fulltime@example.com', date.today(), 5)
        service = PaidLeaveService(user)
        
        expected_days = {
            6: 10, 18: 11, 30: 12, 42: 14,
            54: 16, 66: 18, 78: 20, 90: 20  # 78ヶ月以降は上限20日
        }
        
        for months, expected in expected_days.items():
            with self.subTest(months=months):
                days = service._get_grant_days_by_months(months)
                self.assertEqual(days, expected,
                    f'{months}ヶ月で{days}日だが{expected}日を期待')
    
    def test_grant_days_parttime_week4(self):
        """週4日勤務の付与日数計算"""
        user = self.create_test_user('週4日テスト', 'week4@example.com', date.today(), 4)
        service = PaidLeaveService(user)
        
        test_cases = [(6, 7), (18, 8), (30, 9), (42, 10), (54, 12), (66, 13), (78, 15)]
        for months, expected in test_cases:
            with self.subTest(months=months):
                days = service._get_grant_days_by_months(months)
                self.assertEqual(days, expected)
    
    def test_grant_days_parttime_week3(self):
        """週3日勤務の付与日数計算"""
        user = self.create_test_user('週3日テスト', 'week3@example.com', date.today(), 3)
        service = PaidLeaveService(user)
        
        test_cases = [(6, 5), (18, 6), (30, 6), (42, 8), (54, 9), (66, 10), (78, 11)]
        for months, expected in test_cases:
            with self.subTest(months=months):
                days = service._get_grant_days_by_months(months)
                self.assertEqual(days, expected)
    
    def test_grant_days_parttime_week2(self):
        """週2日勤務の付与日数計算"""
        user = self.create_test_user('週2日テスト', 'week2@example.com', date.today(), 2)
        service = PaidLeaveService(user)
        
        test_cases = [(6, 3), (18, 4), (30, 4), (42, 5), (54, 6), (66, 6), (78, 7)]
        for months, expected in test_cases:
            with self.subTest(months=months):
                days = service._get_grant_days_by_months(months)
                self.assertEqual(days, expected)
    
    def test_grant_days_parttime_week1(self):
        """週1日勤務の付与日数計算"""
        user = self.create_test_user('週1日テスト', 'week1@example.com', date.today(), 1)
        service = PaidLeaveService(user)
        
        test_cases = [(6, 1), (18, 2), (30, 2), (42, 2), (54, 3), (66, 3), (78, 3)]
        for months, expected in test_cases:
            with self.subTest(months=months):
                days = service._get_grant_days_by_months(months)
                self.assertEqual(days, expected)


class Test11_ConsistencyCheck(PaidLeaveAutoGrantTestCase):
    """11. 整合性チェックテスト"""
    
    def test_recalculate_current_leave_accuracy(self):
        """現在有給日数の再計算精度テスト"""
        hire_date = date(2024, 3, 1)
        user = self.create_test_user('整合性テスト', 'consistency@example.com', hire_date, 5)
        
        # 複数の付与・使用・時効レコードを作成
        grant1_date = date(2024, 9, 1)
        grant2_date = date(2025, 9, 1)
        
        # 1回目付与（有効）
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=grant1_date,
            expiry_date=grant1_date + relativedelta(years=2),
            description='6ヶ月付与'
        )
        
        # 2回目付与（有効）
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=11,
            grant_date=grant2_date,
            expiry_date=grant2_date + relativedelta(years=2),
            description='18ヶ月付与'
        )
        
        # 使用記録
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=5,
            grant_date=grant1_date,
            expiry_date=grant1_date + relativedelta(years=2),
            description='夏季休暇'
        )
        
        # 時効記録（古い分の一部）
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='expire',
            days=2,
            grant_date=grant1_date,
            expiry_date=grant1_date + relativedelta(years=2),
            description='時効消滅'
        )
        
        # 間違った current_paid_leave を設定
        user.current_paid_leave = 999
        user.save()
        
        # 整合性チェック実行
        service = PaidLeaveService(user)
        correct_days = service.recalculate_current_leave()
        
        # 正しい計算: (10 + 11) - 5 - 2 = 14
        self.assertEqual(correct_days, 14)
        
        # 管理コマンドでの修正テスト
        self.command.handle(dry_run=False, fix_inconsistencies=True)
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 14)


class Test12_EdgeCases(PaidLeaveAutoGrantTestCase):
    """12. エッジケーステスト"""
    
    def test_no_hire_date_set(self):
        """雇用開始日未設定のユーザー"""
        user = self.create_test_user('未設定ユーザー', 'unset@example.com', None, 5)
        
        service = PaidLeaveService(user)
        status = service.get_paid_leave_status()
        
        self.assertEqual(status['current_days'], 0)
        self.assertIsNone(status['next_grant'])
        self.assertEqual(status['error'], '雇用開始日が設定されていません')
    
    def test_future_hire_date(self):
        """未来の雇用開始日"""
        future_date = date.today() + timedelta(days=30)
        user = self.create_test_user('未来雇用', 'future@example.com', future_date, 5)
        
        service = PaidLeaveService(user)
        status = service.get_paid_leave_status()
        
        self.assertEqual(status['service_months'], 0)
        self.assertIsNone(status['next_grant'])
    
    def test_weekend_hire_date(self):
        """土日の雇用開始日"""
        # 土曜日に雇用開始
        saturday = date(2025, 3, 1)  # 2025-03-01は土曜日
        user = self.create_test_user('土曜雇用', 'saturday@example.com', saturday, 5)
        
        # 6ヶ月間の出勤記録（平日のみ）
        end_date = date(2025, 8, 31)
        self.create_attendance_records(user, saturday, end_date, 0.82)
        
        # 6ヶ月後の処理で正しく付与されるか
        grant_target = saturday + relativedelta(months=6)
        self.execute_grant_process(grant_target)
        
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)