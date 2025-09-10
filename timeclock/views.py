from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import pytz
import calendar
from datetime import datetime, date, timedelta
from .models import TimeRecord
from .services import WorkTimeService
from .services.paid_leave_calculator import PaidLeaveCalculator
from .services.paid_leave_balance_manager import PaidLeaveBalanceManager

@login_required
def timeclock(request):
    jst = pytz.timezone('Asia/Tokyo')
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
    
    context = {
        'today_records': today_records,
        'available_actions': available_actions,
        'current_time': now_jst.strftime('%Y-%m-%d %H:%M:%S'),
        'last_record': last_record,
    }
    
    return render(request, 'timeclock/timeclock.html', context)

@login_required
@require_POST
def clock_action(request):
    action_type = request.POST.get('action_type')
    
    if not action_type:
        messages.error(request, '打刻タイプが指定されていません。')
        return redirect('timeclock')
    
    try:
        jst = pytz.timezone('Asia/Tokyo')
        timestamp = timezone.now().astimezone(jst)
        
        record = TimeRecord(
            user=request.user,
            clock_type=action_type,
            timestamp=timestamp
        )
        record.save()
        
        # 退勤時に労働時間と給与を計算して表示
        if action_type == 'clock_out':
            service = WorkTimeService(request.user)
            daily_summary = service.get_daily_summary()
            monthly_summary = service.get_monthly_summary()
            
            if daily_summary['error']:
                messages.warning(request, daily_summary['error'])
            else:
                work_time_str = service.format_timedelta(daily_summary['work_time'])
                
                message = f"退勤を打刻しました。\n"
                message += f"本日の労働時間: {work_time_str}"
                
                if daily_summary['wage'] > 0:
                    message += f"\n本日の給与: {daily_summary['wage']:,}円"
                
                # 目標月収に対する達成率を追加
                if monthly_summary['achievement_rate'] is not None:
                    message += f"\n目標月収達成率: {monthly_summary['achievement_rate']}%"
                    message += f"\n月収合計: {monthly_summary['total_wage']:,}円 / {monthly_summary['target_income']:,}円"
                
                messages.success(request, message, extra_tags='work_summary')
        else:
            messages.success(request, f'{record.get_clock_type_display()}を打刻しました。')
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e.messages[0]))
    except Exception as e:
        messages.error(request, '打刻に失敗しました。')
    
    return redirect('timeclock')

@login_required
def get_current_time(request):
    jst = pytz.timezone('Asia/Tokyo')
    now_jst = timezone.now().astimezone(jst)
    return JsonResponse({
        'time': now_jst.strftime('%H:%M:%S'),
        'date': now_jst.strftime('%Y年%m月%d日'),
        'datetime': now_jst.strftime('%Y-%m-%d %H:%M:%S')
    })

@login_required
def dashboard(request):
    """個人の勤務状況ダッシュボード"""
    jst = pytz.timezone('Asia/Tokyo')
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
    
    # 有給休暇情報を取得
    balance_manager = PaidLeaveBalanceManager(request.user)
    paid_leave_balance = balance_manager.get_current_balance()
    
    # 次回の有給付与予定を計算
    calculator = PaidLeaveCalculator(request.user)
    next_grant_info = None
    if hasattr(request.user, 'hire_date') and request.user.hire_date:
        # 次回の付与日を計算（現在の日付より後の最初の付与日を探す）
        grant_count = 1
        while grant_count <= 20:  # 安全のため20回まで
            grant_date = calculator.calculate_grant_date(grant_count)
            if grant_date > date.today():
                next_grant_info = {
                    'grant_date': grant_date,
                    'grant_count': grant_count,
                    'expected_days': calculator.determine_grant_days(grant_count, request.user.weekly_work_days)
                }
                break
            grant_count += 1
    
    context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'calendar_weeks': calendar_weeks,
        'monthly_summary': monthly_summary,
        'prev_month': prev_month,
        'next_month': next_month,
        'all_time_stats': all_time_stats,
        'weekdays': ['月', '火', '水', '木', '金', '土', '日'],
        'paid_leave_balance': paid_leave_balance,
        'next_grant_info': next_grant_info
    }
    
    return render(request, 'timeclock/dashboard.html', context)

def get_all_time_stats(user):
    """全期間の勤務統計を取得"""
    jst = pytz.timezone('Asia/Tokyo')
    
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