# PaidLeaveBalanceManagerクラステスト仕様書

## 概要
本仕様書は、PaidLeaveBalanceManagerクラスの各メソッドに対するテストケースを定義する。
各テストケースでは、設定値と期待される検証結果を明確に定義し、有給休暇残日数管理処理が正確に行われることを検証する。

## テストケース一覧

### 1. 現在残日数取得メソッド（get_current_balance）のテスト

#### テストケース1-1: 付与記録のみの残日数計算
**目的**: 使用履歴がない場合の残日数計算の正確性を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日
- PaidLeaveRecord: 
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
  - 付与11日（grant_date=2024年7月1日、days=11、record_type='grant'）

**検証値と期待結果**:
- 残日数: 21日（10+11）

#### テストケース1-2: 付与と使用記録混在時の残日数計算
**目的**: 付与と使用が混在する場合の残日数計算を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2022年7月1日、days=10、record_type='grant'）
  - 使用3日（grant_date=2022年7月1日、used_date=2022年8月15日、days=3、record_type='use'）
  - 付与11日（grant_date=2023年7月1日、days=11、record_type='grant'）
  - 使用2日（grant_date=2023年7月1日、used_date=2023年9月10日、days=2、record_type='use'）

**検証値と期待結果**:
- 残日数: 16日（10-3+11-2）

#### テストケース1-3: 時効記録を含む残日数計算
**目的**: 時効消滅記録を含む場合の残日数計算を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、days=10、record_type='grant'）
  - 使用2日（grant_date=2020年7月1日、used_date=2020年8月1日、days=2、record_type='use'）
  - 時効8日（grant_date=2020年7月1日、expiry_date=2022年7月1日、days=8、record_type='expire'）
  - 付与11日（grant_date=2021年7月1日、days=11、record_type='grant'）
  - 使用1日（grant_date=2021年7月1日、used_date=2021年8月1日、days=1、record_type='use'）

**検証値と期待結果**:
- 残日数: 10日（10-2-8+11-1）

#### テストケース1-4: 取消記録を含む残日数計算
**目的**: 付与取消記録を含む場合の残日数計算を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
  - 取消5日（grant_date=2023年7月1日、cancellation_date=2023年8月1日、days=5、record_type='cancel'）

**検証値と期待結果**:
- 残日数: 5日（10-5）

#### テストケース1-5: 複雑な記録混在時の残日数計算
**目的**: 全種類の記録が混在する場合の残日数計算を検証
**設定値**:
- ユーザー: 入社日2021年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2021年7月1日、days=10、record_type='grant'）
  - 使用3日（grant_date=2021年7月1日、used_date=2021年8月1日、days=3、record_type='use'）
  - 付与11日（grant_date=2022年7月1日、days=11、record_type='grant'）
  - 使用2日（grant_date=2022年7月1日、used_date=2022年9月1日、days=2、record_type='use'）
  - 時効5日（grant_date=2021年7月1日、expiry_date=2023年7月1日、days=5、record_type='expire'）
  - 付与12日（grant_date=2023年7月1日、days=12、record_type='grant'）
  - 取消3日（grant_date=2023年7月1日、cancellation_date=2023年8月1日、days=3、record_type='cancel'）

**検証値と期待結果**:
- 残日数: 20日（10-3+11-2-5+12-3）

### 2. 詳細残日数情報取得メソッド（get_detailed_balance_info）のテスト

#### テストケース2-1: 単一年度の詳細残日数情報取得
**目的**: 単一付与年度での詳細情報取得を検証
**設定値**:
- 基準日: 2024年9月1日
- ユーザー: 入社日2024年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2024年7月1日、days=10、record_type='grant'）
  - 使用2日（grant_date=2024年7月1日、used_date=2024年8月15日、days=2、record_type='use'）

**検証値と期待結果（DetailedBalanceInfoオブジェクト）**:
- total_balance: 8日
- balance_by_grant_date[0]:
  - grant_date: 2024年7月1日
  - original_days: 10日
  - used_days: 2日
  - remaining_days: 8日
  - expiry_date: 2026年7月1日
  - days_until_expiry: 668日

#### テストケース2-2: 複数年度の詳細残日数情報取得
**目的**: 複数付与年度での詳細情報取得と時効順並び替えを検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2022年7月1日、days=10、record_type='grant'）
  - 使用3日（grant_date=2022年7月1日、used_date=2022年8月1日、days=3、record_type='use'）
  - 付与11日（grant_date=2023年7月1日、days=11、record_type='grant'）
  - 使用2日（grant_date=2023年7月1日、used_date=2023年9月1日、days=2、record_type='use'）

**検証値と期待結果（DetailedBalanceInfoオブジェクト）**:
- total_balance: 16日
- balance_by_grant_date: 2件のGrantDateBalanceオブジェクト（時効が近い順）
  - balance_by_grant_date[0]: 2022年付与分（時効2024年7月1日）
  - balance_by_grant_date[1]: 2023年付与分（時効2025年7月1日）

#### テストケース2-3: 一部使用済み・時効済みを含む詳細情報取得
**目的**: 複雑な使用履歴を持つ場合の詳細情報取得を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日
- PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、days=10、record_type='grant'）
  - 使用3日（grant_date=2020年7月1日、used_date=2020年8月1日、days=3、record_type='use'）
  - 時効7日（grant_date=2020年7月1日、expiry_date=2022年7月1日、days=7、record_type='expire'）
  - 付与11日（grant_date=2021年7月1日、days=11、record_type='grant'）
  - 使用5日（grant_date=2021年7月1日、used_date=2022年1月1日、days=5、record_type='use'）
  - 付与12日（grant_date=2022年7月1日、days=12、record_type='grant'）

