// timeclock共通ユーティリティ関数

/**
 * プログレスバーのアニメーション
 */
function animateProgressBar() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const achievement = parseFloat(bar.getAttribute('data-achievement'));
        if (!isNaN(achievement)) {
            setTimeout(() => {
                const width = Math.min(achievement, 100);
                bar.style.width = width + '%';
            }, 100);
        }
    });
}

/**
 * 数値のアニメーション表示
 */
function animateValue(element, start, end, duration) {
    if (!element) return;

    const startTimestamp = Date.now();
    const step = () => {
        const timestamp = Date.now();
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const current = Math.floor(progress * (end - start) + start);
        element.textContent = current.toLocaleString() + (element.dataset.suffix || '');
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

/**
 * ツールチップの初期化（Bootstrap 5.3）
 */
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

/**
 * 長押しイベントリスナーを追加
 * @param {HTMLElement} element - 対象要素
 * @param {Function} callback - 長押し時に実行する関数
 * @param {number} duration - 長押し判定時間（ミリ秒、デフォルト500ms）
 */
function addLongPressListener(element, callback, duration = 500) {
    let pressTimer;
    let isLongPress = false;
    
    const start = (e) => {
        // 既にタイマーが動いている場合はクリア
        if (pressTimer) {
            clearTimeout(pressTimer);
        }
        
        isLongPress = false;
        
        // 長押しタイマー開始
        pressTimer = setTimeout(() => {
            isLongPress = true;
            // 振動フィードバック（対応デバイスのみ）
            if (navigator.vibrate) {
                navigator.vibrate(50);
            }
            // 長押し時のコールバック実行
            callback.call(element, e);
        }, duration);
        
        // 視覚的フィードバック用のクラス追加
        element.classList.add('pressing');
    };
    
    const cancel = () => {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
        isLongPress = false;
        // 視覚的フィードバック用のクラス削除
        element.classList.remove('pressing');
    };
    
    // マウスイベント
    element.addEventListener('mousedown', start);
    element.addEventListener('mouseup', cancel);
    element.addEventListener('mouseleave', cancel);
    
    // タッチイベント（モバイル対応）
    element.addEventListener('touchstart', (e) => {
        // タッチイベントの場合、マウスイベントも発火するのを防ぐ
        e.preventDefault();
        start(e);
    });
    element.addEventListener('touchend', cancel);
    element.addEventListener('touchcancel', cancel);
    
    // 通常のクリックを無効化（長押しのみ有効にする場合）
    element.addEventListener('click', (e) => {
        if (!isLongPress) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
    
    // 右クリックメニューを無効化
    element.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });
}

/**
 * テンプレート文字列の変数を置換
 * @param {string} template - テンプレート文字列（例: "{{ name }}さん、こんにちは"）
 * @param {object} data - 置換するデータ（例: {name: "太郎"}）
 * @returns {string} 置換後の文字列
 */
function replaceTemplate(template, data) {
    return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key) => {
        return data.hasOwnProperty(key) ? data[key] : match;
    });
}

// HTMLエスケープ
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// CSRFトークンを取得
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

// 成功メッセージを表示
function showSuccess(message) {
    showNotification(message, 'success');
}

// エラーメッセージを表示
function showError(message) {
    showNotification(message, 'error');
}

// 通知を表示
function showNotification(message, type) {
    // 既存の通知があれば削除
    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    let alertClass = 'danger'; // デフォルト
    if (type === 'success') alertClass = 'success';
    else if (type === 'info') alertClass = 'info';
    
    const notification = document.createElement('div');
    notification.className = `notification alert alert-${alertClass} alert-dismissible fade show`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    
    notification.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // 5秒後に自動で削除
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * 文字数カウンター機能
 * @param {HTMLTextAreaElement} textarea - 対象のテキストエリア
 * @param {HTMLElement} counter - カウンター表示要素
 * @param {HTMLButtonElement} submitBtn - 送信ボタン（任意）
 * @param {number} maxLength - 最大文字数（デフォルト200）
 */
function updateCharacterCounter(textarea, counter, submitBtn = null, maxLength = 200) {
    const currentLength = textarea.value.length;
    
    counter.textContent = `${currentLength}/${maxLength}文字`;
    
    // スタイル更新
    counter.classList.remove('warning', 'danger');
    if (currentLength > maxLength) {
        counter.classList.add('danger');
    } else if (currentLength > maxLength * 0.9) {
        counter.classList.add('warning');
    }
    
    // 送信ボタンの状態更新（ボタンが指定されている場合）
    if (submitBtn) {
        submitBtn.disabled = currentLength === 0 || currentLength > maxLength;
    }
}