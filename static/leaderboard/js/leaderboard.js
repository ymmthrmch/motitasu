// leaderboard JavaScript（関数ベース設計）

// メイン初期化関数
function initLeaderboard() {
    const elements = cacheElements();
    bindEvents(elements);
    injectSpinnerStyles();
}

// DOM要素取得
function cacheElements() {
    return {
        joinBtn: document.getElementById('joinBtn'),
        updateBtn: document.getElementById('updateBtn'),
        recalculateBtn: document.getElementById('recalculateBtn')
    };
}

// イベントリスナー設定
function bindEvents(elements) {
    if (elements.joinBtn) {
        elements.joinBtn.addEventListener('click', handleJoin);
    }
    if (elements.updateBtn) {
        elements.updateBtn.addEventListener('click', handleUpdate);
    }
    if (elements.recalculateBtn) {
        elements.recalculateBtn.addEventListener('click', handleRecalculate);
    }
}

// スピナースタイル注入
function injectSpinnerStyles() {
    if (document.getElementById('spinner-styles')) return;

    const style = document.createElement('style');
    style.id = 'spinner-styles';
    style.textContent = `
        .loading {
            opacity: 0.7;
            pointer-events: none;
        }
        .spinning {
            display: inline-block;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// ランキング参加処理
async function handleJoin() {
    // 参加確認ダイアログを表示
    const confirmMessage = 'ランキングに参加しますか？\n\n参加すると今月の労働時間が他の参加者に公開されます。\n一度参加すると取り消すことはできません。';
    
    if (!confirm(confirmMessage)) {
        return; // ユーザーがキャンセルした場合は処理を中断
    }

    setButtonLoading(this, true);

    const start = Date.now();

    try {
        const response = await apiRequest('/leaderboard/api/join/');
        const data = await response.json();

        const elapsed = Date.now() - start;
        // API が早すぎても最低 1 秒はローディング
        if (elapsed < 500) {
            await delay(500 - elapsed);
        }

        if (data.success) {
            showSuccess('ランキングに参加しました！');
            setTimeout(() => location.reload(), 1000);
        } else {
            handleApiError(data);
        }
    } catch (error) {
        console.error('参加エラー:', error);
        showError('ネットワークエラーが発生しました');
    } finally {
        setButtonLoading(this, false);
    }
}

// ランキング更新処理
async function handleUpdate() {
    setButtonLoading(this, true);

    const start = Date.now();

    try {
        const response = await apiRequest('/leaderboard/api/update/');
        const data = await response.json();

        const elapsed = Date.now() - start;
        // API が早すぎても最低 1 秒はローディング
        if (elapsed < 500) {
            await delay(500 - elapsed);
        }

        if (data.success) {
            showSuccess('ランキングを更新しました！');
            setTimeout(() => location.reload(), 1000);
        } else {
            handleApiError(data);
        }
    } catch (error) {
        console.error('更新エラー:', error);
        showError('ネットワークエラーが発生しました');
    } finally {
        setButtonLoading(this, false);
    }
}

// 完全再計算処理（管理者用）
async function handleRecalculate() {
    // 確認ダイアログを表示
    const confirmMessage = '完全再計算を実行しますか？\n\n⚠️ この操作には時間がかかる場合があります\n\n・全参加者のキャッシュデータをリセット\n・月初から現在までの労働時間を再計算\n・ランキングを完全更新\n\n処理中はページを閉じないでください。';
    
    if (!confirm(confirmMessage)) {
        return; // ユーザーがキャンセルした場合は処理を中断
    }

    setButtonLoading(this, true);

    const start = Date.now();

    try {
        const response = await apiRequest('/leaderboard/api/recalculate-from-scratch/');
        const data = await response.json();

        const elapsed = Date.now() - start;
        // 最低 2 秒はローディング（処理時間を考慮）
        if (elapsed < 2000) {
            await delay(2000 - elapsed);
        }

        if (data.success) {
            showSuccess(data.message);
            setTimeout(() => location.reload(), 2000);
        } else {
            showError(data.error || data.message || '完全再計算に失敗しました');
        }
    } catch (error) {
        console.error('完全再計算エラー:', error);
        showError('ネットワークエラーが発生しました');
    } finally {
        setButtonLoading(this, false);
    }
}

// ボタンローディング状態制御
function setButtonLoading(button, isLoading) {
    if (!button) return;

    const icon = button.querySelector('i');

    if (isLoading) {
        button.classList.add('loading');
        if (icon) {
            icon.setAttribute('data-original', icon.className);
            icon.className = 'bi bi-arrow-repeat spinning';
        }
    } else {
        button.classList.remove('loading');
        if (icon && icon.getAttribute('data-original')) {
            icon.className = icon.getAttribute('data-original');
            icon.removeAttribute('data-original');
        }
    }
}

// ローディング演出
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// API共通リクエスト
async function apiRequest(url) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    });
}

// APIエラーハンドリング
function handleApiError(data) {
    if (data.status === 'already_joined') {
        showInfo('既にランキングに参加済みです');
        setTimeout(() => location.reload(), 1000);
    } else if (data.status === 'not_join_period') {
        showError('参加期間外です（毎月1日〜10日）');
    } else {
        showError(data.error || 'エラーが発生しました');
    }
}

// 初期化実行
document.addEventListener('DOMContentLoaded', initLeaderboard);