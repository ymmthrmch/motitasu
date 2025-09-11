# PaidLeaveGrantProcessorクラステスト仕様書

## 概要
本仕様書は、PaidLeaveGrantProcessorクラスの各メソッドに対するテストケースを定義する。
各テストケースでは、設定値と期待される検証結果を明確に定義し、有給休暇の付与・取消・時効処理が正確に行われることを検証する。

## テストケース一覧

### 1. 付与処理実行メソッド（execute_grant）のテスト

#### テストケース1-1: 通常の付与処理実行
**目的**: 付与条件を満たす判定結果に基づく正常な付与処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=0
- PaidLeaveJudgment:
  - user: テストユーザー
  - grant_count: 1（付与回数として参照用）
  - judgment_date: 2023年7月1日
  - period_start: 2023年1月1日
  - period_end: 2023年6月30日
  - is_eligible: True
  - grant_days: 10
  - expiry_date: 2025年7月1日
  - description: "付与条件を満たしています"

**検証値と期待結果**:
- 作成されるPaidLeaveRecord:
  - user: テストユーザー
  - record_type: 'grant'
  - grant_date: 2023年7月1日
  - days: 10
  - expiry_date: 2025年7月1日
  - description: "付与条件を満たしています"
- user.current_paid_leave: 10日（更新確認）
- 戻り値: 作成されたPaidLeaveRecordオブジェクト

#### テストケース1-2: 付与不可判定時の処理
**目的**: 付与条件を満たさない判定結果での処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数5日、current_paid_leave=0
- PaidLeaveJudgment:
  - user: テストユーザー
  - grant_count: 1（付与回数として参照用）
  - judgment_date: 2023年7月1日
  - is_eligible: False
  - grant_days: 0
  - description: "出勤率が80%未満のため付与なし"

**検証値と期待結果**:
- PaidLeaveRecordは作成されない
- user.current_paid_leave: 0日（変更なし）
- 戻り値: None

#### テストケース1-3: 2回目以降の付与処理
**目的**: 既に有給残日数がある状態での追加付与処理を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日、current_paid_leave=7
- 既存PaidLeaveRecord: 付与10日（grant_date=2022年7月1日）、使用3日
- PaidLeaveJudgment:
  - grant_count: 2
  - judgment_date: 2023年7月1日
  - is_eligible: True
  - grant_days: 11
  - expiry_date: 2025年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord:
  - grant_date: 2023年7月1日
  - days: 11
  - expiry_date: 2025年7月1日
- user.current_paid_leave: 18日（7+11）
- 戻り値: 作成されたPaidLeaveRecordオブジェクト

#### テストケース1-4: パートタイム労働者の付与処理
**目的**: 比例付与対象者の付与処理を検証
**設定値**:
- ユーザー: 入社日2023年1月1日、週所定労働日数3日、current_paid_leave=0
- PaidLeaveJudgment:
  - grant_count: 1（付与回数として参照用）
  - judgment_date: 2023年7月1日
  - is_eligible: True
  - grant_days: 5
  - expiry_date: 2025年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord:
  - days: 5
  - その他は通常労働者と同様
- user.current_paid_leave: 5日
- 戻り値: 作成されたPaidLeaveRecordオブジェクト

### 2. 取消処理実行メソッド（execute_cancellation）のテスト

#### テストケース2-1: 通常の取消処理実行
**目的**: 未使用の有給に対する取消処理を検証（付与記録の日数減算）
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日、current_paid_leave=10
- 既存PaidLeaveRecord: 付与10日（grant_date=2022年7月1日）※1回目付与日
- 取消パラメータ:
  - target_date: 2022年7月1日（取消対象の付与日）
  - cancellation_days: 10

**検証値と期待結果**:
- 戻り値: List[PaidLeaveRecord]（編集された付与記録のリスト）
- 既存付与記録の変更:
  - 元のdays: 10 → 変更後days: 0（取消処理により減算）
- user.current_paid_leave: 0日（更新確認）

