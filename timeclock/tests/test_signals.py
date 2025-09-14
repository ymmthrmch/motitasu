"""
有給休暇システム Signalsテスト

SIGNALS_TEST.mdのテストケースを実装：
- テストケース1-1: TimeRecord作成時の再判定実行
- テストケース1-2: TimeRecord削除時の再判定実行  
- テストケース2-1: 有給使用記録作成時の残日数更新
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, Mock
from datetime import date, datetime, time
from django.utils import timezone
from timeclock.models import TimeRecord, PaidLeaveRecord

User = get_user_model()


class TimeRecordSignalTest(TestCase):
    """TimeRecord変更シグナルのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='田中太郎'
        )
        # 入社日と週所定労働日数を設定
        self.user.hire_date = date(2023, 1, 1)
        self.user.weekly_work_days = 5
        self.user.paid_leave_grant_schedule = [
            "2023-07-01", 
            "2024-07-01", 
            "2025-07-01"
        ]
        self.user.save()
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    def test_time_record_create_signal_fired(self, mock_process):
        """
        テストケース1-1: TimeRecord作成時の再判定実行
        
        目的: TimeRecord作成時にpost_saveシグナルが発火し、再判定処理が実行されることを検証
        """
        # モックの戻り値を設定（PaidLeaveJudgmentオブジェクトのリスト）
        mock_judgment = Mock()
        mock_judgment.is_eligible = True
        mock_judgment.grant_days = 10
        mock_judgment.attendance_rate = 0.853
        mock_process.return_value = [mock_judgment]
        
        # TimeRecord作成（付与日より前の日付）
        TimeRecord.objects.create(
            user=self.user,
            clock_type='clock_in',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(9, 0)))
        )
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        
        # 呼び出し引数を確認
        mock_process.assert_called_once_with(
            self.user, 
            date(2023, 6, 30), 
            'create'
        )
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    def test_time_record_delete_signal_fired(self, mock_process):
        """
        テストケース1-2: TimeRecord削除時の再判定実行
        
        目的: TimeRecord削除時にpost_deleteシグナルが発火し、再判定処理が実行されることを検証
        """
        # モックの戻り値を設定
        mock_judgment = Mock()
        mock_judgment.is_eligible = False
        mock_judgment.grant_days = 0
        mock_judgment.attendance_rate = 0.775
        mock_process.return_value = [mock_judgment]
        
        # TimeRecord作成
        time_record = TimeRecord.objects.create(
            user=self.user,
            clock_type='clock_in',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 15), time(9, 0)))
        )
        
        # モックをリセット（作成時のシグナル呼び出しをクリア）
        mock_process.reset_mock()
        
        # TimeRecord削除
        time_record.delete()
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        
        # 呼び出し引数を確認
        mock_process.assert_called_once_with(
            self.user,
            date(2023, 6, 15),
            'delete'
        )


