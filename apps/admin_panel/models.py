# apps/admin_panel/models.py

from django.db import models

# ... tumhare baaki models ...

class AppVersion(models.Model):
    version = models.CharField(max_length=20, help_text="e.g. 1.0.5")
    is_force_update = models.BooleanField(default=False)
    apk_url = models.URLField(help_text="APK download link")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"v{self.version}"