#### テストケース2-2: 部分取消処理の実行
**目的**: 一部使用済みの有給に対する部分取消処理を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日、current_paid_leave=5
- 既存PaidLeaveRecord: 
  - 付与10日（grant_date=2022年7月1日）
  - 使用5日（used_date=2022年8月1日）
- 取消パラメータ:
  - target_date: 2022年7月1日（取消対象の付与日）
  - cancellation_days: 10

**検証値と期待結果**:
- 戻り値: List[PaidLeaveRecord]（編集された付与記録のリスト）
- 既存付与記録の変更:
  - 元のdays: 10 → 変更後days: 5（使用済み分のみ残る）
- user.current_paid_leave: 0日（残日数がマイナスにならない範囲で取消）

#### テストケース2-3: 残日数不足時の部分取消処理
**目的**: 取消対象より現在残日数が少ない場合の処理を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日、current_paid_leave=3
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2022年7月1日）
  - 使用7日
- 取消パラメータ:
  - grant_date: 2022年7月1日（1回目付与を取消）
  - cancellation_date: 2022年9月1日
  - description: "再判定により"

**検証値と期待結果**:
- CancellationResult:
  - grant_date: 2022年7月1日（取消対象の付与日）
  - target_cancel_days: 10
  - actual_cancelled_days: 3
  - remaining_balance: 0
  - was_partial: True
- 作成されるPaidLeaveRecord:
  - days: 3
- user.current_paid_leave: 0日

#### テストケース2-4: 既に全て使用済みの有給の取消処理
**目的**: 残日数が0の状態での取消処理を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日、current_paid_leave=0
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2022年7月1日）
  - 使用10日（全て使用済み）
- 取消パラメータ:
  - grant_date: 2022年7月1日（1回目付与を取消）
  - cancellation_date: 2022年9月1日
  - description: "再判定により"

**検証値と期待結果**:
- CancellationResult:
  - grant_date: 2022年7月1日（取消対象の付与日）
  - target_cancel_days: 10
  - actual_cancelled_days: 0
  - remaining_balance: 0
  - was_partial: True
- PaidLeaveRecord（取消）は作成されない
- user.current_paid_leave: 0日（変更なし）

#### テストケース2-5: 複数年度の付与がある場合の特定回取消
**目的**: 複数年度の付与がある中で特定回のみを取り消す処理を検証
**設定値**:
- ユーザー: 入社日2021年1月1日、週所定労働日数5日、current_paid_leave=18
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2021年7月1日）、使用2日
  - 付与11日（grant_date=2022年7月1日）、使用1日
- 取消パラメータ:
  - grant_date: 2021年7月1日（1回目のみ取消）
  - cancellation_date: 2022年9月1日
  - description: "再判定により"

**検証値と期待結果**:
- CancellationResult:
  - grant_date: 2021年7月1日（取消対象の付与日）
  - target_cancel_days: 10
  - actual_cancelled_days: 8（10-2）
  - remaining_balance: 10（18-8）
  - was_partial: True
- user.current_paid_leave: 10日

### 3. 時効処理実行メソッド（process_expiration）のテスト

#### テストケース3-1: 単一の時効処理
**目的**: 期限切れの有給1件に対する時効処理を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、expiry_date=2022年7月1日）
  - 使用2日（used_date=2020年8月1日）
- target_date: 2022年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord:
  - record_type: 'expire'
  - days: 8（10-2）
  - expiry_date: 2022年7月1日
  - description: "有効期限による時効消滅"
- user.current_paid_leave: 0日（8日分が時効）
- 戻り値: [作成された時効記録のPaidLeaveRecord]

#### テストケース3-2: 複数の時効処理
**目的**: 複数の期限切れ有給に対する一括時効処理を検証
**設定値**:
- ユーザー: 入社日2019年1月1日、週所定労働日数5日
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2019年7月1日、expiry_date=2021年7月1日）、使用3日
  - 付与11日（grant_date=2020年7月1日、expiry_date=2022年7月1日）、使用1日
- target_date: 2022年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord: 2件
  - 1件目: grant_date=2019年7月1日, days=7（10-3）
  - 2件目: grant_date=2020年7月1日, days=10（11-1）