**検証値と期待結果**:
- total_balance: 18日（0+6+12）
- balance_by_grant_date: 3件のGrantDateBalanceオブジェクト
  - 2020年付与分: remaining_days=0（全て時効）
  - 2021年付与分: remaining_days=6（11-5）
  - 2022年付与分: remaining_days=12（未使用）

### 3. ユーザー残日数更新メソッド（update_user_balance）のテスト

#### テストケース3-1: 通常のuser.current_paid_leave更新
**目的**: 計算した残日数がユーザーモデルに正しく保存されることを検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=0
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）

**検証値と期待結果**:
- user.current_paid_leave: 10日（データベースに保存済み）
- 戻り値: 10日

#### テストケース3-2: 残日数変更時の更新確認
**目的**: 残日数に変更があった場合の更新処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=10
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
  - 使用3日（grant_date=2023年7月1日、used_date=2023年8月1日、days=3、record_type='use'）

**検証値と期待結果**:
- user.current_paid_leave: 7日（更新後）
- 戻り値: 7日

#### テストケース3-3: 残日数変更なしの場合の処理確認
**目的**: 残日数に変更がない場合でも正しく処理されることを検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=10
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）

**検証値と期待結果**:
- user.current_paid_leave: 10日（変更なし）
- 戻り値: 10日

### 4. 部分取消計算メソッド（calculate_partial_cancellation）のテスト

#### テストケース4-1: 残日数内での部分取消計算
**目的**: 残日数が十分にある場合の部分取消計算を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=10
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
- target_cancel_days: 5日
- target_date: 2023年7月1日

**検証値と期待結果**:
- PaidLeaveRecordの作成（grant_date=2023年7月1日、cancellation_date=2023年8月1日、days=5、record_type='cancel'）
- 戻り値: List[PaidLeaveRecord]（作成された取消記録のリスト）
- user.current_paid_leave: 5日（更新確認）

#### テストケース4-2: 残日数を超える取消要求時の計算
**目的**: 取消要求が残日数を超える場合の処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=10
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
- target_cancel_days: 15日
- target_date: 2023年7月1日

**検証値と期待結果**:
- PaidLeaveRecordの作成（grant_date=2023年7月1日、cancellation_date=2023年8月1日、days=10、record_type='cancel'）
- 戻り値: List[PaidLeaveRecord]（作成された取消記録のリスト）
- user.current_paid_leave: 0日（更新確認）

#### テストケース4-3: 残日数がちょうど0になる場合
**目的**: 取消により残日数がちょうど0になる場合の計算を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=8
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=8、record_type='grant'）
- target_cancel_days: 8日
- target_date: 2023年7月1日

**検証値と期待結果**:
- PaidLeaveRecordの作成（grant_date=2023年7月1日、cancellation_date=2023年8月1日、days=8、record_type='cancel'）
- 戻り値: List[PaidLeaveRecord]（作成された取消記録のリスト）
- user.current_paid_leave: 0日（更新確認）

#### テストケース4-5: 取消要求が0日の場合
**目的**: 取消要求が0日の場合の処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=10
- PaidLeaveRecord:
  - 付与10日（grant_date=2023年7月1日、days=10、record_type='grant'）
- target_cancel_days: 0日
- target_date: 2023年7月1日

**検証値と期待結果**:
- PaidLeaveRecordは作成されない
- 戻り値: []（空のリスト）
- user.current_paid_leave: 10日（変更なし）

## テスト実行時の注意事項

### データベース準備
- 各テストケース実行前に、必要なUserモデル、PaidLeaveRecordを準備する
- テスト用のダミーユーザーを作成し、入社日と週所定労働日数を設定する
- PaidLeaveRecordは適切なrecord_type（'grant', 'use', 'expire', 'cancel'）で作成する

### 日付処理
- テスト実行日に依存しないよう、固定日付を使用する
- タイムゾーンの影響を考慮し、日付のみで判定を行う

### データ整合性
- PaidLeaveRecordのdaysフィールドは正の整数のみを設定する
- record_typeと関連する日付フィールド（grant_date, used_date等）の組み合わせを正しく設定する

### エラーハンドリング
- 異常系のテストでは、適切な例外が発生することを確認する
- データベース接続エラー等の処理も考慮する

### 境界値テスト
- 残日数0日の場合
- 大きな付与日数・使用日数の場合
- マイナス値の扱い（システム上発生しないが堅牢性確認）

### パフォーマンステスト
- 大量のPaidLeaveRecordがある場合の処理速度を検証する
- 複数年にまたがる記録での計算パフォーマンスを確認する

### 統合テスト
- 各メソッドが連携して動作することを確認する
- 実際の残日数管理シナリオを想定した一連の処理をテストする

## 補足事項

### テストデータの管理
- テストデータはフィクスチャとして管理し、再利用可能にする
- 各テストケースは独立して実行可能にする

### モックの利用
- データベースアクセスが不要なテストではモックを使用する
- 日付計算のテストでは固定の基準日を設定する

### 回帰テスト
- 仕様変更時は、既存のテストケースが全て通ることを確認する
- 新規機能追加時は、対応するテストケースを追加する