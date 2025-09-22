// ベース機能のJavaScript

// ログアウト確認ダイアログ
function initLogoutConfirmation() {
    const logoutBtn = document.getElementById('logoutBtn');
    const logoutForm = document.getElementById('logoutForm');
    
    if (logoutBtn && logoutForm) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const confirmMessage = 'ログアウトしますか？\n\n現在の作業は保存されていることを確認してください。';
            
            if (confirm(confirmMessage)) {
                logoutForm.submit();
            }
        });
    }
}

// 初期化
document.addEventListener('DOMContentLoaded', function() {
    initLogoutConfirmation();
});