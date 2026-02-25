from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomPasswordResetView, CustomPasswordResetConfirmView
from . import views
from .views import CustomLoginView

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('approve-member/<int:profile_id>/', views.approve_member, name='approve_member'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('search/', views.member_search, name='member_search'),
    path('message/<int:recipient_id>/', views.send_message, name='send_message'),
    path('update-username/', views.update_username, name='update_username'),
    path('payroll/history/', views.payroll_history, name='payroll_history'),
    path('upload-video/', views.upload_video, name='upload_video'),
    path('directory/', views.leader_directory, name='leader_directory'),
    path('dashboard/payroll/', views.bulk_payroll_page, name='bulk_payroll'),
    path('dashboard/payroll/process/', views.process_payroll, name='process_payroll'),
    path('payroll/verify/', views.verify_payment, name='verify_payment'),
    path('payroll/export/', views.export_payroll_csv, name='export_payroll_csv'),
    path('member-detail/<int:member_id>/', views.member_detail, name='member_detail'),
    path('members/', views.members_list, name='members_list'),
    path('members/export/', views.export_members_excel, name='export_members_excel'),
    path('messages/send/', views.message_view, name='message_view'),
    path('messages/read/<int:message_id>/', views.mark_as_read, name='mark_as_read'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('report/submit/', views.submit_report, name='submit_report'),
    path('disciplinary/admin/', views.disciplinary_admin, name='disciplinary_admin'),
    path('members/bulk-message/', views.bulk_message_send, name='bulk_message_send'),
    path('members/toggle/<int:member_id>/', views.toggle_member_status, name='toggle_member_status'),
    path('members/delete-permanent/<int:user_id>/', views.delete_member_permanent, name='delete_member_permanent'),
    path('dashboard/payroll/history/', views.payroll_history, name='payroll_history'),
    path('verify-account-ajax/', views.verify_account_ajax, name='verify_account_ajax'),
    path('video/<int:video_id>/', views.video_detail, name='video_detail'),
    path('inbox/', views.inbox, name='inbox'),
    path('delete/message/<int:msg_id>/', views.delete_message, name='delete_message'),

    path('password-reset/',
         CustomPasswordResetView.as_view(template_name='password_reset.html'),
         name='password_reset'),

    # 2. Email sent success page
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),

    # 3. The link from the email (THIS WAS MISSING)
    path('password-reset-confirm/<uidb64>/<token>/',
         CustomPasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),

    # 4. Password successfully changed page
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name='password_reset_complete'),
]