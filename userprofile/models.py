from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",)

    whatsapp_number = models.CharField("nomor Whatsapp", max_length=15, blank=True, validators=[RegexValidator(regex=r"\A[1-9][0-9]{7,14}\Z", message="Example 628123456789, Without Space or +",)],)
    
    line_id = models.CharField("ID Line", max_length=100, blank=True)

    default_location = models.ForeignKey(
        "Location.Location",
        verbose_name="Lokasi bawaan",
        on_delete=models.SET_NULL,
        related_name="default_for_profiles",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "profil pengguna"
        verbose_name_plural = "profil pengguna"

    def clean(self):
        super().clean()
        if self.default_location_id and self.user_id:
            location_model = self._meta.get_field("default_location").remote_field.model
            if location_model.objects.filter(pk=self.default_location_id).exclude(owner_id=self.user_id).exists():
                raise ValidationError({
                    "default_location": "Pilih lokasi yang tersimpan di akunmu sendiri."
                })

    def __str__(self):
        return f"Profil {self.user.get_username()}"
