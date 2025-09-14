"""
PaidLeaveBalanceManagerクラスのテストモジュール
"""

from datetime import date, datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from timeclock.services.paid_leave_balance_manager import PaidLeaveBalanceManager, DetailedBalanceInfo, GrantDateBalance
from timeclock.models import PaidLeaveRecord

User = get_user_model()


class TestPaidLeaveBalanceManager(TestCase):
    """PaidLeaveBalanceManagerのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.user = User.objects.create(
            name="testuser",
            email="test@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
        )
        self.manager = PaidLeaveBalanceManager(self.user)

    def test_get_current_balance_only_grants(self):
        """テストケース1-1: 付与記録のみの残日数計算"""
        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=self.user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=self.user,
            grant_date=date(2024, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2026, 7, 1)
        )

        # 残日数を計算
        balance = self.manager.get_current_balance()
        
        # 検証: 10 + 11 = 21日
        self.assertEqual(balance, 21)

    def test_get_current_balance_with_usage(self):
        """テストケース1-2: 付与と使用記録混在時の残日数計算"""
        user = User.objects.create(
            name="testuser2",
            email="test2@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与と使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 15),
            days=3,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            used_date=date(2023, 9, 10),
            days=2,
            record_type='use',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を計算
        balance = manager.get_current_balance()
        
        # 検証: 10 - 3 + 11 - 2 = 16日
        self.assertEqual(balance, 16)

    def test_get_current_balance_with_expiry(self):
        """テストケース1-3: 時効記録を含む残日数計算"""
        user = User.objects.create(
            name="testuser3",
            email="test3@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与、使用、時効記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            used_date=date(2020, 8, 1),
            days=2,
            record_type='use',
            expiry_date=date(2022, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            expiry_date=date(2022, 7, 1),
            days=8,
            record_type='expire',
            used_date=date(2022, 7, 1)  # 時効発生日
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            used_date=date(2021, 8, 1),
            days=1,
            record_type='use',
            expiry_date=date(2023, 7, 1)
        )

        # 残日数を計算
        balance = manager.get_current_balance()
        
        # 検証: 10 - 2 - 8 + 11 - 1 = 10日
        self.assertEqual(balance, 10)

    def test_get_current_balance_with_cancellation(self):
        """テストケース1-4: 取消記録を含む残日数計算"""
        user = User.objects.create(
            name="testuser4",
            email="test4@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与と取消記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            cancellation_date=date(2023, 8, 1),
            days=5,
            record_type='cancel',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を計算
        balance = manager.get_current_balance()
        
        # 検証: 10 - 5 = 5日
        self.assertEqual(balance, 5)

    def test_get_current_balance_complex(self):
        """テストケース1-5: 複雑な記録混在時の残日数計算"""
        user = User.objects.create(
            name="testuser5",
            email="test5@example.com",
            hire_date=date(2021, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 全種類の記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            used_date=date(2021, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 9, 1),
            days=2,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            expiry_date=date(2023, 7, 1),
            days=5,
            record_type='expire',
            used_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=12,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            cancellation_date=date(2023, 8, 1),
            days=3,
            record_type='cancel',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を計算
        balance = manager.get_current_balance()
        
        # 検証: 10 - 3 + 11 - 2 - 5 + 12 - 3 = 20日
        self.assertEqual(balance, 20)

    def test_get_detailed_balance_info_single_year(self):
        """テストケース2-1: 単一年度の詳細残日数情報取得"""
        user = User.objects.create(
            name="testuser6",
            email="test6@example.com",
            hire_date=date(2024, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与と使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2024, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2026, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2024, 7, 1),
            used_date=date(2024, 8, 15),
            days=2,
            record_type='use',
            expiry_date=date(2026, 7, 1)
        )

        # 基準日を2024年9月1日として詳細情報を取得
        detailed_info = manager.get_detailed_balance_info()
        
        # 検証
        self.assertEqual(detailed_info.total_balance, 8)
        self.assertEqual(len(detailed_info.balance_by_grant_date), 1)
        
        balance_info = detailed_info.balance_by_grant_date[0]
        self.assertEqual(balance_info.grant_date, date(2024, 7, 1))
        self.assertEqual(balance_info.original_days, 10)
        self.assertEqual(balance_info.used_days, 2)
        self.assertEqual(balance_info.remaining_days, 8)
        self.assertEqual(balance_info.expiry_date, date(2026, 7, 1))

    def test_get_detailed_balance_info_multiple_years(self):
        """テストケース2-2: 複数年度の詳細残日数情報取得"""
        user = User.objects.create(
            name="testuser7",
            email="test7@example.com",
            hire_date=date(2022, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 複数年度の記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            used_date=date(2022, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2024, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            used_date=date(2023, 9, 1),
            days=2,
            record_type='use',
            expiry_date=date(2025, 7, 1)
        )

        # 詳細情報を取得
        detailed_info = manager.get_detailed_balance_info()
        
        # 検証
        self.assertEqual(detailed_info.total_balance, 16)
        self.assertEqual(len(detailed_info.balance_by_grant_date), 2)
        
        # 時効が近い順に並んでいることを確認
        self.assertEqual(detailed_info.balance_by_grant_date[0].grant_date, date(2022, 7, 1))
        self.assertEqual(detailed_info.balance_by_grant_date[1].grant_date, date(2023, 7, 1))

    def test_get_detailed_balance_info_with_expiry(self):
        """テストケース2-3: 一部使用済み・時効済みを含む詳細情報取得"""
        user = User.objects.create(
            name="testuser8",
            email="test8@example.com",
            hire_date=date(2020, 1, 1),
            weekly_work_days=5,
        )
        manager = PaidLeaveBalanceManager(user)

        # 複雑な使用履歴を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2020, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2022, 7, 1)
        )
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
            expiry_date=date(2022, 7, 1),
            days=7,
            record_type='expire',
            used_date=date(2022, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            days=11,
            record_type='grant',
            expiry_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2021, 7, 1),
            used_date=date(2022, 1, 1),
            days=5,
            record_type='use',
            expiry_date=date(2023, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2022, 7, 1),
            days=12,
            record_type='grant',
            expiry_date=date(2024, 7, 1)
        )

        # 詳細情報を取得
        detailed_info = manager.get_detailed_balance_info()
        
        # 検証
        self.assertEqual(detailed_info.total_balance, 18)  # 0 + 6 + 12
        self.assertEqual(len(detailed_info.balance_by_grant_date), 3)
        
        # 各年度の残日数を確認
        for balance in detailed_info.balance_by_grant_date:
            if balance.grant_date == date(2020, 7, 1):
                self.assertEqual(balance.remaining_days, 0)  # 全て時効
            elif balance.grant_date == date(2021, 7, 1):
                self.assertEqual(balance.remaining_days, 6)  # 11 - 5
            elif balance.grant_date == date(2022, 7, 1):
                self.assertEqual(balance.remaining_days, 12)  # 未使用

    def test_update_user_balance_normal(self):
        """テストケース3-1: 通常のuser.current_paid_leave更新"""
        user = User.objects.create(
            name="testuser9",
            email="test9@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=0
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を更新
        updated_balance = manager.update_user_balance()
        
        # 検証
        self.assertEqual(updated_balance, 10)
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)

    def test_update_user_balance_with_change(self):
        """テストケース3-2: 残日数変更時の更新確認"""
        user = User.objects.create(
            name="testuser10",
            email="test10@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与と使用記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            used_date=date(2023, 8, 1),
            days=3,
            record_type='use',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を更新
        updated_balance = manager.update_user_balance()
        
        # 検証
        self.assertEqual(updated_balance, 7)
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 7)

    def test_update_user_balance_no_change(self):
        """テストケース3-3: 残日数変更なしの場合の処理確認"""
        user = User.objects.create(
            name="testuser11",
            email="test11@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を更新
        updated_balance = manager.update_user_balance()
        
        # 検証
        self.assertEqual(updated_balance, 10)
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)

    def test_calculate_partial_cancellation_within_balance(self):
        """テストケース4-1: 残日数内での部分取消計算"""
        user = User.objects.create(
            name="testuser12",
            email="test12@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # 部分取消を実行
        actual_cancelled, remaining = manager.calculate_partial_cancellation(
            target_cancel_days=5,
            target_date=date(2023, 8, 1)
        )
        
        # 検証
        self.assertEqual(actual_cancelled, 5)
        self.assertEqual(remaining, 5)
        
        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 5)
        self.assertEqual(cancel_record.grant_date, date(2023, 7, 1))
        self.assertEqual(cancel_record.cancellation_date, date(2023, 8, 1))

    def test_calculate_partial_cancellation_exceeds_balance(self):
        """テストケース4-2: 残日数を超える取消要求時の計算"""
        user = User.objects.create(
            name="testuser13",
            email="test13@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # 残日数を超える取消を要求
        actual_cancelled, remaining = manager.calculate_partial_cancellation(
            target_cancel_days=15,
            target_date=date(2023, 8, 1)
        )
        
        # 検証
        self.assertEqual(actual_cancelled, 10)
        self.assertEqual(remaining, 0)
        
        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 10)

    def test_calculate_partial_cancellation_exact_balance(self):
        """テストケース4-3: 残日数がちょうど0になる場合"""
        user = User.objects.create(
            name="testuser14",
            email="test14@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=8
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=8,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # ちょうど残日数分の取消
        actual_cancelled, remaining = manager.calculate_partial_cancellation(
            target_cancel_days=8,
            target_date=date(2023, 8, 1)
        )
        
        # 検証
        self.assertEqual(actual_cancelled, 8)
        self.assertEqual(remaining, 0)
        
        # 取消記録が作成されていることを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).first()
        self.assertIsNotNone(cancel_record)
        self.assertEqual(cancel_record.days, 8)

    def test_calculate_partial_cancellation_zero_days(self):
        """テストケース4-5: 取消要求が0日の場合"""
        user = User.objects.create(
            name="testuser15",
            email="test15@example.com",
            hire_date=date(2023, 1, 1),
            weekly_work_days=5,
            current_paid_leave=10
        )
        manager = PaidLeaveBalanceManager(user)

        # 付与記録を作成
        PaidLeaveRecord.objects.create(
            user=user,
            grant_date=date(2023, 7, 1),
            days=10,
            record_type='grant',
            expiry_date=date(2025, 7, 1)
        )

        # 0日の取消要求
        actual_cancelled, remaining = manager.calculate_partial_cancellation(
            target_cancel_days=0,
            target_date=date(2023, 8, 1)
        )
        
        # 検証
        self.assertEqual(actual_cancelled, 0)
        self.assertEqual(remaining, 10)
        
        # 取消記録が作成されていないことを確認
        cancel_record = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='cancel'
        ).exists()
        self.assertFalse(cancel_record)