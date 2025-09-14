document.addEventListener('DOMContentLoaded', function () {
    // プログレスバーのアニメーション
    animateProgressBar();

    // カレンダーの日付クリックイベント（将来の拡張用）
    const calendarDays = document.querySelectorAll('.calendar-day.has-data');
    calendarDays.forEach(day => {
        day.addEventListener('click', function () {
            // 将来的に日別の詳細表示機能を追加可能
            console.log('Day clicked:', this);
        });
    });

    // カレンダーの月切り替え時のアニメーション
    const calendarCard = document.querySelector('.calendar-card');
    if (calendarCard) {
        calendarCard.style.opacity = '0';
        setTimeout(() => {
            calendarCard.style.transition = 'opacity 0.5s ease';
            calendarCard.style.opacity = '1';
        }, 100);
    }

    // サマリーカードの数値アニメーション
    const statsValues = document.querySelectorAll('.animate-value');
    statsValues.forEach(element => {
        const text = element.textContent;
        const match = text.match(/^(\d+)/);
        if (match) {
            const value = parseInt(match[1]);
            const suffix = text.replace(/^\d+/, '');
            element.dataset.suffix = suffix;
            animateValue(element, 0, value, 1000);
        }
    });

    // ツールチップの初期化（Bootstrap 5.3）
    initializeTooltips();
});