class PaidLeaveRecordSignalTest(TestCase):
    """PaidLeaveRecord変更シグナルのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.user = User.objects.create_user(
            email='test2@example.com',
            name='佐藤花子'
        )
        self.user.hire_date = date(2023, 1, 1)
        self.user.current_paid_leave = 10
        self.user.save()
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_paid_leave_record_change')
    def test_paid_leave_use_record_signal_fired(self, mock_process):
        """
        テストケース2-1: 有給使用記録作成時の残日数更新
        
        目的: PaidLeaveRecord（使用）作成時にpost_saveシグナルが発火し、残日数更新が実行されることを検証
        """
        # モックの設定（残日数更新処理は戻り値なし）
        mock_process.return_value = None
        
        # 有給使用記録作成
        paid_leave_record = PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='use',
            days=3,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            used_date=date(2023, 8, 1),
            description='夏季休暇'
        )
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        
        # 呼び出し引数を確認
        mock_process.assert_called_once_with(
            self.user,
            paid_leave_record,
            'create'
        )
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_paid_leave_record_change')
    def test_paid_leave_record_delete_signal_fired(self, mock_process):
        """
        テストケース2-2: 有給記録削除時の残日数更新
        
        目的: PaidLeaveRecord削除時にpost_deleteシグナルが発火し、残日数更新が実行されることを検証
        """
        # モックの設定
        mock_process.return_value = None
        
        # 有給使用記録作成
        paid_leave_record = PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='use',
            days=1,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            used_date=date(2023, 9, 1),
            description='有給消化'
        )
        
        # モックをリセット（作成時のシグナル呼び出しをクリア）
        mock_process.reset_mock()
        
        # PaidLeaveRecord削除
        paid_leave_record.delete()
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        
        # 呼び出し引数を確認
        mock_process.assert_called_once_with(
            self.user,
            paid_leave_record,
            'delete'
        )


class SignalIntegrationTest(TestCase):
    """シグナル連鎖・統合テスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.user = User.objects.create_user(
            email='test3@example.com',
            name='山田一郎'
        )
        self.user.hire_date = date(2023, 1, 1)
        self.user.weekly_work_days = 5
        self.user.current_paid_leave = 0
        self.user.paid_leave_grant_schedule = ["2023-07-01", "2024-07-01", "2025-07-01"]
        self.user.save()

    
    def test_signal_chain_execution_creating_new_timerecord(self):
        """
        シグナル連鎖テスト: TimeRecord変更による再判定とPaidLeaveRecord自動作成の連鎖
        
        目的: TimeRecord変更で再判定が行われ、新たにPaidLeaveRecordが作成され、
              さらにその作成により残日数が更新される一連の処理を検証
        """
        # 初期状態の確認
        self.assertEqual(self.user.current_paid_leave, 0)
        self.assertEqual(PaidLeaveRecord.objects.filter(user=self.user).count(), 0)
        
        # シグナルを一時的に無効化して準備データを作成
        from timeclock.signals import handle_time_record_save, handle_time_record_delete
        
        # 6ヶ月分の出勤記録を作成（出勤率80%以上を満たすため）
        # 準備段階ではシグナルを無効化
        handle_time_record_save._disabled = True
        handle_time_record_delete._disabled = True
        
        try:
            # 103日分の出勤記録を作成（全労働日の8割以上出勤を満たすため）
            # 1月から6月にかけて平日を中心に記録
            work_days_count = 0
            for month in range(1, 7):
                # 各月の日数を取得
                if month in [1, 3, 5]:
                    days_in_month = 31
                elif month == 2:
                    days_in_month = 28
                else:
                    days_in_month = 30
                
                # 平日を中心に出勤記録を作成（週5日ペース）
                for day in range(1, days_in_month + 1):
                    # 土日を除く平日のみ（簡易的な判定）
                    weekday = date(2023, month, day).weekday()
                    if weekday < 5:  # 月曜日(0)〜金曜日(4)
                        if work_days_count < 103:  # 103日分まで
                            TimeRecord.objects.create(
                                user=self.user,
                                clock_type='clock_in',
                                timestamp=timezone.make_aware(datetime.combine(date(2023, month, day), time(9, 0)))
                            )
                            TimeRecord.objects.create(
                                user=self.user,
                                clock_type='clock_out',
                                timestamp=timezone.make_aware(datetime.combine(date(2023, month, day), time(18, 0)))
                            )
                            work_days_count += 1

            if work_days_count != 103:
                raise ValueError("準備データの出勤記録が103日分になっていません。")
            
        finally:
            # シグナルを再度有効化
            handle_time_record_save._disabled = False
            handle_time_record_delete._disabled = False
        
        # 付与日直前（6月30日）の記録を追加 - これがトリガーとなる（シグナル有効）
        TimeRecord.objects.create(
            user=self.user,
            clock_type='clock_in',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(9, 0)))
        )
        TimeRecord.objects.create(
            user=self.user,
            clock_type='clock_out',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(18, 0)))
        )
        
        # シグナル連鎖により自動的にPaidLeaveRecordが作成されることを確認
        # 注：実際のシグナル連鎖はビジネスロジックに依存するため、
        # ここではシグナルが発火したことを確認するまでに留める
        # （実際の付与処理はPaidLeaveAutoProcessorのテストで検証）
        
        # TimeRecord作成後、シグナルが発火したことを確認
        paid_leave_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            grant_date=date(2023, 7, 1)
        )
        self.assertEqual(paid_leave_records.count(), 1)
        self.assertEqual(self.user.current_paid_leave, 10)
    
    def test_signal_chain_execution_deleting_new_timerecord(self):
        """
        シグナル連鎖テスト: TimeRecord削除による再判定とPaidLeaveRecord自動削除の連鎖
        
        目的: TimeRecord変更で再判定が行われ、新たにPaidLeaveRecordが作成され、
              さらにその作成により残日数が更新される一連の処理を検証
        """
        # 初期状態の確認
        self.assertEqual(self.user.current_paid_leave, 0)
        self.assertEqual(PaidLeaveRecord.objects.filter(user=self.user).count(), 0)
        
        # シグナルを一時的に無効化して準備データを作成
        from timeclock.signals import handle_time_record_save, handle_time_record_delete
        
        # 6ヶ月分の出勤記録を作成（出勤率80%以上を満たすため）
        # 準備段階ではシグナルを無効化
        handle_time_record_save._disabled = True
        handle_time_record_delete._disabled = True
        
        try:
            # 104日分の出勤記録を作成（全労働日の8割以上出勤を満たすため）
            # 1月から6月にかけて平日を中心に記録
            work_days_count = 0
            for month in range(1, 7):
                # 各月の日数を取得
                if month in [1, 3, 5]:
                    days_in_month = 31
                elif month == 2:
                    days_in_month = 28
                else:
                    days_in_month = 30
                
                # 平日を中心に出勤記録を作成（週5日ペース）
                for day in range(1, days_in_month + 1):
                    # 土日を除く平日のみ（簡易的な判定）
                    weekday = date(2023, month, day).weekday()
                    if weekday < 5 and not (month == 6 and day == 30):  # 月曜日(0)〜金曜日(4)
                        if work_days_count < 103:  # 103日分まで
                            TimeRecord.objects.create(
                                user=self.user,
                                clock_type='clock_in',
                                timestamp=timezone.make_aware(datetime.combine(date(2023, month, day), time(9, 0)))
                            )
                            TimeRecord.objects.create(
                                user=self.user,
                                clock_type='clock_out',
                                timestamp=timezone.make_aware(datetime.combine(date(2023, month, day), time(18, 0)))
                            )
                            work_days_count += 1
            
            if work_days_count != 103:
                raise ValueError("準備データの出勤記録が103日分になっていません。")
            
            # 削除するための付与日直前（6月30日）の記録も追加
            TimeRecord.objects.create(
                user=self.user,
                clock_type='clock_in',
                timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(9, 0)))
            )
            TimeRecord.objects.create(
                user=self.user,
                clock_type='clock_out',
                timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(18, 0)))
            )

            # 削除されるPaidLeaveRecordを追加
            PaidLeaveRecord.objects.create(
                user=self.user,
                record_type='grant',
                days=10,
                grant_date=date(2023, 7, 1),
                expiry_date=date(2025, 7, 1),
                description='テスト付与'
            )
            self.user.current_paid_leave = 10
            self.user.save()

        finally:
            # シグナルを再度有効化
            handle_time_record_save._disabled = False
            handle_time_record_delete._disabled = False
        
        # 付与日直前（6月30日）の記録を削除 - これがトリガーとなる（シグナル有効）
        TimeRecord.objects.get(
            user=self.user,
            clock_type='clock_in',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(9, 0)))
        ).delete()
        TimeRecord.objects.get(
            user=self.user,
            clock_type='clock_out',
            timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(18, 0)))
        ).delete()
        
        # シグナル連鎖により自動的にPaidLeaveRecordが削除されることを確認
        # DB更新後の最新状態を取得
        self.user.refresh_from_db()
        
        paid_leave_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            grant_date=date(2023, 7, 1)
        )
        self.assertEqual(paid_leave_records.count(), 0)
        self.assertEqual(self.user.current_paid_leave, 0)

    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_paid_leave_record_change')
    def test_signal_disabled_flag(self, mock_plr_process, mock_tr_process):
        """
        シグナル無効化フラグのテスト
        
        目的: テスト時などにTimeRecordとPaidLeaveRecordのシグナルが無効化されることを検証
        """
        from timeclock.signals import (handle_time_record_save, handle_time_record_delete,
                                       handle_paid_leave_record_save, handle_paid_leave_record_delete)
        
        # TimeRecord関連のシグナル無効化テスト
        handle_time_record_save._disabled = True
        handle_time_record_delete._disabled = True
        
        try:
            # シグナル無効化フラグが設定されている状態でTimeRecord作成
            time_record = TimeRecord.objects.create(
                user=self.user,
                clock_type='clock_in',
                timestamp=timezone.make_aware(datetime.combine(date(2023, 6, 30), time(9, 0)))
            )
            
            # シグナルが無効化されているため、process_time_record_changeは呼び出されない
            self.assertFalse(mock_tr_process.called)
            
            # TimeRecord削除
            time_record.delete()
            
            # 削除時もシグナルが無効化されている
            self.assertFalse(mock_tr_process.called)
        finally:
            # フラグをリセット
            handle_time_record_save._disabled = False
            handle_time_record_delete._disabled = False
        
        # PaidLeaveRecord関連のシグナル無効化テスト
        handle_paid_leave_record_save._disabled = True
        handle_paid_leave_record_delete._disabled = True
        
        try:
            # シグナル無効化フラグが設定されている状態でPaidLeaveRecord作成
            paid_leave_record = PaidLeaveRecord.objects.create(
                user=self.user,
                record_type='grant',
                days=10,
                grant_date=date(2023, 7, 1),
                expiry_date=date(2025, 7, 1),
                description='テスト付与'
            )
            
            # シグナルが無効化されているため、process_paid_leave_record_changeは呼び出されない
            self.assertFalse(mock_plr_process.called)
            
            # PaidLeaveRecord削除
            paid_leave_record.delete()
            
            # 削除時もシグナルが無効化されている
            self.assertFalse(mock_plr_process.called)
        finally:
            # フラグをリセット
            handle_paid_leave_record_save._disabled = False
            handle_paid_leave_record_delete._disabled = False