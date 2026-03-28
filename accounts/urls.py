from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomPasswordResetView, CustomPasswordResetConfirmView
from . import views
from .views import CustomLoginView
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', views.landing, name='landing'),
    path('admin-langing/page', views.admin_landing_page, name='admin_landing'),
    path('ulama-langing/page', views.ulama_landing_page, name='ulama_landing'),
    path('fag-langing/page', views.fag_landing_page, name='fag_landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('approve-member/<int:profile_id>/', views.approve_member, name='approve_member'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('search/', views.member_search, name='member_search'),
    path('members/list/', views.members_list, name='members_list'),
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
    path('members/export/', views.export_members_excel, name='export_members_excel'),
    path('messages/send/', views.message_view, name='message_view'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('report/submit/<int:committee_id>/', views.submit_report, name='submit_report'),
    path('disciplinary/admin/', views.disciplinary_admin, name='disciplinary_admin'),
    path('members/bulk-message/', views.bulk_message_send, name='bulk_message_send'),
    path('bulk-voice/', views.bulk_voice_send, name='bulk_voice_send'),
    path('members/list/', views.members_list, name='members_list'),
    path('members/toggle/<int:member_id>/', views.toggle_member_status, name='toggle_member_status'),
    path('members/delete-permanent/<int:user_id>/', views.delete_member_permanent, name='delete_member_permanent'),
    path('dashboard/payroll/history/', views.payroll_history, name='payroll_history'),
    path('verify-account-ajax/', views.verify_account_ajax, name='verify_account_ajax'),
    path('video/<int:video_id>/', views.video_detail, name='video_detail'),
    path('inbox/', views.inbox, name='inbox'),
    path('sent/', views.sent_messages, name='sent_messages'),
    path('message/toggle/<int:message_id>/', views.mark_message_read_ajax, name='mark_read_ajax'),
    path('message/delete/<int:message_id>/', views.delete_message, name='delete_message'),
    path('message/reply/<int:message_id>/', views.leader_reply, name='leader_reply'),
    path('ajax/load-lgas/', views.load_lgas, name='ajax_load_lgas'),
    path('ajax/load-wards/', views.load_wards, name='ajax_load_wards'),
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico')),
    path('broadcast/send/', views.bulk_message_send, name='bulk_message_send'),
    path('voice/send/', views.bulk_voice_send, name='bulk_voice_send'),
    path('committee/<int:pk>/join/', views.join_committee, name='join_committee'),
    path('committee/<int:pk>/leave/', views.leave_committee, name='leave_committee'),
    path('announcement/create/', views.create_announcement, name='create_announcement'),
    path('announcement/delete/<int:pk>/', views.delete_announcement, name='delete_announcement'),
    path('gallery/', views.gallery_list, name='gallery_list'),
    path('gallery/upload/', views.upload_gallery_image, name='upload_gallery_image'),
    path('gallery/delete/<int:pk>/', views.delete_gallery_image, name='delete_gallery_image'),
    path('committee/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('committee/delete/<int:pk>/', views.delete_committee, name='delete_committee'),
    path('announcement/edit/<int:pk>/', views.edit_announcement, name='edit_announcement'),
    
    # Chat and Feed
    path('chat/delete/<int:chat_id>/', views.delete_chat_message, name='delete_chat_message'),
    path('chat/clear/', views.clear_unit_chat, name='clear_unit_chat'),
    path('send-to-leader/', views.send_to_leader, name='send_to_leader'),
    path('committee/create/', views.create_committee, name='create_committee'),
    path('committee/<int:pk>/', views.committee_detail, name='committee_detail'),
    path('committees/', views.committee_list, name='committee_list'),
    path('committee/<int:committee_pk>/upload-report/', 
         views.upload_committee_report, 
         name='upload_committee_report'),
    
    path('groupchat/create/', views.create_groupchat, name='create_groupchat'),
    path('groupchat/<int:pk>/', views.groupchat_detail, name='groupchat_detail'),
    path('groupchats/', views.groupchat_list, name='groupchat_list'),
    path('groupchat/<int:pk>/join/', views.join_groupchat, name='join_groupchat'),
    path('groupchat/<int:pk>/leave/', views.leave_groupchat, name='leave_groupchat'),
    path('groupchat/delete/<int:pk>/', views.delete_groupchat, name='delete_groupchat'),
    path('groupchat/<int:pk>/comment/', views.add_g_comment, name='add_g_comment'),

    # MASJID MODULE
    path('masjids/', views.masjid_list, name='masjid_list'),
    path('masjids/create/', views.create_masjid, name='create_masjid'),
    
    # SCHOOL MODULE
    path('schools/', views.school_dashboard, name='school_dashboard'),
    path('schools/create/', views.create_school, name='create_school'),
    path('schools/', views.school_list, name='school_list'),
    
    # HOSPITAL MODULE
    path('hospitals/', views.hospital_list, name='hospital_list'),
    path('hospitals/create/', views.create_hospital, name='create_hospital'),
    path('forgot-username/', views.forgot_username, name='forgot_username'),

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