"""
PaidLeaveGrantProcessorクラスのテストモジュール
"""

from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from timeclock.services.paid_leave_grant_processor import PaidLeaveGrantProcessor
from timeclock.services.paid_leave_calculator import PaidLeaveJudgment
from timeclock.models import PaidLeaveRecord

User = get_user_model()


class TestPaidLeaveGrantProcessor(TestCase):
    """PaidLeaveGrantProcessorのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.user = User.objects.create(
            name="testuser",
            email="test@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=0
        )
        self.processor = PaidLeaveGrantProcessor(self.user)

    def test_execute_grant_normal(self):
        """テストケース1-1: 通常の付与処理実行"""
        # PaidLeaveJudgmentオブジェクトを作成
        judgment = PaidLeaveJudgment(
            grant_count=1,
            judgment_date=date(2023, 7, 1),
            period_start=date(2023, 1, 1),
            period_end=date(2023, 6, 30),
            required_work_days=100,
            attendance_days=85,
            attendance_rate=0.85,
            is_eligible=True,
            grant_days=10,
            expiry_date=date(2025, 7, 1),
            description="付与条件を満たしています"
        )

        # 付与処理を実行
        result = self.processor.execute_grant(judgment)

        # 検証
        self.assertIsNotNone(result)
        self.assertEqual(result.user, self.user)
        self.assertEqual(result.record_type, 'grant')
        self.assertEqual(result.grant_date, date(2023, 7, 1))
        self.assertEqual(result.days, 10)
        self.assertEqual(result.expiry_date, date(2025, 7, 1))
        self.assertEqual(result.description, "付与条件を満たしています")
        
        # user.current_paid_leaveが更新されていることを確認
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_paid_leave, 10)

    def test_execute_grant_ineligible(self):
        """テストケース1-2: 付与不可判定時の処理"""
        # PaidLeaveJudgmentオブジェクトを作成（付与不可）
        judgment = PaidLeaveJudgment(
            grant_count=1,
            judgment_date=date(2023, 7, 1),
            period_start=date(2023, 1, 1),
            period_end=date(2023, 6, 30),
            required_work_days=100,
            attendance_days=75,
            attendance_rate=0.75,
            is_eligible=False,
            grant_days=0,
            expiry_date=date(2025, 7, 1),
            description="出勤率が80%未満のため付与なし"
        )

        # 付与処理を実行
        result = self.processor.execute_grant(judgment)

        # 検証
        self.assertIsNone(result)
        
        # PaidLeaveRecordが作成されていないことを確認
        self.assertFalse(PaidLeaveRecord.objects.filter(user=self.user, record_type='grant').exists())
        
        # user.current_paid_leaveが変更されていないことを確認
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_paid_leave, 0)

    def test_execute_grant_second_time(self):
        """テストケース1-3: 2回目以降の付与処理"""
        user = User.objects.create(
            name="testuser2",
            email="test2@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=7
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        # 使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )

        # 2回目の付与判定を作成
        judgment = PaidLeaveJudgment(
            grant_count=2,
            judgment_date=date(2023, 7, 1),
            period_start=date(2022, 7, 1),
            period_end=date(2023, 6, 30),
            required_work_days=100,
            attendance_days=85,
            attendance_rate=0.85,
            is_eligible=True,
            grant_days=11,
            expiry_date=date(2025, 7, 1),
            description="付与条件を満たしています"
        )

        # 付与処理を実行
        result = processor.execute_grant(judgment)

        # 検証
        self.assertIsNotNone(result)
        self.assertEqual(result.grant_date, date(2023, 7, 1))
        self.assertEqual(result.days, 11)
        self.assertEqual(result.expiry_date, date(2025, 7, 1))
        
        # user.current_paid_leaveが更新されていることを確認（7+11=18）
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 18)

    def test_execute_grant_part_time_worker(self):
        """テストケース1-4: パートタイム労働者の付与処理"""
        user = User.objects.create(
            name="testuser3",
            email="test3@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=3,
            current_paid_leave=0
        )
        processor = PaidLeaveGrantProcessor(user)

        # パートタイム労働者の付与判定を作成
        judgment = PaidLeaveJudgment(
            grant_count=1,
            judgment_date=date(2023, 7, 1),
            period_start=date(2023, 1, 1),
            period_end=date(2023, 6, 30),
            required_work_days=60,
            attendance_days=50,
            attendance_rate=0.83,
            is_eligible=True,
            grant_days=5,
            expiry_date=date(2025, 7, 1),
            description="付与条件を満たしています"
        )

        # 付与処理を実行
        result = processor.execute_grant(judgment)

        # 検証
        self.assertIsNotNone(result)
        self.assertEqual(result.days, 5)
        self.assertEqual(result.grant_date, date(2023, 7, 1))
        self.assertEqual(result.expiry_date, date(2025, 7, 1))
        
        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 5)

    def test_execute_cancellation_normal(self):
        """テストケース2-1: 通常の取消処理実行"""
        user = User.objects.create(
            name="testuser4",
            email="test4@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )

        # 取消処理を実行
        result = processor.execute_cancellation(
            grant_date=date(2022, 7, 1),
            cancellation_date=date(2022, 8, 1),
            description="再判定により出勤率不足のため"
        )

        # 検証
        self.assertIsNotNone(result)
        self.assertEqual(result.grant_date, date(2022, 7, 1))
        self.assertEqual(result.target_cancel_days, 10)
        self.assertEqual(result.actual_cancelled_days, 10)
        self.assertEqual(result.remaining_balance, 0)
        self.assertEqual(result.was_partial, False)
        self.assertEqual(result.cancellation_date, date(2022, 8, 1))
        self.assertEqual(result.description, "再判定により出勤率不足のため")

        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 10)
        self.assertEqual(cancel_record.cancellation_date, date(2022, 8, 1))
        self.assertEqual(cancel_record.description, "再判定により出勤率不足のため")

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_execute_cancellation_partial(self):
        """テストケース2-2: 部分取消処理の実行"""
        user = User.objects.create(
            name="testuser5",
            email="test5@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=5
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        # 使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=5,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )

        # 取消処理を実行
        result = processor.execute_cancellation(
            grant_date=date(2022, 7, 1),
            cancellation_date=date(2022, 9, 1),
            description="再判定により"
        )

        # 検証
        self.assertEqual(result.grant_date, date(2022, 7, 1))
        self.assertEqual(result.target_cancel_days, 10)
        self.assertEqual(result.actual_cancelled_days, 5)
        self.assertEqual(result.remaining_balance, 0)
        self.assertEqual(result.was_partial, True)
        self.assertEqual(result.cancellation_date, date(2022, 9, 1))

        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 5)  # 実際に取り消された日数

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_execute_cancellation_insufficient_balance(self):
        """テストケース2-3: 残日数不足時の部分取消処理"""
        user = User.objects.create(
            name="testuser6",
            email="test6@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=3
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        # 使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=7,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )

        # 取消処理を実行
        result = processor.execute_cancellation(
            grant_date=date(2022, 7, 1),
            cancellation_date=date(2022, 9, 1),
            description="再判定により"
        )

        # 検証
        self.assertEqual(result.grant_date, date(2022, 7, 1))
        self.assertEqual(result.target_cancel_days, 10)
        self.assertEqual(result.actual_cancelled_days, 3)
        self.assertEqual(result.remaining_balance, 0)
        self.assertEqual(result.was_partial, True)

        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 3)

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_execute_cancellation_all_used(self):
        """テストケース2-4: 既に全て使用済みの有給の取消処理"""
        user = User.objects.create(
            name="testuser7",
            email="test7@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=0
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        # 使用記録を作成（全て使用済み）
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=10,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )

        # 取消処理を実行
        result = processor.execute_cancellation(
            grant_date=date(2022, 7, 1),
            cancellation_date=date(2022, 9, 1),
            description="再判定により"
        )

        # 検証
        self.assertEqual(result.grant_date, date(2022, 7, 1))
        self.assertEqual(result.target_cancel_days, 10)
        self.assertEqual(result.actual_cancelled_days, 0)
        self.assertEqual(result.remaining_balance, 0)
        self.assertEqual(result.was_partial, True)

        # 取消記録が作成されていないことを確認
        self.assertFalse(PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).exists())

        # user.current_paid_leaveが変更されていないことを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_execute_cancellation_multiple_grants(self):
        """テストケース2-5: 複数年度の付与がある場合の特定回取消"""
        user = User.objects.create(
            name="testuser8",
            email="test8@example.com",
            hire_date=date(2021, 1, 1),
            weekly_work_days=5,
            current_paid_leave=18
        )
        processor = PaidLeaveGrantProcessor(user)

        # 1回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2023, 7, 1)
        )
        # 1回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            used_date=date(2021, 8, 1),
            days=2,
            record_type='use',
            expiry_date=date(2023, 7, 1)
        )
        # 2回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        # 2回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=1,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )

        # 1回目のみの取消処理を実行
        result = processor.execute_cancellation(
            grant_date=date(2021, 7, 1),
            cancellation_date=date(2022, 9, 1),
            description="再判定により"
        )

        # 検証
        self.assertEqual(result.grant_date, date(2021, 7, 1))
        self.assertEqual(result.target_cancel_days, 10)
        self.assertEqual(result.actual_cancelled_days, 8)  # 10-2
        self.assertEqual(result.remaining_balance, 10)  # 18-8
        self.assertEqual(result.was_partial, True)

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)

    def test_process_expiration_single(self):
        """テストケース3-1: 単一の時効処理"""
        user = User.objects.create(
            name="testuser9",
            email="test9@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
            current_paid_leave=8
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        # 使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2020, 8, 1),
            days=2,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )

        # 時効処理を実行
        result = processor.process_expiration(date(2022, 7, 1))

        # 検証
        self.assertEqual(len(result), 1)
        expire_record = result[0]
        self.assertEqual(expire_record.record_type, 'expire')
        self.assertEqual(expire_record.grant_date, date(2020, 7, 1))
        self.assertEqual(expire_record.days, 8)  # 10-2
        self.assertEqual(expire_record.expiry_date, date(2022, 7, 1))
        self.assertEqual(expire_record.description, "有効期限による時効消滅")

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_process_expiration_multiple(self):
        """テストケース3-2: 複数の時効処理"""
        user = User.objects.create(
            name="testuser10",
            email="test10@example.com",
            hire_date=date(2019, 1, 1),
            weekly_work_days=5,
            current_paid_leave=17
        )
        processor = PaidLeaveGrantProcessor(user)

        # 1回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2019, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2021, 7, 1)
        )
        # 1回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2019, 7, 1),
            used_date=date(2019, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2021, 7, 1)
        )
        # 2回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        # 2回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2020, 8, 1),
            days=1,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )

        # 時効処理を実行（2022年7月1日）
        result = processor.process_expiration(date(2022, 7, 1))

        # 検証
        self.assertEqual(len(result), 2)
        
        # 1回目の時効記録を確認
        expire_record_1 = next((r for r in result if r.grant_date == date(2019, 7, 1)), None)
        self.assertIsNotNone(expire_record_1)
        self.assertEqual(expire_record_1.days, 7)  # 10-3
        
        # 2回目の時効記録を確認
        expire_record_2 = next((r for r in result if r.grant_date == date(2020, 7, 1)), None)
        self.assertIsNotNone(expire_record_2)
        self.assertEqual(expire_record_2.days, 10)  # 11-1

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)  # 17日分が時効

    def test_process_expiration_no_target(self):
        """テストケース3-3: 時効対象がない場合の処理"""
        user = User.objects.create(
            name="testuser11",
            email="test11@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成（まだ有効期限内）
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )

        # 時効処理を実行（まだ有効期限前）
        result = processor.process_expiration(date(2023, 7, 1))

        # 検証
        self.assertEqual(len(result), 0)

        # 時効記録が作成されていないことを確認
        self.assertFalse(PaidLeaveRecord.objects.filter(
            user=user,
            record_type='expire'
        ).exists())

        # user.current_paid_leaveが変更されていないことを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)

    def test_process_expiration_partial_used(self):
        """テストケース3-4: 部分的に使用済みの有給の時効処理"""
        user = User.objects.create(
            name="testuser12",
            email="test12@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
            current_paid_leave=4
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        # 使用記録を作成（複数回に分けて使用）
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2020, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2021, 1, 1),
            days=3,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )

        # 時効処理を実行
        result = processor.process_expiration(date(2022, 7, 1))

        # 検証
        self.assertEqual(len(result), 1)
        expire_record = result[0]
        self.assertEqual(expire_record.record_type, 'expire')
        self.assertEqual(expire_record.days, 4)  # 10-6

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_process_expiration_all_used(self):
        """テストケース3-5: 既に全て使用済みの有給の時効処理"""
        user = User.objects.create(
            name="testuser13",
            email="test13@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
            current_paid_leave=0
        )
        processor = PaidLeaveGrantProcessor(user)

        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        # 使用記録を作成（全て使用済み）
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2021, 1, 1),
            days=10,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )

        # 時効処理を実行
        result = processor.process_expiration(date(2022, 7, 1))

        # 検証
        self.assertEqual(len(result), 0)

        # 時効記録が作成されていないことを確認
        self.assertFalse(PaidLeaveRecord.objects.filter(
            user=user,
            record_type='expire'
        ).exists())

        # user.current_paid_leaveが変更されていないことを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 0)

    def test_process_expiration_partial_multiple_years(self):
        """テストケース3-6: 複数年度で一部のみ時効の場合"""
        user = User.objects.create(
            name="testuser14",
            email="test14@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
            current_paid_leave=0
        )
        processor = PaidLeaveGrantProcessor(user)

        # 1回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        # 1回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2020, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )
        # 2回目の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2023, 7, 1)
        )
        # 2回目の使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            used_date=date(2021, 8, 1),
            days=2,
            record_type='use',
            expiry_date=date(2023, 7, 1)
        )

        # 時効処理を実行（2022年7月1日）
        result = processor.process_expiration(date(2022, 7, 1))

        # 検証
        self.assertEqual(len(result), 1)  # 2020年付与分のみ時効
        expire_record = result[0]
        self.assertEqual(expire_record.grant_date, date(2020, 7, 1))
        self.assertEqual(expire_record.days, 7)  # 10-3

        # user.current_paid_leaveが更新されていることを確認
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 9)  # 16-7