from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
import logging

from .models import PaidLeaveRecord

logger = logging.getLogger(__name__)

@receiver(post_save, sender=PaidLeaveRecord)
def update_paid_leave_on_save(sender, instance, created, **kwargs):
    """PaidLeaveRecord作成時にcurrent_paid_leaveを更新"""
    if not created:
        return
    
    user = instance.user
    old_value = user.current_paid_leave
    
    try:
        with transaction.atomic():
            if instance.record_type == 'grant':
                user.current_paid_leave += instance.days
                logger.info(f"有給付与: {user.name} +{instance.days}日 ({old_value}→{user.current_paid_leave})")
                
            elif instance.record_type == 'use':
                user.current_paid_leave = max(0, user.current_paid_leave - instance.days)
                logger.info(f"有給使用: {user.name} -{instance.days}日 ({old_value}→{user.current_paid_leave})")
                
            elif instance.record_type == 'expire':
                user.current_paid_leave = max(0, user.current_paid_leave - instance.days)
                logger.info(f"有給時効: {user.name} -{instance.days}日 ({old_value}→{user.current_paid_leave})")
            
            user.save(update_fields=['current_paid_leave'])
            
    except Exception as e:
        logger.error(f"有給日数更新エラー: {user.name} - {e}")
        raise

@receiver(post_delete, sender=PaidLeaveRecord)
def update_paid_leave_on_delete(sender, instance, **kwargs):
    """PaidLeaveRecord削除時に巻き戻し"""
    user = instance.user
    old_value = user.current_paid_leave
    
    try:
        with transaction.atomic():
            if instance.record_type == 'grant':
                user.current_paid_leave = max(0, user.current_paid_leave - instance.days)
                logger.info(f"有給付与取消: {user.name} -{instance.days}日 ({old_value}→{user.current_paid_leave})")
                
            elif instance.record_type == 'use':
                user.current_paid_leave += instance.days
                logger.info(f"有給使用取消: {user.name} +{instance.days}日 ({old_value}→{user.current_paid_leave})")
                
            elif instance.record_type == 'expire':
                user.current_paid_leave += instance.days
                logger.info(f"有給時効取消: {user.name} +{instance.days}日 ({old_value}→{user.current_paid_leave})")
            
            user.save(update_fields=['current_paid_leave'])
            
    except Exception as e:
        logger.error(f"有給日数巻き戻しエラー: {user.name} - {e}")
        raise