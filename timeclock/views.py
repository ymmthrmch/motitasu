from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from zoneinfo import ZoneInfo
import calendar
from datetime import datetime, date, timedelta
from dataclasses import asdict
from .models import TimeRecord, MonthlyTarget
from .services import WorkTimeService
from .services.paid_leave_calculator import PaidLeaveCalculator
from .services.paid_leave_balance_manager import PaidLeaveBalanceManager
from leaderboard.models import LeaderboardEntry
from leaderboard.services.leaderboard_service import LeaderboardService
from salary.services.salary_skill_service import SalarySkillService

@login_required
def timeclock(request):
    jst = ZoneInfo(settings.TIME_ZONE)
    now_jst = timezone.now().astimezone(jst)
    today_start = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timezone.timedelta(days=1)
    
    today_records = TimeRecord.objects.filter(
        user=request.user,
        timestamp__gte=today_start,
        timestamp__lt=today_end
    ).order_by('timestamp')
    
    last_record = today_records.last()
    
    available_actions = []
    if not today_records.filter(clock_type='clock_in').exists():
        available_actions.append('clock_in')
    elif today_records.filter(clock_type='clock_out').exists():
        pass
    elif last_record:
        if last_record.clock_type == 'clock_in':
            available_actions.extend(['break_start', 'clock_out'])
        elif last_record.clock_type == 'break_start':
            available_actions.append('break_end')
        elif last_record.clock_type == 'break_end':
            available_actions.extend(['break_start', 'clock_out'])
    
    # 退勤済みの場合、成果情報を計算
    work_summary = None
    if last_record and last_record.clock_type == 'clock_out':
        service = WorkTimeService(request.user)
        daily_summary = service.get_daily_summary()
        monthly_summary = service.get_monthly_summary()
        
        if not daily_summary['error']:
            work_time_str = service.format_timedelta(daily_summary['work_time'])
            
            work_summary = {
                'work_time': work_time_str,
                'wage': daily_summary['wage'],
                'achievement_rate': monthly_summary['achievement_rate'],
                'total_wage': monthly_summary['total_wage'],
                'target_income': monthly_summary['target_income'],
            }
            
            try:
                year = now_jst.year
                month = now_jst.month
                entry = LeaderboardEntry.objects.get(user=request.user, year=year, month=month)
                all_entries = LeaderboardEntry.objects.filter(year=year, month=month)
                work_summary['leaderboard'] = {
                    'rank': entry.rank,
                    'all_entries': len(all_entries)
                    }
            except LeaderboardEntry.DoesNotExist:
                pass
    
    context = {
        'today_records': today_records,
        'available_actions': available_actions,
        'current_time': now_jst.strftime('%Y-%m-%d %H:%M:%S'),
        'last_record': last_record,
        'work_summary': work_summary,
    }
    
    return render(request, 'timeclock/timeclock.html', context)

@login_required
@require_POST
def clock_action(request):
    action_type = request.POST.get('action_type')
    user = request.user
    
    if not action_type:
        messages.error(request, '打刻タイプが指定されていません。')
        return redirect('timeclock')
    
    try:
        from .signals import handle_time_record_save, handle_time_record_delete
        
        # 打刻時はシグナル無効化（リアルタイム処理では再判定を行わない）
        handle_time_record_save._disabled = True
        handle_time_record_delete._disabled = True
        
        try:
            jst = ZoneInfo(settings.TIME_ZONE)
            timestamp = timezone.now().astimezone(jst)
            
            record = TimeRecord(
                user=user,
                clock_type=action_type,
                timestamp=timestamp
            )
            record.save()
            
        finally:
            # シグナルを再有効化
            handle_time_record_save._disabled = False
            handle_time_record_delete._disabled = False

        if action_type == 'clock_out':
            try:
                year = timestamp.year
                month = timestamp.month
                entry = LeaderboardEntry.objects.get(user=user, year=year, month=month)
                service = LeaderboardService(user)
                service.update_user_stats(year, month)
                service.update_leaderboard(year, month)
            except LeaderboardEntry.DoesNotExist:
                pass
            except Exception:
                pass
            
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e.messages[0]))
    except Exception:
        messages.error(request, '打刻に失敗しました')
    
    return redirect('timeclock:timeclock')

def get_current_time(request):
    jst = ZoneInfo(settings.TIME_ZONE)
    now_jst = timezone.now().astimezone(jst)
    return JsonResponse({
        'time': now_jst.strftime('%H:%M:%S'),
        'date': now_jst.strftime('%Y年%m月%d日'),
        'datetime': now_jst.strftime('%Y-%m-%d %H:%M:%S')
    })

