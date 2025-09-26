// 申告承認画面のJavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 行クリック機能の初期化
    initializeRowClick();
});

// 行クリック機能の初期化
function initializeRowClick() {
    document.querySelectorAll('.application-row').forEach(row => {
        row.addEventListener('click', function(e) {
            // リンクをクリックした場合は除外
            if (e.target.closest('a') || e.target.matches('a')) {
                return;
            }
            
            // 個別審査画面に遷移
            const applicationId = this.dataset.applicationId;
            if (applicationId) {
                window.location.href = `/salary/admin/applications/${applicationId}/review/`;
            }
        });
        
        // 行にポインタカーソルを設定
        row.style.cursor = 'pointer';
    });
}