"""
PaidLeaveCalculatorクラスのテストモジュール
"""

from datetime import date, datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from timeclock.services.paid_leave_calculator import PaidLeaveCalculator
from timeclock.models import TimeRecord, PaidLeaveRecord

User = get_user_model()


class TestPaidLeaveCalculator(TestCase):
    """PaidLeaveCalculatorのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.user = User.objects.create(
            name="testuser",
            email="test@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=5,
        )
        self.calculator = PaidLeaveCalculator(self.user)

    def test_calculate_grant_date_normal(self):
        """テストケース1-1: 通常日付での付与日計算"""
        self.assertEqual(self.calculator.calculate_grant_date(1), date(2000, 7, 1))
        self.assertEqual(self.calculator.calculate_grant_date(2), date(2001, 7, 1))
        self.assertEqual(self.calculator.calculate_grant_date(3), date(2002, 7, 1))
        self.assertEqual(self.calculator.calculate_grant_date(7), date(2006, 7, 1))

    def test_calculate_grant_date_leap_year(self):
        """テストケース1-2: 月末入社での付与日計算（閏年考慮）"""
        user = User.objects.create(
            name="testuser_leap",
            email="leap@example.com",
            hire_date=date(2003, 8, 31),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        self.assertEqual(calculator.calculate_grant_date(1), date(2004, 2, 29))
        self.assertEqual(calculator.calculate_grant_date(2), date(2005, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(3), date(2006, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(4), date(2007, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(5), date(2008, 2, 29))

    def test_calculate_grant_date_month_end_adjustment(self):
        """テストケース1-3: 月末調整が必要な日付での付与日計算"""
        user = User.objects.create(
            name="testuser_month_end",
            email="monthend@example.com",
            hire_date=date(2000, 8, 29),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        self.assertEqual(calculator.calculate_grant_date(1), date(2001, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(2), date(2002, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(3), date(2003, 2, 28))
        self.assertEqual(calculator.calculate_grant_date(4), date(2004, 2, 29))

    def test_calculate_judgment_period_first_grant(self):
        """テストケース2-1: 初回付与の判定期間"""
        user = User.objects.create(
            name="testuser_period",
            email="period@example.com",
            hire_date=date(2000, 4, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        start_date, end_date = calculator.calculate_judgment_period(1)
        self.assertEqual(start_date, date(2000, 4, 1))
        self.assertEqual(end_date, date(2000, 9, 30))

    def test_calculate_judgment_period_subsequent_grants(self):
        """テストケース2-2: 2回目以降の判定期間"""
        user = User.objects.create(
            name="testuser_period2",
            email="period2@example.com",
            hire_date=date(2000, 4, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 2回目の判定期間
        start_date, end_date = calculator.calculate_judgment_period(2)
        self.assertEqual(start_date, date(2000, 10, 1))
        self.assertEqual(end_date, date(2001, 9, 30))

        # 3回目の判定期間
        start_date, end_date = calculator.calculate_judgment_period(3)
        self.assertEqual(start_date, date(2001, 10, 1))
        self.assertEqual(end_date, date(2002, 9, 30))

    def test_get_next_grant_info_before_first_grant(self):
        """テストケース3-1: 初回付与前の情報取得"""
        user = User.objects.create(
            name="testuser_next_info",
            email="nextinfo@example.com",
            hire_date=date(2024, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 基準日を設定
        reference_date = date(2024, 4, 1)

        # テスト用の出勤記録を作成（60日分）
        for i in range(60):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(reference_date - timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        next_info = calculator.get_next_grant_info(reference_date)

        self.assertEqual(next_info.next_grant_date, date(2024, 7, 1))
        self.assertEqual(next_info.days_until_grant, 91)
        self.assertEqual(next_info.current_attendance_days, 60)
        self.assertEqual(next_info.required_attendance_days, 104)  # 130日間の80%
        self.assertEqual(next_info.remaining_attendance_needed, 44)
        self.assertEqual(next_info.expected_grant_days, 10)

    def test_get_next_grant_info_before_second_grant(self):
        """テストケース3-2: 2回目付与前の情報取得"""
        user = User.objects.create(
            name="testuser_next_info2",
            email="nextinfo2@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=4,
        )
        calculator = PaidLeaveCalculator(user)

        # 基準日を設定
        reference_date = date(2024, 4, 1)

        # 1回目付与日からの出勤記録を作成（125日分）
        first_grant_date = calculator.calculate_grant_date(1)
        for i in range(125):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(first_grant_date + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        next_info = calculator.get_next_grant_info(reference_date)

        self.assertEqual(next_info.next_grant_date, date(2024, 7, 1))
        self.assertEqual(next_info.days_until_grant, 91)
        self.assertEqual(next_info.current_attendance_days, 125)
        self.assertEqual(next_info.required_attendance_days, 168)
        self.assertEqual(next_info.remaining_attendance_needed, 43)
        self.assertEqual(next_info.expected_grant_days, 8)

    def test_calculate_required_work_days_week5(self):
        """テストケース4-1: 週5日勤務の所定労働日数計算"""
        user = User.objects.create(
            name="testuser_work5",
            email="work5@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        required_days = calculator.calculate_required_work_days(
            date(2024, 1, 1), date(2024, 6, 30), 5
        )
        self.assertEqual(required_days, 130)

    def test_calculate_required_work_days_week3(self):
        """テストケース4-2: 週3日勤務の所定労働日数計算"""
        user = User.objects.create(
            name="testuser_work3",
            email="work3@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=3,
        )
        calculator = PaidLeaveCalculator(user)

        required_days = calculator.calculate_required_work_days(
            date(2023, 1, 1), date(2023, 6, 30), 3
        )
        self.assertEqual(required_days, 77)

    def test_calculate_required_work_days_one_year(self):
        """テストケース4-3: 1年間の所定労働日数計算"""
        user = User.objects.create(
            name="testuser_year",
            email="year@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=4,
        )
        calculator = PaidLeaveCalculator(user)

        required_days = calculator.calculate_required_work_days(
            date(2023, 7, 1), date(2024, 6, 30), 4
        )
        self.assertEqual(required_days, 209)

    def test_calculate_attendance_actual_work_only(self):
        """テストケース5-1: 実出勤のみの出勤日数計算"""
        user = User.objects.create(
            name="testuser_attend1",
            email="attend1@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 100件の出勤記録を作成
        for i in range(100):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2024, 1, 1) + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        attendance_days, attendance_rate = calculator.calculate_attendance(
            date(2024, 1, 1), date(2024, 6, 30)
        )
        self.assertEqual(attendance_days, 100)

    def test_calculate_attendance_with_paid_leave(self):
        """テストケース5-2: 有給使用を含む出勤日数計算"""
        user = User.objects.create(
            name="testuser_attend2",
            email="attend2@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 95件の出勤記録を作成
        for i in range(95):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2024, 1, 1) + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        # 5件の有給使用記録を作成
        for i in range(5):
            PaidLeaveRecord.objects.create(
                user=user,
                used_date=date(2024, 3, 1) + timedelta(days=i),
                days=1,
                record_type="use",
                grant_date=date(2023, 1, 1),
                expiry_date=date(2025, 1, 1),
            )

        attendance_days, attendance_rate = calculator.calculate_attendance(
            date(2024, 1, 1), date(2024, 6, 30)
        )
        self.assertEqual(attendance_days, 100)  # 95 + 5

    def test_calculate_attendance_80_percent_boundary(self):
        """テストケース5-3: 境界値（80%ちょうど）の出勤率計算"""
        user = User.objects.create(
            name="testuser_boundary",
            email="boundary@example.com",
            hire_date=date(2000, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 208件の出勤記録を作成（260日の80%）
        for i in range(208):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2023, 1, 1) + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        attendance_days, attendance_rate = calculator.calculate_attendance(
            date(2023, 1, 1), date(2023, 12, 31)
        )
        self.assertAlmostEqual(attendance_rate, 0.800, places=3)

    def test_calculate_attendance_error_handling(self):
        """テストケース5-4: エラーの処理"""
        with self.assertRaises(ValueError):
            self.calculator.calculate_attendance(date(2023, 1, 2), date(2023, 1, 1))

    def test_determine_grant_days_normal_worker(self):
        """テストケース7-1: 通常労働者の付与日数決定"""
        self.assertEqual(self.calculator.determine_grant_days(1, 5), 10)
        self.assertEqual(self.calculator.determine_grant_days(2, 5), 11)
        self.assertEqual(self.calculator.determine_grant_days(3, 5), 12)
        self.assertEqual(self.calculator.determine_grant_days(4, 5), 14)
        self.assertEqual(self.calculator.determine_grant_days(5, 5), 16)
        self.assertEqual(self.calculator.determine_grant_days(6, 5), 18)
        self.assertEqual(self.calculator.determine_grant_days(7, 5), 20)
        self.assertEqual(self.calculator.determine_grant_days(8, 5), 20)

    def test_determine_grant_days_week4(self):
        """テストケース7-2: 週4日勤務者の付与日数決定"""
        self.assertEqual(self.calculator.determine_grant_days(1, 4), 7)
        self.assertEqual(self.calculator.determine_grant_days(2, 4), 8)
        self.assertEqual(self.calculator.determine_grant_days(3, 4), 9)
        self.assertEqual(self.calculator.determine_grant_days(4, 4), 10)
        self.assertEqual(self.calculator.determine_grant_days(5, 4), 12)
        self.assertEqual(self.calculator.determine_grant_days(6, 4), 13)
        self.assertEqual(self.calculator.determine_grant_days(7, 4), 15)
        self.assertEqual(self.calculator.determine_grant_days(8, 4), 15)

    def test_determine_grant_days_week3(self):
        """テストケース7-3: 週3日勤務者の付与日数決定"""
        self.assertEqual(self.calculator.determine_grant_days(1, 3), 5)
        self.assertEqual(self.calculator.determine_grant_days(2, 3), 6)
        self.assertEqual(self.calculator.determine_grant_days(3, 3), 6)
        self.assertEqual(self.calculator.determine_grant_days(4, 3), 8)
        self.assertEqual(self.calculator.determine_grant_days(5, 3), 9)
        self.assertEqual(self.calculator.determine_grant_days(6, 3), 10)
        self.assertEqual(self.calculator.determine_grant_days(7, 3), 11)
        self.assertEqual(self.calculator.determine_grant_days(8, 3), 11)

    def test_determine_grant_days_week2(self):
        """テストケース7-4: 週2日勤務者の付与日数決定"""
        self.assertEqual(self.calculator.determine_grant_days(1, 2), 3)
        self.assertEqual(self.calculator.determine_grant_days(2, 2), 4)
        self.assertEqual(self.calculator.determine_grant_days(3, 2), 4)
        self.assertEqual(self.calculator.determine_grant_days(4, 2), 5)
        self.assertEqual(self.calculator.determine_grant_days(5, 2), 6)
        self.assertEqual(self.calculator.determine_grant_days(6, 2), 6)
        self.assertEqual(self.calculator.determine_grant_days(7, 2), 7)
        self.assertEqual(self.calculator.determine_grant_days(8, 2), 7)

    def test_determine_grant_days_week1(self):
        """テストケース7-5: 週1日勤務者の付与日数決定"""
        self.assertEqual(self.calculator.determine_grant_days(1, 1), 1)
        self.assertEqual(self.calculator.determine_grant_days(2, 1), 2)
        self.assertEqual(self.calculator.determine_grant_days(3, 1), 2)
        self.assertEqual(self.calculator.determine_grant_days(4, 1), 2)
        self.assertEqual(self.calculator.determine_grant_days(5, 1), 3)
        self.assertEqual(self.calculator.determine_grant_days(6, 1), 3)
        self.assertEqual(self.calculator.determine_grant_days(7, 1), 3)
        self.assertEqual(self.calculator.determine_grant_days(8, 1), 3)

    def test_judge_grant_eligibility_under_80_percent(self):
        """テストケース8-1: 出勤率80%未満での付与判定"""
        user = User.objects.create(
            name="testuser_judge1",
            email="judge1@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 90日の実出勤記録を作成
        for i in range(90):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2023, 1, 1) + timedelta(days=i * 2), datetime.min.time())),  # 期間内に分散
                clock_type="clock_in",
            )

        # 5日の有給使用記録を作成
        for i in range(5):
            PaidLeaveRecord.objects.create(
                user=user,
                used_date=date(2023, 3, 1) + timedelta(days=i),
                days=1,
                record_type="use",
                grant_date=date(2022, 1, 1),
                expiry_date=date(2024, 1, 1),
            )

        judgment = calculator.judge_grant_eligibility(1)

        self.assertEqual(judgment.grant_count, 1)
        self.assertEqual(judgment.judgment_date, date(2023, 7, 1))
        self.assertEqual(judgment.period_start, date(2023, 1, 1))
        self.assertEqual(judgment.period_end, date(2023, 6, 30))
        self.assertEqual(judgment.required_work_days, 129)
        self.assertEqual(judgment.attendance_days, 95)
        self.assertAlmostEqual(judgment.attendance_rate, 0.7364, places=3)
        self.assertFalse(judgment.is_eligible)
        self.assertEqual(judgment.grant_days, 0)
        self.assertEqual(judgment.description, "出勤率が80%未満のため付与なし")

    def test_judge_grant_eligibility_over_80_percent(self):
        """テストケース8-2: 出勤率80%以上での付与判定"""
        user = User.objects.create(
            name="testuser_judge2",
            email="judge2@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 100日の実出勤記録を作成
        for i in range(100):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2023, 1, 1) + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        # 5日の有給使用記録を作成
        for i in range(5):
            PaidLeaveRecord.objects.create(
                user=user,
                used_date=date(2023, 4, 1) + timedelta(days=i),
                days=1,
                record_type="use",
                grant_date=date(2022, 1, 1),
                expiry_date=date(2024, 1, 1),
            )

        judgment = calculator.judge_grant_eligibility(1)

        self.assertEqual(judgment.grant_count, 1)
        self.assertEqual(judgment.judgment_date, date(2023, 7, 1))
        self.assertEqual(judgment.period_start, date(2023, 1, 1))
        self.assertEqual(judgment.period_end, date(2023, 6, 30))
        self.assertEqual(judgment.required_work_days, 129)
        self.assertEqual(judgment.attendance_days, 105)
        self.assertAlmostEqual(judgment.attendance_rate, 0.8139, places=3)
        self.assertTrue(judgment.is_eligible)
        self.assertEqual(judgment.grant_days, 10)
        self.assertEqual(judgment.expiry_date, date(2025, 7, 1))
        self.assertEqual(judgment.description, "付与条件を満たしています")

    def test_judge_grant_eligibility_exactly_80_percent(self):
        """テストケース8-3: 境界値（出勤率ちょうど80%）での付与判定"""
        user = User.objects.create(
            name="testuser_judge3",
            email="judge3@example.com",
            hire_date=date(2024, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 103日の実出勤記録を作成
        for i in range(103):
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(date(2024, 1, 1) + timedelta(days=i), datetime.min.time())),
                clock_type="clock_in",
            )

        # 1日の有給使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user, 
            used_date=date(2024, 4, 1), 
            days=1, 
            record_type="use",
            grant_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1),
        )

        judgment = calculator.judge_grant_eligibility(1)

        self.assertEqual(judgment.grant_count, 1)
        self.assertEqual(judgment.judgment_date, date(2024, 7, 1))
        self.assertEqual(judgment.period_start, date(2024, 1, 1))
        self.assertEqual(judgment.period_end, date(2024, 6, 30))
        self.assertEqual(judgment.required_work_days, 130)
        self.assertEqual(judgment.attendance_days, 104)
        self.assertAlmostEqual(judgment.attendance_rate, 0.8000, places=3)
        self.assertTrue(judgment.is_eligible)
        self.assertEqual(judgment.grant_days, 10)
        self.assertEqual(judgment.expiry_date, date(2026, 7, 1))
        self.assertEqual(judgment.description, "付与条件を満たしています")

    def test_should_rejudge_required(self):
        """テストケース9-1: 直近付与日より前の記録修正"""
        user = User.objects.create(
            name="testuser_rejudge1",
            email="rejudge1@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        result = calculator.should_rejudge(date(2020, 6, 30), date(2020, 7, 2))
        self.assertTrue(result)

    def test_should_rejudge_not_required(self):
        """テストケース9-2: 直近付与日以降の記録修正"""
        user = User.objects.create(
            name="testuser_rejudge2",
            email="rejudge2@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        result = calculator.should_rejudge(date(2020, 7, 1), date(2020, 7, 2))
        self.assertFalse(result)

    def test_should_rejudge_same_day(self):
        """テストケース9-3: 付与日当日の記録修正"""
        user = User.objects.create(
            name="testuser_rejudge3",
            email="rejudge3@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        result = calculator.should_rejudge(date(2020, 7, 1), date(2020, 7, 1))
        self.assertFalse(result)

    def test_find_affected_grants_single(self):
        """テストケース10-1: 単一の付与回に影響"""
        user = User.objects.create(
            name="testuser_affected",
            email="affected@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        affected_grant = calculator.find_affected_grants(date(2020, 6, 15))
        self.assertEqual(affected_grant, 1)

    def test_find_affected_grants_second(self):
        """テストケース10-2: 2回目の付与回に影響"""
        user = User.objects.create(
            name="testuser_affected2",
            email="affected2@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        affected_grant = calculator.find_affected_grants(date(2021, 6, 15))
        self.assertEqual(affected_grant, 2)

    def test_find_affected_grants_none(self):
        """テストケース10-3: 影響なしの場合"""
        user = User.objects.create(
            name="testuser_affected3",
            email="affected3@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        calculator = PaidLeaveCalculator(user)

        # 入社前の日付（影響なし）
        affected_grant = calculator.find_affected_grants(date(2019, 12, 15))
        self.assertIsNone(affected_grant)

    def test_calculate_expiry_date_normal(self):
        """テストケース11-1: 通常日付の有効期限計算"""
        expiry_date = self.calculator.calculate_expiry_date(date(2024, 7, 1))
        self.assertEqual(expiry_date, date(2026, 7, 1))

    def test_calculate_expiry_date_leap_year(self):
        """テストケース11-2: 閏年2月29日の有効期限計算"""
        expiry_date = self.calculator.calculate_expiry_date(date(2024, 2, 29))
        self.assertEqual(expiry_date, date(2026, 2, 28))

    def test_calculate_expiry_date_month_end(self):
        """テストケース11-3: 月末日の有効期限計算"""
        expiry_date = self.calculator.calculate_expiry_date(date(2023, 1, 31))
        self.assertEqual(expiry_date, date(2025, 1, 31))
