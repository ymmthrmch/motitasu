# Signalsテスト仕様書

## 概要
本仕様書は、有給休暇システムのDjangoシグナル処理のテストケースを定義する。
TimeRecord変更とPaidLeaveRecord変更に伴う自動処理が正確に実行されることを検証する。

## テストケース一覧

### 1. TimeRecord変更シグナル（handle_time_record_change）のテスト

#### テストケース1-1: TimeRecord作成時の再判定実行
**目的**: TimeRecord作成時にpost_saveシグナルが発火し、再判定処理が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存付与: 2023年7月1日に10日付与済み
- 作成するTimeRecord:
  - 日付: 2023年6月30日 (付与日より前)
  - timestamp: 2023年6月30日 09:00
  - clock_type: 'clock_in'

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_time_record_changeメソッド呼び出し: ✅ 実行される
- 再判定実行: ✅ 影響を受ける付与回の再判定が実行される
- 戻り値: [PaidLeaveJudgmentオブジェクト]（再判定結果を含むリスト）
- ログ出力: "TimeRecord変更処理開始" が記録される

#### テストケース1-2: TimeRecord削除時の再判定実行
**目的**: TimeRecord削除時にpost_deleteシグナルが発火し、再判定処理が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存付与: 2023年7月1日に10日付与済み
- 削除するTimeRecord:
  - 日付: 2023年6月15日 (付与日より前)
  - timestamp: 2023年6月15日 09:00
  - clock_type: 'clock_in'

**検証値と期待結果**:
- シグナル発火: ✅ post_deleteが呼び出される
- process_time_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'delete'で処理される
- 再判定実行: ✅ 出勤日数減少による影響を判定

#### テストケース1-3: TimeRecord更新時の再判定実行
**目的**: TimeRecord更新時にpost_saveシグナルが発火し、再判定処理が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存付与: 2023年7月1日に10日付与済み
- 更新するTimeRecord:
  - 元の日付: 2023年6月20日
  - 新しい日付: 2023年6月20日 (時刻のみ変更)
  - 元timestamp: 2023年6月20日 09:00
  - 新timestamp: 2023年6月20日 10:00

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_time_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'update'で処理される

#### テストケース1-4: 再判定が不要なTimeRecord変更
**目的**: 付与日以降のTimeRecord変更では再判定が実行されないことを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存付与: 2023年7月1日に10日付与済み
- 作成するTimeRecord:
  - 日付: 2023年7月2日 (付与日より後)
  - timestamp: 2023年7月2日 09:00
  - clock_type: 'clock_in'

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_time_record_changeメソッド呼び出し: ✅ 実行される
- 再判定実行: ❌ should_rejudge=Falseで処理終了
- 戻り値: []（空のPaidLeaveJudgmentリスト）

#### テストケース1-5: まだ付与がないユーザーのTimeRecord変更
**目的**: 初回付与前のユーザーでTimeRecord変更があっても再判定されないことを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年5月1日
  - 週所定労働日数: 5日
  - 付与履歴: なし（初回付与前）
- 作成するTimeRecord:
  - 日付: 2023年6月1日
  - timestamp: 2023年6月1日 09:00
  - clock_type: 'clock_in'

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_time_record_changeメソッド呼び出し: ✅ 実行される
- 再判定実行: ❌ 直近付与日がないため処理終了
- 戻り値: []（空のPaidLeaveJudgmentリスト）

#### テストケース1-6: シグナル無効化フラグのテスト
**目的**: テスト時などにシグナルが無効化されることを検証
**設定値**:
- シグナル無効化フラグ: True
- ユーザー: 任意
- TimeRecord: 任意

**検証値と期待結果**:
- シグナル発火: ❌ 無効化により処理されない
- process_time_record_changeメソッド呼び出し: ❌ 実行されない

### 2. PaidLeaveRecord変更シグナル（handle_paid_leave_record_change）のテスト

