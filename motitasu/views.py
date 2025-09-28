from django.shortcuts import redirect
from django.http import HttpResponse



def home(request):
    """ホーム画面 - 伝言板へリダイレクト"""
    return redirect('bulletin_board:message_list')