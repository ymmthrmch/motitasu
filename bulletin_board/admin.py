from django.contrib import admin
from .models import Message, Reaction

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_preview', 'is_pinned', 'pin_duration_hours', 'created_at')
    list_filter = ('created_at', 'user', 'is_pinned', 'pin_duration_hours')
    search_fields = ('content', 'user__name')
    readonly_fields = ('created_at', 'updated_at', 'pinned_at', 'pin_expires_at')
    actions = ['bulk_unpin_messages']
    
    def bulk_unpin_messages(self, request, queryset):
        """選択したメッセージのピン留めを一括解除"""
        count = 0
        for message in queryset.filter(is_pinned=True):
            message.unpin_message()
            count += 1
        self.message_user(request, f'{count}件のピン留めを解除しました。')
    bulk_unpin_messages.short_description = '選択したメッセージのピン留めを解除'
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'メッセージ内容'

@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_preview', 'get_emoji', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__name', 'message__content')
    
    def message_preview(self, obj):
        return obj.message.content[:30] + "..." if len(obj.message.content) > 30 else obj.message.content
    message_preview.short_description = 'メッセージ'