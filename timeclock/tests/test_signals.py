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
        
        # 既存の付与記録を作成
        PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            description='初回付与'
        )
    
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
            timestamp=datetime.combine(date(2023, 6, 30), time(9, 0))
        )
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        
        # 呼び出し引数を確認
        mock_process.assert_called_once_with(
            self.user, 
            date(2023, 6, 30), 
            'create'
        )
        
        # 戻り値が PaidLeaveJudgment のリストであることを確認
        result = mock_process.return_value
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertTrue(hasattr(result[0], 'is_eligible'))
    
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
            timestamp=datetime.combine(date(2023, 6, 15), time(9, 0))
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
        
        # 戻り値確認
        result = mock_process.return_value
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].is_eligible)


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
        
        # 戻り値がNoneであることを確認
        result = mock_process.return_value
        self.assertIsNone(result)


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
        self.user.paid_leave_grant_schedule = ["2023-07-01"]
        self.user.save()
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_paid_leave_record_change')
    def test_signal_chain_execution(self, mock_plr_process, mock_tr_process):
        """
        シグナル連鎖テスト: TimeRecord変更による再判定とPaidLeaveRecord自動作成の連鎖
        
        目的: TimeRecord変更で再判定が行われ、新たにPaidLeaveRecordが作成される際のシグナル連鎖を検証
        """
        # TimeRecordシグナルのモック設定
        mock_judgment = Mock()
        mock_judgment.is_eligible = True
        mock_judgment.grant_days = 10
        mock_judgment.grant_date = date(2023, 7, 1)
        mock_tr_process.return_value = [mock_judgment]
        
        # PaidLeaveRecordシグナルのモック設定  
        mock_plr_process.return_value = None
        
        # TimeRecord作成（出勤率改善により付与条件を満たす）
        TimeRecord.objects.create(
            user=self.user,
            clock_type='clock_in',
            timestamp=datetime.combine(date(2023, 6, 30), time(9, 0))
        )
        
        # TimeRecordシグナルが発火したことを確認
        self.assertTrue(mock_tr_process.called)
        mock_tr_process.assert_called_once_with(
            self.user,
            date(2023, 6, 30),
            'create'
        )
        
        # 実際のシナリオでは、ここで再判定により付与記録が作成される
        # テストでは手動でPaidLeaveRecordを作成してシグナル連鎖をシミュレート
        PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='grant',
            days=10,
            grant_date=date(2023, 7, 1),
            expiry_date=date(2025, 7, 1),
            description='再判定により付与'
        )
        
        # PaidLeaveRecordシグナルが発火したことを確認
        self.assertTrue(mock_plr_process.called)
        
        # 両方のシグナルが適切に実行されたことを確認
        self.assertEqual(mock_tr_process.call_count, 1)
        self.assertEqual(mock_plr_process.call_count, 1)
    
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    def test_signal_disabled_flag(self, mock_process):
        """
        シグナル無効化フラグのテスト
        
        目的: テスト時などにシグナルが無効化されることを検証
        """
        from timeclock.signals import handle_time_record_save, handle_time_record_delete
        
        # 関数レベルの無効化フラグを設定
        handle_time_record_save._disabled = True
        handle_time_record_delete._disabled = True
        
        try:
            # シグナル無効化フラグが設定されている状態でTimeRecord作成
            TimeRecord.objects.create(
                user=self.user,
                clock_type='clock_in',
                timestamp=datetime.combine(date(2023, 6, 30), time(9, 0))
            )
            
            # シグナルが無効化されているため、process_time_record_changeは呼び出されない
            self.assertFalse(mock_process.called)
        finally:
            # フラグをリセット
            handle_time_record_save._disabled = False
            handle_time_record_delete._disabled = False