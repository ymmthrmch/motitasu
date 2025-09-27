// 給与グレード作成・編集フォーム用JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('gradeCreateForm') || document.getElementById('gradeEditForm');
    const availableSkills = document.getElementById('availableSkills');
    const selectedSkills = document.getElementById('selectedSkills');
    const availableGrades = document.getElementById('availableGrades');
    const selectedGrades = document.getElementById('selectedGrades');
    const addSkillBtn = document.getElementById('addSkillBtn');
    const removeSkillBtn = document.getElementById('removeSkillBtn');
    const addGradeBtn = document.getElementById('addGradeBtn');
    const removeGradeBtn = document.getElementById('removeGradeBtn');

    // 編集画面の場合、既選択項目を右側に移動
    if (form.id === 'gradeEditForm') {
        initializeEditMode();
    }

    // スキル移動機能
    addSkillBtn.addEventListener('click', function() {
        moveSelectedOptions(availableSkills, selectedSkills);
    });

    removeSkillBtn.addEventListener('click', function() {
        moveSelectedOptions(selectedSkills, availableSkills);
    });

    // グレード移動機能
    addGradeBtn.addEventListener('click', function() {
        moveSelectedOptions(availableGrades, selectedGrades);
    });

    removeGradeBtn.addEventListener('click', function() {
        moveSelectedOptions(selectedGrades, availableGrades);
    });

    // ダブルクリックでも移動可能にする
    availableSkills.addEventListener('dblclick', function() {
        moveSelectedOptions(availableSkills, selectedSkills);
    });

    selectedSkills.addEventListener('dblclick', function() {
        moveSelectedOptions(selectedSkills, availableSkills);
    });

    availableGrades.addEventListener('dblclick', function() {
        moveSelectedOptions(availableGrades, selectedGrades);
    });

    selectedGrades.addEventListener('dblclick', function() {
        moveSelectedOptions(selectedGrades, availableGrades);
    });

    // オプション移動の共通関数
    function moveSelectedOptions(fromSelect, toSelect) {
        const selectedOptions = Array.from(fromSelect.selectedOptions);
        selectedOptions.forEach(option => {
            toSelect.appendChild(option);
            option.selected = false;
        });
        sortSelectOptions(toSelect);
    }

    // セレクトボックスのソート
    function sortSelectOptions(selectElement) {
        const options = Array.from(selectElement.options);
        options.sort((a, b) => a.text.localeCompare(b.text));
        selectElement.innerHTML = '';
        options.forEach(option => selectElement.appendChild(option));
    }

    // 編集画面初期化（既存の選択項目を右側に移動）
    function initializeEditMode() {
        // データ属性またはwindowオブジェクトから既存データを取得
        const existingSkillIds = getExistingData('required-skills') || window.existingRequiredSkills || [];
        const existingGradeIds = getExistingData('next-grades') || window.existingNextGrades || [];

        // 既存の必要スキルを右側に移動
        existingSkillIds.forEach(skillId => {
            const option = availableSkills.querySelector(`option[value="${skillId}"]`);
            if (option) {
                selectedSkills.appendChild(option);
            }
        });

        // 既存の昇進先グレードを右側に移動
        existingGradeIds.forEach(gradeId => {
            const option = availableGrades.querySelector(`option[value="${gradeId}"]`);
            if (option) {
                selectedGrades.appendChild(option);
            }
        });

        sortSelectOptions(selectedSkills);
        sortSelectOptions(selectedGrades);
    }

    // 既存データを取得する関数（data属性から）
    function getExistingData(dataKey) {
        const container = document.querySelector('[data-' + dataKey + ']');
        if (container) {
            const dataStr = container.getAttribute('data-' + dataKey);
            try {
                return JSON.parse(dataStr);
            } catch (e) {
                console.warn('Failed to parse existing data:', dataStr);
                return [];
            }
        }
        return null;
    }

    // フォーム送信時にhiddenフィールドに値を設定
    form.addEventListener('submit', function(e) {
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // hiddenフィールドに値を設定
        const requiredSkillsField = document.getElementById('id_required_skills');
        const nextGradesField = document.getElementById('id_next_possible_grades');
        
        // 隠しフィールドがselectタイプかinputタイプかを判定して適切に値を設定
        if (requiredSkillsField) {
            if (requiredSkillsField.tagName === 'SELECT') {
                // selectタイプの場合は全オプションをクリアして新しく追加
                requiredSkillsField.innerHTML = '';
                Array.from(selectedSkills.options).forEach(option => {
                    const newOption = document.createElement('option');
                    newOption.value = option.value;
                    newOption.selected = true;
                    requiredSkillsField.appendChild(newOption);
                });
            } else {
                // inputタイプの場合はカンマ区切りで値を設定
                const skillIds = Array.from(selectedSkills.options).map(option => option.value);
                requiredSkillsField.value = skillIds.join(',');
            }
        }

        if (nextGradesField) {
            if (nextGradesField.tagName === 'SELECT') {
                // selectタイプの場合は全オプションをクリアして新しく追加
                nextGradesField.innerHTML = '';
                Array.from(selectedGrades.options).forEach(option => {
                    const newOption = document.createElement('option');
                    newOption.value = option.value;
                    newOption.selected = true;
                    nextGradesField.appendChild(newOption);
                });
            } else {
                // inputタイプの場合はカンマ区切りで値を設定
                const gradeIds = Array.from(selectedGrades.options).map(option => option.value);
                nextGradesField.value = gradeIds.join(',');
            }
        }
        
        // 二重送信防止
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 保存中...';
        
        // フォームエラーがあれば再有効化
        setTimeout(() => {
            if (document.querySelector('.text-danger')) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }, 100);
    });
});