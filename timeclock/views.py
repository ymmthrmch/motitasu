from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import pytz
from .models import TimeRecord

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