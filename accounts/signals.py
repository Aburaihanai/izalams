from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Profile

@receiver(post_save, sender=Profile)
def notify_leader(sender, instance, created, **kwargs):
    if created:
        # Find the leader for the specific unit
        leader = Profile.objects.filter(unit=instance.unit, is_leader=True).first()
        if leader:
            send_mail(
                subject='New Member Awaiting Approval',
                message=f'Assalamu Alaikum, {instance.user.username} has registered for {instance.unit.name}. Please log in to approve.',
                from_email='admin@jibwis.org',
                recipient_list=[leader.user.email],
                fail_silently=True,
            )