# Google Apps Script統合ガイド

## 概要

Renderのcron jobの代わりに、Google Apps Scriptを使用して定期処理を実行する方法です。

## 必要な環境変数

### Django側 (settings.py)

```python
# Cron API用の秘密鍵（32文字以上の推奨）
CRON_API_SECRET = 'your-secure-secret-key-here-32-chars-minimum'
```

## APIエンドポイント

| エンドポイント | 頻度 | 説明 |
|---------------|------|------|
| `/api/cron/paid-leave-grants/` | 毎日午前0時 | 有給休暇の日次付与・時効処理 |
| `/api/cron/cleanup-pins/` | 5分ごと | 期限切れピン留めメッセージ削除 |
| `/api/cron/recalculate-leaderboards/` | 毎日午前2時 | ランキングデータ完全再計算 |
| `/api/cron/health-check/` | 1時間ごと | システム死活監視 |

## Google Apps Script実装例

### 1. スクリプトの作成

```javascript
// Google Apps Scriptのコード

// 設定
const CONFIG = {
  BASE_URL: 'https://motitasu.onrender.com',
  API_SECRET: 'ec710a5db03f41125aa4518267da6a3a0a13763a8db1fdbad47bd434ce01f631'
};

/**
 * HMAC-SHA256署名を生成
 */
function generateSignature(payload, secret) {
  const signature = Utilities.computeHmacSignature(
    Utilities.MacAlgorithm.HMAC_SHA_256,
    payload,
    secret,
    Utilities.Charset.UTF_8
  );
  return signature.map(byte => {
    const hex = (byte & 0xFF).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  }).join('');
}

/**
 * 認証付きAPIリクエストを送信
 */
function sendCronRequest(endpoint, payload = {}) {
  const url = CONFIG.BASE_URL + endpoint;
  const timestamp = new Date().toISOString();
  const payloadStr = JSON.stringify(payload);
  const signaturePayload = payloadStr + timestamp;
  const signature = generateSignature(signaturePayload, CONFIG.API_SECRET);
  
  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Cron-Signature': signature,
      'X-Cron-Timestamp': timestamp
    },
    payload: payloadStr
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const responseData = JSON.parse(response.getContentText());
    
    if (response.getResponseCode() === 200 && responseData.success) {
      console.log(`成功: ${endpoint}`, responseData);
      return responseData;
    } else {
      console.error(`エラー: ${endpoint}`, responseData);
      throw new Error(responseData.error || 'Unknown error');
    }
  } catch (error) {
    console.error(`リクエスト失敗: ${endpoint}`, error);
    throw error;
  }
}

/**
 * 日次有給付与処理
 * トリガー: 毎日午前0時（JST）
 */
function processDailyPaidLeaveGrants() {
  try {
    const result = sendCronRequest('/api/cron/paid-leave-grants/');
    console.log('日次有給付与処理完了:', result.message);
    
    // 結果をスプレッドシートに記録（オプション）
    logToSpreadsheet('有給付与処理', result);
  } catch (error) {
    console.error('日次有給付与処理エラー:', error);
    // エラー通知（オプション）
    sendErrorNotification('日次有給付与処理', error);
  }
}

/**
 * 期限切れピン留め削除処理
 * トリガー: 5分ごと
 */
function cleanupExpiredPins() {
  try {
    const result = sendCronRequest('/api/cron/cleanup-pins/');
    console.log('ピン留め削除処理完了:', result.message);
    
    // 処理があった場合のみログに記録
    if (result.processed_count > 0) {
      logToSpreadsheet('ピン留め削除', result);
    }
  } catch (error) {
    console.error('ピン留め削除処理エラー:', error);
    sendErrorNotification('ピン留め削除処理', error);
  }
}

/**
 * ランキングデータ完全再計算処理
 * トリガー: 毎日午前2時（JST）
 */
function recalculateLeaderboards() {
  try {
    const result = sendCronRequest('/api/cron/recalculate-leaderboards/');
    console.log('ランキング再計算完了:', result.message);
    
    // 処理があった場合のみログに記録
    if (result.processed_count > 0) {
      logToSpreadsheet('ランキング再計算', result);
    }
  } catch (error) {
    console.error('ランキング再計算エラー:', error);
    sendErrorNotification('ランキング再計算処理', error);
  }
}

/**
 * システム死活監視
 * トリガー: 1時間ごと
 */
function healthCheck() {
  try {
    const result = sendCronRequest('/api/cron/health-check/');
    console.log('ヘルスチェック完了:', result.message);
  } catch (error) {
    console.error('ヘルスチェックエラー:', error);
    sendErrorNotification('ヘルスチェック', error);
  }
}

/**
 * 結果をスプレッドシートに記録（オプション）
 */
function logToSpreadsheet(processName, result) {
  const SHEET_ID = 'your-spreadsheet-id'; // スプレッドシートIDを設定
  
  try {
    const sheet = SpreadsheetApp.openById(SHEET_ID).getActiveSheet();
    const timestamp = new Date();
    
    sheet.appendRow([
      timestamp,
      processName,
      result.success ? '成功' : '失敗',
      JSON.stringify(result)
    ]);
  } catch (error) {
    console.error('スプレッドシートログ記録エラー:', error);
  }
}

/**
 * エラー通知（オプション）
 */
function sendErrorNotification(processName, error) {
  // Gmail通知
  try {
    GmailApp.sendEmail(
      'admin@your-domain.com',
      `[Motitasu] ${processName}でエラーが発生`,
      `処理: ${processName}\nエラー: ${error.toString()}\n時刻: ${new Date()}`
    );
  } catch (e) {
    console.error('エラー通知送信失敗:', e);
  }
}
```

