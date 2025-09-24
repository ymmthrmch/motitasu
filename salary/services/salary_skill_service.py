from ..models import UserSkill, SkillApplication, UserSalaryGrade, SalaryGrade, Skill


class SalarySkillService:
    """給与・スキル関連のビジネスロジックを提供するサービス"""
    
    def __init__(self, user):
        self.user = user
    
    def get_dashboard_info(self):
        """ダッシュボード表示用の統合情報を取得"""
        return {
            'current_grade_info': self.get_current_grade_info(),
            'acquired_skills': self.get_acquired_skills(),
            'promotion_paths': self.get_promotion_paths(),
            'skill_applications': self.get_skill_applications(),
            'available_skills': self.get_available_skills(),
            'has_salary_grade': self.has_salary_grade()
        }
    
    def get_current_grade_info(self):
        """現在の給与グレード情報を取得"""
        try:
            current_grade = self.user.current_salary_grade
            if current_grade:
                return {
                    'name': current_grade.name,
                    'level': current_grade.level,
                    'hourly_wage': current_grade.hourly_wage,
                    'grade_object': current_grade
                }
        except ValueError:
            # 給与グレード未設定の場合
            pass
        return None
    
    def get_acquired_skills(self):
        """習得済みスキル一覧を取得"""
        user_skills = UserSkill.objects.filter(
            user=self.user
        ).select_related('skill', 'approved_by').order_by('skill__category', 'skill__name')
        
        return [
            {
                'skill': us.skill,
                'acquired_date': us.acquired_date,
                'approved_by': us.approved_by,
                'category': us.skill.get_category_display()
            } for us in user_skills
        ]
    
    def get_promotion_paths(self):
        """昇進可能なルート情報を取得"""
        current_grade_info = self.get_current_grade_info()
        if not current_grade_info:
            return []
        
        current_grade = current_grade_info['grade_object']
        next_grades = current_grade.next_possible_grades.all()
        
        promotion_paths = []
        for grade in next_grades:
            path_info = self._analyze_grade_requirements(grade)
            promotion_paths.append(path_info)
        
        # 完成度順でソート（完成度が高い順）
        promotion_paths.sort(key=lambda x: x['completion_rate'], reverse=True)
        return promotion_paths
    
    def _analyze_grade_requirements(self, target_grade):
        """指定グレードの必要スキルと現在の達成状況を分析"""
        required_skills = target_grade.required_skills.all()
        user_skills = UserSkill.objects.filter(
            user=self.user, 
            skill__in=required_skills
        ).values_list('skill_id', flat=True)
        
        # 申告中のスキルも取得
        pending_skills = SkillApplication.objects.filter(
            user=self.user,
            skill__in=required_skills,
            status='pending'
        ).values_list('skill_id', flat=True)
        
        acquired_skill_ids = set(user_skills)
        pending_skill_ids = set(pending_skills)
        
        skill_status = []
        for skill in required_skills:
            if skill.id in acquired_skill_ids:
                status = 'acquired'
            elif skill.id in pending_skill_ids:
                status = 'pending'
            else:
                status = 'required'
                
            skill_status.append({
                'skill': skill,
                'acquired': skill.id in acquired_skill_ids,
                'pending': skill.id in pending_skill_ids,
                'status': status,
                'category': skill.get_category_display()
            })
        
        completion_rate = 100 * len(acquired_skill_ids) / len(required_skills) if required_skills else 100
        
        return {
            'grade': target_grade,
            'skill_status': skill_status,
            'completion_rate': completion_rate,
            'acquired_count': len(acquired_skill_ids),
            'required_count': len(required_skills),
            'missing_skills': [s for s in skill_status if not s['acquired']]
        }
    
    def get_skill_applications(self):
        """スキル申告状況を取得"""
        applications = SkillApplication.objects.filter(
            user=self.user
        ).select_related('skill', 'processed_by').order_by('-application_date')
        
        pending = []
        history = []
        
        for app in applications:
            app_info = {
                'skill': app.skill,
                'status': app.get_status_display(),
                'application_date': app.application_date,
                'comment': app.comment,
                'processed_by': app.processed_by,
                'processed_date': app.processed_date,
                'category': app.skill.get_category_display()
            }
            
            if app.status == 'pending':
                pending.append(app_info)
            else:
                history.append(app_info)
        
        return {
            'pending': pending,
            'history': history[:10]  # 直近10件
        }
    
    def get_available_skills(self):
        """申告可能なスキル一覧を取得"""
        # 既に習得済みのスキル
        acquired_skill_ids = set(
            UserSkill.objects.filter(user=self.user).values_list('skill_id', flat=True)
        )
        
        # 申告中のスキル
        pending_skill_ids = set(
            SkillApplication.objects.filter(
                user=self.user, status='pending'
            ).values_list('skill_id', flat=True)
        )
        
        # 除外するスキルID
        excluded_skill_ids = acquired_skill_ids | pending_skill_ids
        
        # 申告可能なスキル
        available_skills = Skill.objects.exclude(
            id__in=excluded_skill_ids
        ).order_by('category', 'name')
        
        return list(available_skills)
    
    def has_salary_grade(self):
        """給与グレードが設定されているかチェック"""
        try:
            return self.user.current_salary_grade is not None
        except ValueError:
            return False
    
    def apply_for_skill(self, skill_id, comment=""):
        """スキル習得を申告"""
        skill = Skill.objects.get(id=skill_id)
        
        # 既に習得済みかチェック
        if UserSkill.objects.filter(user=self.user, skill=skill).exists():
            raise ValueError("このスキルは既に習得済みです")
        
        # 申告中かチェック
        if SkillApplication.objects.filter(
            user=self.user, skill=skill, status='pending'
        ).exists():
            raise ValueError("このスキルは既に申告中です")
        
        # 申告を作成
        application = SkillApplication.objects.create(
            user=self.user,
            skill=skill,
            comment=comment
        )
        
        return application
    
    def get_skill_holders(self, skill_id):
        """指定スキルの習得者一覧を取得"""
        skill = Skill.objects.get(id=skill_id)
        holders = UserSkill.objects.filter(
            skill=skill
        ).select_related('user').order_by('acquired_date')
        
        return {
            'skill': skill,
            'holders': [
                {
                    'user': holder.user,
                    'acquired_date': holder.acquired_date
                } for holder in holders
            ]
        }