document.addEventListener('DOMContentLoaded', function() {
    // プログレスバーのアニメーション
    const progressBars = document.querySelectorAll('.progress-bar-dashboard');
    progressBars.forEach(bar => {
        const achievement = parseFloat(bar.getAttribute('data-achievement'));
        if (!isNaN(achievement)) {
            setTimeout(() => {
                const width = Math.min(achievement, 100);
                bar.style.width = width + '%';
            }, 300);
        }
    });
    
    // カレンダーの日付クリックイベント（将来の拡張用）
    const calendarDays = document.querySelectorAll('.calendar-day.has-data');
    calendarDays.forEach(day => {
        day.addEventListener('click', function() {
            // 将来的に日別の詳細表示機能を追加可能
            console.log('Day clicked:', this);
        });
    });
    
    // カレンダーの月切り替え時のアニメーション
    const calendarContainer = document.querySelector('.calendar-container');
    if (calendarContainer) {
        calendarContainer.style.opacity = '0';
        setTimeout(() => {
            calendarContainer.style.transition = 'opacity 0.5s ease';
            calendarContainer.style.opacity = '1';
        }, 100);
    }
    
    // サマリーカードのカウントアップアニメーション
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
    
    // 給与のアニメーション
    const wageElement = document.querySelector('.monthly-wage .amount');
    if (wageElement) {
        const wageText = wageElement.textContent;
        const wageValue = parseInt(wageText.replace(/[^0-9]/g, ''));
        if (!isNaN(wageValue)) {
            wageElement.dataset.suffix = '円';
            animateValue(wageElement, 0, wageValue, 1000);
        }
    }
    
    // 累計統計のアニメーション
    const statsValues = document.querySelectorAll('.all-time .value');
    statsValues.forEach(element => {
        const text = element.textContent;
        const match = text.match(/^(\d+)/);
        if (match) {
            const value = parseInt(match[1]);
            const suffix = text.replace(/^\d+/, '');
            element.dataset.suffix = suffix;
            animateValue(element, 0, value, 800);
        }
    });
    
    // ツールチップの初期化（Bootstrap使用時）
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});