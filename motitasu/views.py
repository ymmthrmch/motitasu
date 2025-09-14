from django.shortcuts import redirect


def home(request):
    """ホーム画面 - 伝言板へリダイレクト"""
    return redirect('bulletin_board:message_list')