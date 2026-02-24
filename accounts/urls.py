from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomPasswordResetView, CustomPasswordResetConfirmView
from . import views
from .views import CustomLoginView

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('approve/<int:profile_id>/', views.approve_member, name='approve_member'),
    path('pay/<int:member_id>/', views.initiate_payment, name='pay_member'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('search/', views.member_search, name='member_search'),
    path('message/<int:recipient_id>/', views.send_message, name='send_message'),
    path('pay/<int:member_id>/', views.initiate_payment, name='pay_member'),
    path('update-username/', views.update_username, name='update_username'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('payroll/history/', views.payroll_history, name='payroll_history'),
    path('upload-video/', views.upload_video, name='upload_video'),
    path('directory/', views.leader_directory, name='leader_directory'),
    path('receipt/<str:reference>/', views.payment_receipt, name='payment_receipt'),
    path('payroll/bulk/', views.bulk_payroll, name='bulk_payroll'),
    path('payroll/verify/', views.verify_payment, name='verify_payment'),
    path('payroll/export/', views.export_payroll_csv, name='export_payroll_csv'),
    path('member-detail/<int:member_id>/', views.member_detail, name='member_detail'),
    path('members/', views.members_list, name='members_list'),
    path('members/export/', views.export_members_excel, name='export_members_excel'),
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