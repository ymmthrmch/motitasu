// 管理ダッシュボードのJavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    function animateCountUp(element, target, duration) {
        const start = 0;
        const increment = target / (duration / 16); // 60fps想定
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, 16);
    }
    
    // === スキル・グレードマップのスムーススクロール ===
    const mapContainers = document.querySelectorAll('.skills-map, .grades-map');
    
    mapContainers.forEach(container => {
        // マウスホイールでの横スクロールサポート
        container.addEventListener('wheel', function(e) {
            if (e.deltaY !== 0) {
                e.preventDefault();
                this.scrollTop += e.deltaY;
            }
        });
    });
    
    // === 活動ログのリアルタイム更新 ===
    const activityLog = document.querySelector('.activity-log');
    
    if (activityLog) {
        // 定期的に新しい活動をチェック（5分ごと）
        setInterval(refreshActivityLog, 5 * 60 * 1000);
    }
    
    function refreshActivityLog() {
        // 実際の実装では、APIから最新の活動ログを取得してDOMを更新
        // 現在はコメントアウト - 必要に応じて実装
        /*
        fetch('/salary/admin/api/recent-activities/')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' && data.activities) {
                    updateActivityLog(data.activities);
                }
            })
            .catch(error => console.log('Activity log update failed:', error));
        */
    }
    
    // === 承認待ち通知の点滅効果 ===
    const pendingCard = document.querySelector('.card-header-warning');
    const pendingCount = document.querySelector('.display-info.warning');
    
    if (pendingCard && pendingCount && parseInt(pendingCount.textContent) > 0) {
        // 承認待ちがある場合、定期的に注意を促す
        setInterval(() => {
            pendingCard.style.animation = 'pulse 0.5s ease-in-out';
            setTimeout(() => {
                pendingCard.style.animation = '';
            }, 500);
        }, 10000); // 10秒ごと
    }
    
    // === ツールチップの初期化 ===
    const avatars = document.querySelectorAll('.user-avatar[title]');
    
    avatars.forEach(avatar => {
        // Bootstrap tooltipがある場合は初期化
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            new bootstrap.Tooltip(avatar);
        }
    });
    
    // === クイックアクションボタンのキーボードショートカット ===
    document.addEventListener('keydown', function(e) {
        // Ctrl + 数字キーでクイックアクション
        if (e.ctrlKey && e.key >= '1' && e.key <= '4') {
            e.preventDefault();
            const quickActions = document.querySelectorAll('.quick-actions .btn-gradient-primary, .quick-actions .btn-gradient-success, .quick-actions .btn-gradient-info, .quick-actions .btn-gradient-warning');
            const index = parseInt(e.key) - 1;
            
            if (quickActions[index]) {
                quickActions[index].click();
            }
        }
    });
    
    // === パフォーマンス監視 ===
    if (performance && performance.mark) {
        performance.mark('dashboard-load-complete');
        console.log('Dashboard loaded successfully');
    }
});