- user.current_paid_leave: 0日（17日分が時効）
- 戻り値: [2件のPaidLeaveRecordリスト]

#### テストケース3-3: 時効対象がない場合の処理
**目的**: 期限切れの有給がない場合の処理を検証
**設定値**:
- ユーザー: 入社日2022年1月1日、週所定労働日数5日
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2022年7月1日、expiry_date=2024年7月1日）
- target_date: 2023年7月1日

**検証値と期待結果**:
- PaidLeaveRecordは作成されない
- user.current_paid_leave: 10日（変更なし）
- 戻り値: []（空のリスト）

#### テストケース3-4: 部分的に使用済みの有給の時効処理
**目的**: 一部使用済みの有給の時効処理を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、expiry_date=2022年7月1日）
  - 使用6日（複数回に分けて使用）
- target_date: 2022年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord:
  - record_type: 'expire'
  - days: 4（10-6）
- user.current_paid_leave: 0日（4日分が時効）
- 戻り値: [作成された時効記録]

#### テストケース3-5: 既に全て使用済みの有給の時効処理
**目的**: 残日数が0の有給に対する時効処理を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、expiry_date=2022年7月1日）
  - 使用10日（全て使用済み）
- target_date: 2022年7月1日

**検証値と期待結果**:
- PaidLeaveRecord（時効）は作成されない
- user.current_paid_leave: 0日（変更なし）
- 戻り値: []（空のリスト）

#### テストケース3-6: 複数年度で一部のみ時効の場合
**目的**: 複数年度の付与があり一部のみが時効対象の場合を検証
**設定値**:
- ユーザー: 入社日2020年1月1日、週所定労働日数5日、current_paid_leave=0
- 既存PaidLeaveRecord:
  - 付与10日（grant_date=2020年7月1日、expiry_date=2022年7月1日）、使用3日
  - 付与11日（grant_date=2021年7月1日、expiry_date=2023年7月1日）、使用2日
- target_date: 2022年7月1日

**検証値と期待結果**:
- 作成されるPaidLeaveRecord: 1件（2020年付与分のみ）
  - days: 7（10-3）
- user.current_paid_leave: 9日（16-7）
- 戻り値: [1件のPaidLeaveRecord]

## テスト実行時の注意事項

### データベース準備
- 各テストケース実行前に、必要なUserモデル、PaidLeaveRecordを準備する
- テスト用のダミーユーザーを作成し、入社日と週所定労働日数を設定する
- PaidLeaveRecordは適切なrecord_type（'grant', 'use', 'expire', 'cancel'）で作成する

### 日付処理
- テスト実行日に依存しないよう、固定日付を使用する
- タイムゾーンの影響を考慮し、日付のみで判定を行う
- 有効期限計算は付与日から2年後を正確に計算する

### データ整合性確認
- 作成されたPaidLeaveRecordの全フィールドが正しく設定されていることを確認
- user.current_paid_leaveの更新が正しく行われることを確認
- データベースへの保存が正常に完了することを確認

### エラーハンドリング
- 存在しないgrant_dateに対する取消要求のエラー処理
- データベース制約違反時の適切なエラーハンドリング
- トランザクション処理の確認（失敗時のロールバック）

### 境界値テスト
- 残日数ちょうど0の場合の処理
- 付与日数・使用日数が最大値の場合
- 同日に複数の処理が実行される場合

### パフォーマンステスト
- 大量のPaidLeaveRecordがある場合の処理速度
- 複数年度の処理での効率性確認

### 統合テスト
- PaidLeaveBalanceManagerとの連携動作確認
- シグナル処理との統合確認
- 実際の付与・取消・時効シナリオでの一連の処理テスト

## 補足事項

### テストデータの管理
- フィクスチャを活用してテストデータを管理
- 各テストケースの独立性を保つ

### モックの利用
- 外部依存関係（日付取得等）はモックを使用
- データベーストランザクションのテスト

### 回帰テスト
- 仕様変更時の既存テスト確認
- 新機能追加時のテストケース追加

### ログとデバッグ
- 処理過程のログ出力確認
- エラー発生時のスタックトレース検証