#### テストケース2-1: 有給使用記録作成時の残日数更新
**目的**: PaidLeaveRecord（使用）作成時にpost_saveシグナルが発火し、残日数更新が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - current_paid_leave: 10日
- 作成するPaidLeaveRecord:
  - record_type: 'use'
  - days: 3
  - used_date: 2023年8月1日
  - grant_date: 2023年7月1日
  - expiry_date: 2025年7月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'create'で処理される
- 残日数更新: user.current_paid_leave = 7日に更新
- ログ出力: "PaidLeaveRecord変更処理" が記録される

#### テストケース2-2: 有給付与記録作成時の残日数更新
**目的**: PaidLeaveRecord（付与）作成時にpost_saveシグナルが発火し、残日数更新が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - current_paid_leave: 5日
- 作成するPaidLeaveRecord:
  - record_type: 'grant'
  - days: 10
  - grant_date: 2023年7月1日
  - expiry_date: 2025年7月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'create'で処理される
- 残日数更新: user.current_paid_leave = 15日に更新

#### テストケース2-3: 有給取消記録作成時の残日数更新
**目的**: PaidLeaveRecord（取消）作成時にpost_saveシグナルが発火し、残日数更新が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - current_paid_leave: 10日
- 作成するPaidLeaveRecord:
  - record_type: 'cancel'
  - days: 5
  - grant_date: 2023年7月1日
  - expiry_date: 2025年7月1日
  - cancellation_date: 2023年8月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'create'で処理される
- 残日数更新: user.current_paid_leave = 5日に更新

#### テストケース2-4: 時効記録作成時の残日数更新
**目的**: PaidLeaveRecord（時効）作成時にpost_saveシグナルが発火し、残日数更新が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2021年1月1日
  - current_paid_leave: 8日
- 作成するPaidLeaveRecord:
  - record_type: 'expire'
  - days: 3
  - grant_date: 2021年7月1日
  - expiry_date: 2023年7月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'create'で処理される
- 残日数更新: user.current_paid_leave = 5日に更新

#### テストケース2-5: PaidLeaveRecord削除時の残日数更新
**目的**: PaidLeaveRecord削除時にpost_deleteシグナルが発火し、残日数更新が実行されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - current_paid_leave: 7日
- 削除するPaidLeaveRecord:
  - record_type: 'use'
  - days: 3
  - used_date: 2023年8月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_deleteが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'delete'で処理される
- 残日数更新: user.current_paid_leave = 10日に更新（3日分戻る）

#### テストケース2-6: PaidLeaveRecord更新時の残日数更新
**目的**: PaidLeaveRecord更新時にpost_saveシグナルが発火し、残日数が再計算されることを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - current_paid_leave: 7日
- 更新するPaidLeaveRecord:
  - record_type: 'use'
  - 更新前days: 3
  - 更新後days: 5
  - used_date: 2023年8月1日

**検証値と期待結果**:
- シグナル発火: ✅ post_saveが呼び出される
- process_paid_leave_record_changeメソッド呼び出し: ✅ 実行される
- change_type: 'update'で処理される
- 残日数更新: 再計算された正しい残日数に更新

### 3. シグナル連鎖・複合処理のテスト

#### テストケース3-1: TimeRecord変更による再判定とPaidLeaveRecord自動作成の連鎖
**目的**: TimeRecord変更で再判定が行われ、新たにPaidLeaveRecordが作成される際のシグナル連鎖を検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存出勤記録: 100日（出勤率79.9%で付与失敗）
- 追加するTimeRecord:
  - 日付: 2023年6月30日
  - 追加により出勤率80.1%に改善

**検証値と期待結果**:
- TimeRecordシグナル発火: ✅ handle_time_record_change実行
- 再判定実行: ✅ 出勤率改善により付与条件満たす
- PaidLeaveRecord自動作成: ✅ grant記録が作成される
- PaidLeaveRecordシグナル発火: ✅ handle_paid_leave_record_change実行
- 残日数更新: ✅ user.current_paid_leaveが正しく更新