@login_required
def dashboard(request):
    """個人の勤務状況ダッシュボード"""
    jst = ZoneInfo(settings.TIME_ZONE)
    now = timezone.now().astimezone(jst)
    
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    service = WorkTimeService(request.user)
    
    monthly_summary = service.get_monthly_summary(year, month)
    
    cal = calendar.monthcalendar(year, month)
    
    daily_data = {}
    for daily in monthly_summary['daily_summaries']:
        day = daily['date'].day
        daily_data[day] = {
            'work_hours': daily['work_hours'],
            'wage': daily['wage'],
            'has_clock_out': daily['has_clock_out']
        }
    
    calendar_weeks = []
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                day_data = daily_data.get(day, {})
                week_data.append({
                    'day': day,
                    'work_hours': day_data.get('work_hours', 0),
                    'wage': day_data.get('wage', 0),
                    'has_data': day in daily_data,
                    'is_today': (year == now.year and month == now.month and day == now.day),
                    'has_clock_out': day_data.get('has_clock_out', False)
                })
        calendar_weeks.append(week_data)
    
    if month == 1:
        prev_month = {'year': year - 1, 'month': 12}
        next_month = {'year': year, 'month': 2}
    elif month == 12:
        prev_month = {'year': year, 'month': 11}
        next_month = {'year': year + 1, 'month': 1}
    else:
        prev_month = {'year': year, 'month': month - 1}
        next_month = {'year': year, 'month': month + 1}
    
    if next_month['year'] > now.year or (next_month['year'] == now.year and next_month['month'] > now.month):
        next_month = None
    
    all_time_stats = get_all_time_stats(request.user)
    
    # 有給休暇情報を取得（入社日が設定されている場合のみ）
    paid_leave_status = {}
    
    if request.user.hire_date:
        try:
            balance_manager = PaidLeaveBalanceManager(request.user)
            paid_leave_balance_info = balance_manager.get_detailed_balance_info()
            
            # 次回の有給付与予定を計算
            calculator = PaidLeaveCalculator(request.user)
            next_grant_info = calculator.get_next_grant_info()

            # dataclassを辞書に変換してから結合
            if paid_leave_balance_info:
                paid_leave_status.update(asdict(paid_leave_balance_info))
            if next_grant_info:
                paid_leave_status.update(asdict(next_grant_info))
            
            paid_leave_status['hire_date_missing'] = False
        except Exception:
            # 有給休暇計算でエラーが発生した場合
            paid_leave_status['hire_date_missing'] = True
    else:
        paid_leave_status['hire_date_missing'] = True
    
    # 給与・スキル情報を取得
    salary_skill_service = SalarySkillService(request.user)
    salary_skill_info = salary_skill_service.get_dashboard_info()
    
    # 現在月かどうかを判定
    is_current_month = (year == now.year and month == now.month)
    
    context = {
        'year': year,
        'month': month,
        'calendar_weeks': calendar_weeks,
        'monthly_summary': monthly_summary,
        'prev_month': prev_month,
        'next_month': next_month,
        'all_time_stats': all_time_stats,
        'weekdays': ['月', '火', '水', '木', '金', '土', '日'],
        'paid_leave_status': paid_leave_status,
        'salary_skill_info': salary_skill_info,
        'is_current_month': is_current_month
    }
    
    return render(request, 'timeclock/dashboard.html', context)

def get_all_time_stats(user):
    """全期間の勤務統計を取得"""
    jst = ZoneInfo(settings.TIME_ZONE)
    
    # 最初の打刻記録を取得
    first_record = TimeRecord.objects.filter(
        user=user,
        clock_type='clock_in'
    ).order_by('timestamp').first()
    
    if not first_record:
        return {
            'total_days': 0,
            'total_hours': 0,
            'total_wage': 0,
            'start_date': None
        }
    
    start_date = first_record.timestamp.astimezone(jst).date()
    today = timezone.now().astimezone(jst).date()
    
    service = WorkTimeService(user)
    total_hours = 0
    total_wage = 0
    work_days = 0
    
    # 各日の統計を集計
    current_date = start_date
    while current_date <= today:
        daily = service.get_daily_summary(current_date)
        if daily['work_hours'] > 0:
            total_hours += daily['work_hours']
            total_wage += daily['wage']
            work_days += 1
        current_date += timedelta(days=1)
    
    return {
        'total_days': work_days,
        'total_hours': round(total_hours, 1),
        'total_wage': total_wage,
        'start_date': start_date
    }


@login_required
@require_POST
def set_monthly_target(request):
    """月収目標を設定するAPI"""
    try:
        year = int(request.POST.get('year', 0))
        month = int(request.POST.get('month', 0))
        target_income = int(request.POST.get('target_income', 0))
        
        if not (1 <= month <= 12):
            return JsonResponse({
                'success': False,
                'message': '月は1から12の間で入力してください。'
            })
        
        if target_income <= 0:
            return JsonResponse({
                'success': False,
                'message': '目標月収は正の値で入力してください。'
            })
        
        # 既存の目標があれば更新、なければ作成
        monthly_target, created = MonthlyTarget.objects.update_or_create(
            user=request.user,
            year=year,
            month=month,
            defaults={'target_income': target_income}
        )
        
        action = '作成' if created else '更新'
        return JsonResponse({
            'success': True,
            'message': f'{year}年{month}月の目標月収を{action}しました。',
            'target': {
                'year': monthly_target.year,
                'month': monthly_target.month,
                'target_income': monthly_target.target_income,
            }
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'message': '入力値が正しくありません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'エラーが発生しました。再度お試しください。'
        })