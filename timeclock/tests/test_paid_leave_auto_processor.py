"""
PaidLeaveAutoProcessorクラスのテストモジュール

テスト仕様書 PAID_LEAVE_AUTO_PROCESSOR_TEST.md に基づいて実装
"""

from datetime import date, datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
import time

from timeclock.services.paid_leave_auto_processor import PaidLeaveAutoProcessor
from timeclock.services.paid_leave_calculator import PaidLeaveJudgment
from timeclock.models import TimeRecord, PaidLeaveRecord

User = get_user_model()


class TestPaidLeaveAutoProcessor(TestCase):
    """PaidLeaveAutoProcessorのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.processor = PaidLeaveAutoProcessor()
        
    def _create_user_with_schedule(self, hire_date, weekly_work_days=5, name_suffix=""):
        """付与スケジュール付きのユーザーを作成"""
        user = User.objects.create(
            name=f"testuser{name_suffix}",
            email=f"test{name_suffix}@example.com",
            hire_date=hire_date,
            weekly_work_days=weekly_work_days,
            current_paid_leave=0,
        )
        # paid_leave_grant_scheduleはsaveメソッドで自動計算される
        user.refresh_from_db()
        return user
    
    def _create_time_records_for_attendance(self, user, start_date, days_count):
        """指定日数分の出勤記録を作成"""
        for i in range(days_count):
            record_date = start_date + timedelta(days=i)
            TimeRecord.objects.create(
                user=user,
                timestamp=timezone.make_aware(datetime.combine(record_date, datetime.min.time())),
                clock_type="clock_in",
            )

    # === 1. 日次付与処理メソッド（process_daily_grants_and_expirations）のテスト ===
    
    def test_process_daily_grants_with_eligible_user(self):
        """テストケース1-1: 付与対象ユーザーが存在する場合の日次処理"""
        target_date = date(2023, 7, 1)
        
        # ユーザー1: 入社日2023年1月1日（1回目付与対象）
        user1 = self._create_user_with_schedule(date(2023, 1, 1), name_suffix="1")
        
        # 十分な出勤記録を作成（80%以上の出勤率）
        self._create_time_records_for_attendance(user1, date(2023, 1, 1), 150)
        
        # 日次処理を実行
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証
        self.assertEqual(len(judgments), 1)
        judgment = judgments[0]
        self.assertTrue(judgment.is_eligible)
        self.assertEqual(judgment.grant_days, 10)
        self.assertEqual(judgment.judgment_date, target_date)
        
        # PaidLeaveRecordが作成されていることを確認
        paid_leave_records = PaidLeaveRecord.objects.filter(
            user=user1, 
            record_type='grant',
            grant_date=target_date
        )
        self.assertEqual(paid_leave_records.count(), 1)
        self.assertEqual(paid_leave_records.first().days, 10)
        
        # ユーザーの残日数が更新されていることを確認
        user1.refresh_from_db()
        self.assertEqual(user1.current_paid_leave, 10)

    def test_process_daily_grants_no_eligible_users(self):
        """テストケース1-2: 付与対象ユーザーが存在しない場合の日次処理"""
        target_date = date(2023, 7, 1)
        
        # ユーザー1: 入社日2023年2月1日（付与対象外）
        user1 = self._create_user_with_schedule(date(2023, 2, 1), name_suffix="1")
        
        # 日次処理を実行
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証
        self.assertEqual(len(judgments), 0)
        
        # PaidLeaveRecordが作成されていないことを確認
        paid_leave_records = PaidLeaveRecord.objects.filter(
            user=user1, 
            record_type='grant'
        )
        self.assertEqual(paid_leave_records.count(), 0)

    def test_process_daily_grants_multiple_users(self):
        """テストケース1-3: 複数ユーザーの同時処理"""
        target_date = date(2023, 7, 1)
        
        # ユーザー1: 入社日2023年1月1日（1回目付与）
        user1 = self._create_user_with_schedule(date(2023, 1, 1), name_suffix="1")
        self._create_time_records_for_attendance(user1, date(2023, 1, 1), 150)
        
        # ユーザー2: 入社日2022年1月1日（2回目付与）
        user2 = self._create_user_with_schedule(date(2022, 1, 1), name_suffix="2")
        self._create_time_records_for_attendance(user2, date(2022, 7, 1), 300)
        
        # ユーザー3: 入社日2022年8月1日（対象外）
        user3 = self._create_user_with_schedule(date(2022, 8, 1), name_suffix="3")
        
        # 日次処理を実行
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証
        self.assertEqual(len(judgments), 2)
        
        # ユーザー1の判定結果確認
        user1_judgment = next(j for j in judgments if j.grant_count == 1)
        self.assertTrue(user1_judgment.is_eligible)
        self.assertEqual(user1_judgment.grant_days, 10)
        
        # ユーザー2の判定結果確認
        user2_judgment = next(j for j in judgments if j.grant_count == 2)
        self.assertTrue(user2_judgment.is_eligible)
        self.assertEqual(user2_judgment.grant_days, 11)
        
        # ユーザー3は対象外であることを確認
        user3_records = PaidLeaveRecord.objects.filter(user=user3, record_type='grant')
        self.assertEqual(user3_records.count(), 0)

    def test_process_daily_grants_mixed_eligibility(self):
        """テストケース1-4: 付与条件を満たすユーザー・満たさないユーザー混在時の処理"""
        target_date = date(2023, 7, 1)
        
        # ユーザー1: 出勤率85%（条件満たす）
        user1 = self._create_user_with_schedule(date(2023, 1, 1), name_suffix="1")
        self._create_time_records_for_attendance(user1, date(2023, 1, 1), 110)  # 85%相当
        
        # ユーザー2: 出勤率75%（条件満たさない）
        user2 = self._create_user_with_schedule(date(2023, 1, 1), name_suffix="2")
        self._create_time_records_for_attendance(user2, date(2023, 1, 1), 97)   # 75%相当
        
        # 日次処理を実行
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証
        self.assertEqual(len(judgments), 2)
        
        # 判定結果を整理
        eligible_judgment = next((j for j in judgments if j.is_eligible), None)
        ineligible_judgment = next((j for j in judgments if not j.is_eligible), None)
        
        self.assertIsNotNone(eligible_judgment)
        self.assertIsNotNone(ineligible_judgment)
        
        self.assertEqual(eligible_judgment.grant_days, 10)
        self.assertEqual(ineligible_judgment.grant_days, 0)

    def test_process_daily_grants_with_expiration(self):
        """テストケース1-5: 時効処理も同時実行されることの確認"""
        target_date = date(2023, 7, 1)
        
        # ユーザー1: 新規付与対象
        user1 = self._create_user_with_schedule(date(2023, 1, 1), name_suffix="1")
        self._create_time_records_for_attendance(user1, date(2023, 1, 1), 150)
        
        # ユーザー2: 時効対象の有給あり
        user2 = self._create_user_with_schedule(date(2021, 1, 1), name_suffix="2")
        # 3回目付与の判定期間（2022/7/1～2023/6/30）に十分な出勤記録を作成
        self._create_time_records_for_attendance(user2, date(2022, 7, 1), 300)
        # 2021年7月1日付与で2023年7月1日に時効
        PaidLeaveRecord.objects.create(
            user=user2,
            record_type='grant',
            days=10,
            grant_date=date(2021, 7, 1),
            expiry_date=date(2023, 7, 1),
            description="初回付与"
        )
        user2.current_paid_leave = 10
        user2.save()
        
        # 日次処理を実行
        with patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor._process_expiration_for_user') as mock_expiration:
            judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証
        self.assertEqual(len(judgments), 2)  # user1の1回目付与 + user2の3回目付与
        
        # 両方とも付与成功であることを確認
        for judgment in judgments:
            self.assertTrue(judgment.is_eligible)
        
        # 時効処理が両ユーザーに対して呼び出されたことを確認
        self.assertEqual(mock_expiration.call_count, 2)

    def test_process_daily_grants_performance(self):
        """テストケース1-6: 大量ユーザーでの処理効率確認"""
        target_date = date(2023, 7, 1)
        
        # 100名のユーザーを作成（全員付与対象）
        users = []
        for i in range(100):
            user = self._create_user_with_schedule(date(2023, 1, 1), name_suffix=str(i))
            self._create_time_records_for_attendance(user, date(2023, 1, 1), 150)
            users.append(user)
        for i in range(450):
            user = self._create_user_with_schedule(date(2023, 1, 1), name_suffix=str(i+100))
            self._create_time_records_for_attendance(user, date(2023, 1, 1), 50)
            users.append(user)
        for i in range(450):
            user = self._create_user_with_schedule(date(2023, 1, 2), name_suffix=str(i+550))
            self._create_time_records_for_attendance(user, date(2023, 1, 2), 150)
            users.append(user)
        
        # 処理時間を測定
        start_time = time.time()
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        end_time = time.time()
        
        # 検証
        self.assertEqual(len(judgments), 550)
        
        # 処理時間が許容範囲内（160秒以内）
        processing_time = end_time - start_time
        self.assertLess(processing_time, 200.0)
        
        # 付与成功・失敗の内訳を確認
        eligible_judgments = [j for j in judgments if j.is_eligible]
        ineligible_judgments = [j for j in judgments if not j.is_eligible]
        
        # 100名が付与成功、450名が付与失敗（出勤率不足）
        self.assertEqual(len(eligible_judgments), 100)
        self.assertEqual(len(ineligible_judgments), 450)
        
        # 付与成功者は全て10日付与
        for judgment in eligible_judgments:
            self.assertEqual(judgment.grant_days, 10)
            
        # 付与失敗者は0日
        for judgment in ineligible_judgments:
            self.assertEqual(judgment.grant_days, 0)

    # === 2. TimeRecord変更処理メソッド（process_time_record_change）のテスト ===
    
    @patch('django.utils.timezone.now')
    def test_process_time_record_change_rejudge_required(self, mock_now):
        """テストケース2-1: 再判定が必要な場合のTimeRecord変更処理"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 7, 2))
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        # 既に付与済みの設定
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            description="初回付与"
        )
        user.current_paid_leave = 10
        user.save()
        
        # 再判定処理をモック
        with patch.object(self.processor, '_execute_rejudgment') as mock_rejudgment:
            mock_rejudgment.return_value = [MagicMock(spec=PaidLeaveJudgment)]
            
            # TimeRecord変更処理を実行
            record_date = date(2023, 6, 30)  # 直近付与日より前
            judgments = self.processor.process_time_record_change(user, record_date, 'create')
        
        # 検証
        mock_rejudgment.assert_called_once_with(user, record_date)
        self.assertEqual(len(judgments), 1)

    @patch('django.utils.timezone.now')
    def test_process_time_record_change_rejudge_not_required(self, mock_now):
        """テストケース2-2: 再判定が不要な場合のTimeRecord変更処理"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 7, 2))
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        # TimeRecord変更処理を実行
        record_date = date(2023, 7, 2)  # 直近付与日より後
        judgments = self.processor.process_time_record_change(user, record_date, 'create')
        
        # 検証
        self.assertEqual(len(judgments), 0)

    @patch('django.utils.timezone.now')
    def test_process_time_record_change_create(self, mock_now):
        """テストケース2-3: TimeRecord作成時の処理"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 7, 2))
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        # 既存の出勤記録を作成（判定に影響）
        self._create_time_records_for_attendance(user, date(2023, 1, 1), 100)
        
        # 既に付与済みの設定
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            description="初回付与"
        )
        user.current_paid_leave = 10
        user.save()
        
        # TimeRecord新規作成時の処理
        record_date = date(2023, 6, 30)
        with patch.object(self.processor, '_execute_rejudgment') as mock_rejudgment:
            mock_rejudgment.return_value = []
            
            judgments = self.processor.process_time_record_change(user, record_date, 'create')
        
        # 検証：再判定が実行されることを確認
        mock_rejudgment.assert_called_once_with(user, record_date)

    @patch('django.utils.timezone.now')
    def test_process_time_record_change_delete(self, mock_now):
        """テストケース2-4: TimeRecord削除時の処理"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 7, 2))
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        # 既に付与済みの設定
        PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            description="初回付与"
        )
        user.current_paid_leave = 10
        user.save()
        
        # TimeRecord削除時の処理
        record_date = date(2023, 6, 30)
        with patch.object(self.processor, '_execute_rejudgment') as mock_rejudgment:
            mock_rejudgment.return_value = []
            
            judgments = self.processor.process_time_record_change(user, record_date, 'delete')
        
        # 検証：再判定が実行されることを確認
        mock_rejudgment.assert_called_once_with(user, record_date)

    @patch('django.utils.timezone.now')
    def test_process_time_record_change_grant_date_today(self, mock_now):
        """テストケース2-5: 付与日当日の記録変更"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 7, 1))
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        # TimeRecord変更処理を実行（付与日当日）
        record_date = date(2023, 7, 1)
        judgments = self.processor.process_time_record_change(user, record_date, 'create')
        
        # 検証：再判定は実行されない
        self.assertEqual(len(judgments), 0)

    @patch('django.utils.timezone.now')
    def test_process_time_record_change_no_grants_yet(self, mock_now):
        """テストケース2-6: まだ付与がないユーザーの記録変更"""
        mock_now.return_value = timezone.make_aware(datetime(2023, 6, 1))
        
        # ユーザー設定（初回付与前）
        user = self._create_user_with_schedule(date(2023, 5, 1))
        
        # TimeRecord変更処理を実行
        record_date = date(2023, 6, 1)
        judgments = self.processor.process_time_record_change(user, record_date, 'create')
        
        # 検証：再判定対象なし
        self.assertEqual(len(judgments), 0)

    # === 3. PaidLeaveRecord変更処理メソッド（process_paid_leave_record_change）のテスト ===
    
    def test_process_paid_leave_record_change_use_create(self):
        """テストケース3-1: 有給使用記録作成時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 10
        user.save()
        
        # 使用記録作成
        record = PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=3,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            used_date=date(2023, 8, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 7
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'create')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_grant_create(self):
        """テストケース3-2: 有給付与記録作成時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 5
        user.save()
        
        # 付与記録作成
        record = PaidLeaveRecord.objects.create(
            user=user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 15
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'create')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_cancel_create(self):
        """テストケース3-3: 有給取消記録作成時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 10
        user.save()
        
        # 取消記録作成
        record = PaidLeaveRecord.objects.create(
            user=user,
            record_type='cancel',
            days=5,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            cancellation_date=date(2023, 8, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 5
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'create')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_expire_create(self):
        """テストケース3-4: 時効記録作成時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 8
        user.save()
        
        # 時効記録作成
        record = PaidLeaveRecord.objects.create(
            user=user,
            record_type='expire',
            days=3,
            grant_date=date(2021, 7, 1),
            expiry_date=date(2023, 7, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 5
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'create')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_update(self):
        """テストケース3-5: PaidLeaveRecord更新時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 7
        user.save()
        
        # 記録更新（以前は3日、現在は5日）
        record = PaidLeaveRecord.objects.create(
            user=user,
            record_type='use',
            days=5,  # 更新後
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            used_date=date(2023, 8, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 5  # 再計算された正しい残日数
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'update')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_delete(self):
        """テストケース3-6: PaidLeaveRecord削除時の残日数更新"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 5
        user.save()
        
        # 削除される記録（使用記録3日）
        record = PaidLeaveRecord(
            user=user,
            record_type='use',
            days=3,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            used_date=date(2023, 8, 1),
        )
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            mock_update.return_value = 8  # 5+3
            
            # PaidLeaveRecord変更処理を実行
            result = self.processor.process_paid_leave_record_change(user, record, 'delete')
        
        # 検証
        self.assertIsNone(result)  # 戻り値はNone
        mock_update.assert_called_once()

    def test_process_paid_leave_record_change_multiple_consecutive(self):
        """テストケース3-7: 複数のPaidLeaveRecord変更の連続処理"""
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        user.current_paid_leave = 10
        user.save()
        
        # 残日数更新処理をモック
        with patch('timeclock.services.paid_leave_balance_manager.PaidLeaveBalanceManager.update_user_balance') as mock_update:
            # 各処理での期待残日数を設定
            mock_update.side_effect = [8, 13, 14]  # 10-2=8, 8+5=13, 13+1=14
            
            # 処理1: 使用記録作成（days=2）
            record1 = PaidLeaveRecord.objects.create(
                user=user,
                record_type='use',
                days=2,
                grant_date=date(2023, 7, 1),
                expiry_date=date(2025, 7, 1),
                used_date=date(2023, 8, 1),
            )
            self.processor.process_paid_leave_record_change(user, record1, 'create')
            
            # 処理2: 付与記録作成（days=5）
            record2 = PaidLeaveRecord.objects.create(
                user=user,
                record_type='grant',
                days=5,
                grant_date=date(2023, 7, 1),
                expiry_date=date(2025, 7, 1),
            )
            self.processor.process_paid_leave_record_change(user, record2, 'create')
            
            # 処理3: 使用記録削除（days=1）
            record3 = PaidLeaveRecord(
                user=user,
                record_type='use',
                days=1,
                grant_date=date(2023, 7, 1),
                expiry_date=date(2025, 7, 1),
                used_date=date(2023, 8, 2),
            )
            self.processor.process_paid_leave_record_change(user, record3, 'delete')
        
        # 検証：各処理で正しく更新されること
        self.assertEqual(mock_update.call_count, 3)

    # === 4. エラー処理・例外処理のテスト ===
    
    def test_error_handling_nonexistent_user(self):
        """テストケース4-1: 存在しないユーザーに対する処理"""
        # 存在しないユーザー（削除済み）
        user = User(id=99999, name="deleted_user", email="deleted@example.com")
        
        # エラーが発生しないことを検証
        try:
            judgments = self.processor.process_time_record_change(user, date(2023, 6, 30), 'create')
            # 処理が中断されずに空のリストが返される
            self.assertEqual(judgments, [])
        except Exception as e:
            self.fail(f"予期しないエラーが発生: {str(e)}")

    def test_error_handling_invalid_date(self):
        """テストケース4-3: 無効な日付での処理"""
        # 無効な日付での処理
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            self.processor.process_daily_grants_and_expirations(None)
        
        user = self._create_user_with_schedule(date(2023, 1, 1))
        
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            self.processor.process_time_record_change(user, "invalid_date", 'create')

    # === 5. パフォーマンス・統合テスト ===
    
    def test_integration_with_all_classes(self):
        """テストケース5-2: 他クラスとの統合動作テスト"""
        target_date = date(2023, 7, 1)
        
        # ユーザー設定
        user = self._create_user_with_schedule(date(2023, 1, 1))
        self._create_time_records_for_attendance(user, date(2023, 1, 1), 150)
        
        # 統合テスト：日次処理から残日数更新まで
        judgments = self.processor.process_daily_grants_and_expirations(target_date)
        
        # 検証：全クラスが連携して動作していること
        self.assertEqual(len(judgments), 1)
        self.assertTrue(judgments[0].is_eligible)
        
        # PaidLeaveCalculatorが正しく判定
        self.assertEqual(judgments[0].grant_days, 10)
        
        # PaidLeaveGrantProcessorが正しく付与
        grant_records = PaidLeaveRecord.objects.filter(
            user=user, 
            record_type='grant',
            grant_date=target_date
        )
        self.assertEqual(grant_records.count(), 1)
        
        # PaidLeaveBalanceManagerが正しく残日数更新
        user.refresh_from_db()
        self.assertEqual(user.current_paid_leave, 10)
        
        # データの一貫性維持確認
        self.assertEqual(grant_records.first().days, judgments[0].grant_days)
        self.assertEqual(grant_records.first().expiry_date, judgments[0].expiry_date)