#### テストケース3-2: TimeRecord削除による付与取消とPaidLeaveRecord作成の連鎖
**目的**: TimeRecord削除で出勤率低下し、付与取消が発生する際のシグナル連鎖を検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - 週所定労働日数: 5日
  - 既存付与: 10日
  - 既存出勤記録: 101日（出勤率80.1%で付与成功済み）
- 削除するTimeRecord:
  - 日付: 2023年6月15日
  - 削除により出勤率79.9%に低下

**検証値と期待結果**:
- TimeRecordシグナル発火: ✅ handle_time_record_change実行
- 再判定実行: ✅ 出勤率低下により付与条件を満たさない
- PaidLeaveRecord自動作成: ✅ cancel記録が作成される
- PaidLeaveRecordシグナル発火: ✅ handle_paid_leave_record_change実行
- 残日数更新: ✅ 取消分が反映された残日数に更新

### 4. エラー処理・例外処理のテスト

#### テストケース4-1: PaidLeaveAutoProcessor処理エラー時のシグナル処理
**目的**: 依存クラスでエラーが発生した場合の適切なエラー処理を検証
**設定値**:
- ユーザー: 正常な設定
- TimeRecord: 正常な設定
- PaidLeaveAutoProcessor: モックでエラーを発生させる

**検証値と期待結果**:
- シグナル発火: ✅ 正常に呼び出される
- エラー処理: ✅ 例外が適切にキャッチされる
- ログ出力: ✅ エラーログが出力される
- データ整合性: ✅ データベースの状態は変更されない

#### テストケース4-2: 存在しないユーザーのシグナル処理
**目的**: 削除されたユーザーのレコード変更時のエラー処理を検証
**設定値**:
- ユーザー: 削除済みまたは無効なユーザーID
- TimeRecord/PaidLeaveRecord: 正常な設定

**検証値と期待結果**:
- シグナル発火: ✅ 正常に呼び出される
- エラー処理: ✅ 適切にハンドリングされる
- システム継続: ✅ 他の処理に影響しない

#### テストケース4-3: データベース接続エラー時のシグナル処理
**目的**: データベース接続エラー時の適切な処理を検証
**設定値**:
- データベース接続: 一時的に無効化
- シグナル処理: 正常なパラメータ

**検証値と期待結果**:
- シグナル発火: ✅ 正常に呼び出される
- エラー処理: ✅ データベースエラーが適切に処理される
- ログ出力: ✅ エラー詳細がログに記録される

### 5. Userモデル拡張メソッドのテスト

#### テストケース5-1: get_latest_grant_dateメソッドのテスト
**目的**: 直近付与日の取得が正しく動作することを検証
**設定値**:
- ユーザー:
  - 入社日: 2023年1月1日
  - paid_leave_grant_schedule: [2023年7月1日, 2024年7月1日, 2025年7月1日]
- 基準日: 2024年1月1日

**検証値と期待結果**:
- get_latest_grant_date(2024年1月1日): 2023年7月1日
- get_latest_grant_date(2023年6月30日): None（まだ付与前）
- get_latest_grant_date(None): 現在日時基準での直近付与日

#### テストケース5-2: is_grant_date_todayメソッドのテスト
**目的**: 指定日が付与日かの判定が正しく動作することを検証
**設定値**:
- ユーザー:
  - paid_leave_grant_schedule: [2023年7月1日, 2024年7月1日, 2025年7月1日]

**検証値と期待結果**:
- is_grant_date_today(2023年7月1日): True
- is_grant_date_today(2024年7月1日): True
- is_grant_date_today(2023年6月30日): False
- is_grant_date_today(2023年7月2日): False