### 2. トリガーの設定

Google Apps Scriptエディターで以下のトリガーを設定:

1. **日次有給付与処理**
   - 関数: `processDailyPaidLeaveGrants`
   - イベントソース: 時間主導型
   - 時間ベースのトリガー: 日タイマー
   - 時刻: 午前0時～午前1時

2. **期限切れピン留め削除**
   - 関数: `cleanupExpiredPins`
   - イベントソース: 時間主導型
   - 時間ベースのトリガー: 分ベースのタイマー
   - 間隔: 5分おき

3. **ランキングデータ完全再計算**
   - 関数: `recalculateLeaderboards`
   - イベントソース: 時間主導型
   - 時間ベースのトリガー: 日タイマー
   - 時刻: 午前2時～午前3時

4. **システム死活監視**
   - 関数: `healthCheck`
   - イベントソース: 時間主導型
   - 時間ベースのトリガー: 時間ベースのタイマー
   - 間隔: 1時間おき

## セキュリティ考慮事項

1. **API秘密鍵**
   - 32文字以上の強力なランダム文字列を使用
   - 定期的に更新（月1回推奨）

2. **署名検証**
   - リクエストボディ + タイムスタンプのHMAC-SHA256署名
   - タイムスタンプによるリプレイ攻撃防止（10分以内のリクエストのみ有効）

3. **ログ管理**
   - 成功・失敗の記録
   - エラー発生時の通知機能

## 運用開始手順

1. Django側で`CRON_API_SECRET`を設定
2. Google Apps Scriptプロジェクトを作成
3. 上記のスクリプトをコピー・ペースト
4. `CONFIG`の値を実際の環境に合わせて更新
5. トリガーを設定
6. テスト実行で動作確認

## 監視とアラート

- スプレッドシートによる実行ログ記録
- Gmail通知によるエラーアラート
- Django側のログ出力

## トラブルシューティング

- 署名エラー: API秘密鍵とタイムスタンプを確認
- タイムアウト: Google Apps Scriptの実行時間制限（6分）に注意
- レート制限: APIエンドポイントの呼び出し頻度を調整