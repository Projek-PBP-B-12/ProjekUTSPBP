from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",)

    whatsapp_number = models.CharField("nomor Whatsapp", max_length=15, blank=True, validators=[RegexValidator(regex=r"\A[1-9][0-9]{7,14}\Z", message="Example 628123456789, Without Space or +",)],)
    
    line_id = models.CharField("ID Line", max_length=100, blank=True)

    default_latitude = models.DecimalField("Default Latitude", max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90),MaxValueValidator(90)],)

    default_longitude = models.DecimalField("Default Longitude", max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180),MaxValueValidator(180)],)

    class Meta:
        verbose_name = "profil pengguna"
        verbose_name_plural = "profil pengguna"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(default_latitude__isnull=True, default_longitude__isnull=True)
                    | models.Q(default_latitude__isnull=False, default_longitude__isnull=False)
                ),
                name="profile_coordinates_pair",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(default_latitude__isnull=True)
                    | models.Q(default_latitude__gte=-90, default_latitude__lte=90)
                ),
                name="profile_latitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(default_longitude__isnull=True)
                    | models.Q(default_longitude__gte=-180, default_longitude__lte=180)
                ),
                name="profile_longitude_range",
            ),
        ]

    def clean(self):
        super().clean()
        if (self.default_latitude is None) != (self.default_longitude is None):
            raise ValidationError(
                "Lintang dan Bujur harus diisi bersama atau keduanya dikosongkan."
            )

    def __str__(self):
        return f"Profil {self.user.get_username()}"
