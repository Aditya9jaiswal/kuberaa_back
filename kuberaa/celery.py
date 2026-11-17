import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')

app = Celery('kuberaa')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Schedule — every minute check for room releases
app.conf.beat_schedule = {
    'check-room-releases': {
        'task': 'apps.matches.tasks.check_room_releases',
        'schedule': 60.0,  # every 60 seconds
    },
}