#### テストケース5-3: paid_leave_grant_schedule自動計算のテスト
**目的**: 入社日変更時の付与スケジュール自動更新を検証
**設定値**:
- ユーザー: 初期状態（hire_date未設定）
- hire_date設定: 2023年1月1日

**検証値と期待結果**:
- save()実行後のpaid_leave_grant_schedule: [2023年7月1日, 2024年7月1日, 2025年7月1日, ...]
- 1回目〜20回目程度の付与日が正確に計算されること

#### テストケース5-4: _calculate_grant_scheduleメソッドのテスト
**目的**: 付与スケジュール計算ロジックの正確性を検証
**設定値**:
- 入社日: 2020年2月29日（うるう年）

**検証値と期待結果**:
- 計算される付与スケジュール:
  - 1回目: 2020年8月29日
  - 2回目: 2021年8月29日
  - 3回目: 2022年8月29日
  - 4回目: 2023年8月29日
  - 5回目: 2024年8月29日

### 6. パフォーマンス・スケーラビリティテスト

#### テストケース6-1: 大量TimeRecord変更時のシグナル処理性能
**目的**: 多数のTimeRecord変更が同時に発生した場合の性能を検証
**設定値**:
- ユーザー数: 100名
- TimeRecord変更: 各ユーザー10件ずつ一括作成
- 総変更数: 1000件

**検証値と期待結果**:
- 全シグナル処理完了: ✅ 制限時間内に処理完了
- メモリ使用量: ✅ 許容範囲内
- データ整合性: ✅ 全ての残日数が正しく更新

#### テストケース6-2: 並行処理時のシグナル競合テスト
**目的**: 同一ユーザーの複数レコードが同時に変更された場合の処理を検証
**設定値**:
- ユーザー: 1名
- 同時操作: TimeRecord作成とPaidLeaveRecord使用を並行実行

**検証値と期待結果**:
- デッドロック回避: ✅ デッドロックが発生しない
- データ整合性: ✅ 最終的な残日数が正確
- 処理順序: ✅ 適切な順序で処理される

## テスト実行時の注意事項

### テスト環境準備
- シグナルが有効な状態でテスト実行
- 必要に応じてSignalDisablerを使用
- テストデータの独立性を保つ

### シグナル発火タイミングの制御
```python
# シグナル発火確認のサンプルコード
from django.test import TestCase
from unittest.mock import patch

class SignalTest(TestCase):
    @patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor.process_time_record_change')
    def test_signal_fired(self, mock_process):
        # TimeRecord作成
        TimeRecord.objects.create(...)
        
        # シグナルが発火したことを確認
        self.assertTrue(mock_process.called)
        mock_process.assert_called_once_with(...)
```

### モック・スタブの利用
- 外部依存関係（PaidLeaveAutoProcessor等）の適切なモック化
```python
# PaidLeaveAutoProcessorのモック例
from unittest.mock import Mock, patch

@patch('timeclock.services.paid_leave_auto_processor.PaidLeaveAutoProcessor')
def test_with_mocked_processor(self, MockProcessor):
    mock_instance = MockProcessor.return_value
    mock_instance.process_time_record_change.return_value = []
    
    # テスト実行...
```

### 並行処理テストの実装方法
```python
import threading
from django.test import TransactionTestCase

class ConcurrentSignalTest(TransactionTestCase):
    def test_concurrent_signal_processing(self):
        def create_time_record():
            TimeRecord.objects.create(...)
        
        # 並行実行
        threads = [threading.Thread(target=create_time_record) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # 結果検証...
```

### データベーストランザクション
- 各テストでのロールバック確認
- トランザクションの分離レベル確認

### ログ出力検証
- 適切なログレベルでの出力確認
- エラー時のスタックトレース確認

### 境界値テスト
- None値や不正な型でのシグナル処理
- 大量データでのメモリ使用量

この仕様書に基づいてシグナル処理の包括的なテストを実装し、有給休暇システムの自動処理が確実に動作することを保証します。