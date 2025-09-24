from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from .models import Skill, SkillApplication, UserSkill
from .services.salary_skill_service import SalarySkillService


@login_required
def skill_detail_api(request, skill_id):
    """スキル詳細情報をJSON形式で返すAPI"""
    try:
        service = SalarySkillService(request.user)
        skill_data = service.get_skill_holders(skill_id)
        
        # スキルの状態を判定
        skill_obj = skill_data['skill']
        
        # 習得済みかチェック
        user_skill = UserSkill.objects.filter(user=request.user, skill=skill_obj).first()
        is_acquired = user_skill is not None
        
        # 申告中かチェック
        pending_application = SkillApplication.objects.filter(
            user=request.user, 
            skill=skill_obj, 
            status='pending'
        ).first()
        is_pending = pending_application is not None
        
        # 申告可能かチェック
        available_skills = service.get_available_skills()
        can_apply = any(skill.id == skill_id for skill in available_skills)
        
        # レスポンスデータ構築
        response_data = {
            'skill': {
                'id': skill_data['skill'].id,
                'name': skill_data['skill'].name,
                'description': skill_data['skill'].description,
                'category': skill_data['skill'].get_category_display(),
            },
            'holders': [
                {
                    'user': {
                        'name': holder['user'].name
                    },
                    'acquired_date': holder['acquired_date'].strftime('%Y年%m月%d日')
                } for holder in skill_data['holders']
            ],
            'can_apply': can_apply,
            'is_acquired': is_acquired,
            'is_pending': is_pending,
            'acquired_date': user_skill.acquired_date.strftime('%Y年%m月%d日') if user_skill else None,
            'application_date': pending_application.application_date.strftime('%Y年%m月%d日') if pending_application else None
        }
        
        return JsonResponse(response_data)
        
    except Skill.DoesNotExist:
        return JsonResponse({
            'error': 'スキルが見つかりません'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': 'エラーが発生しました'
        }, status=500)


@login_required
@require_POST
def apply_skill_api(request):
    """スキル習得申告API"""
    try:
        data = json.loads(request.body)
        skill_id = data.get('skill_id')
        comment = data.get('comment', '')
        
        if not skill_id:
            return JsonResponse({
                'error': 'スキルIDが指定されていません'
            }, status=400)
        
        service = SalarySkillService(request.user)
        application = service.apply_for_skill(skill_id, comment)
        
        return JsonResponse({
            'success': True,
            'message': 'スキル習得を申告しました。承認をお待ちください。',
            'application_id': application.id
        })
        
    except ValueError as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': 'エラーが発生しました'
        }, status=500)
