from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

# Create your models here.

FOOD_CATEGORIES = [
    ("FRUIT", "Fruit"),
    ("VEGETABLE", "Vegetable"),
    ("MEAT", "Meat"),
    ("SEAFOOD", "Seafood"),
    ("DAIRY", "Dairy"),
    ("GRAIN", "Grain"),
    ("BEVERAGE", "Beverage"),
    ("SNACK", "Snack"),
    ("OTHER", "Other"),
]

FOOD_STATUSES = [
    ("STORED", "Stored"),
    ("CONSUMED", "Consumed"),
    ("OFFERED", "Offered to public"),
]

class FoodItem(models.Model):

    # Primary keynya pake BigAutoField aja ;)
    id = models.BigAutoField(primary_key=True, editable=False)

    # related_name biar bisa mengakses FoodItem berdasarkan usernya seperti user.food_items.all()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="food_items")
    
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=FOOD_CATEGORIES, default="OTHER")
    purchase_date = models.DateField(blank=True)
    expiration_date = models.DateField(blank=True)
    status = models.CharField(max_length=10, choices=FOOD_STATUSES, default="STORED")
    image_url = models.URLField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # @property artinya gak perlu pake function untuk mengakses. Jadi seolah-olah seperti atribut.
    # Untuk mengakses tinggal fooditem.days_until_expiration
    @property
    def days_until_expiration(self):
        return (self.expiration_date - timezone.localdate()).days

    @property
    def is_expired(self):
        return self.expiration_date < timezone.localdate()

    @property
    def expiration_state(self):
        if self.status == "CONSUMED":
            return "CONSUMED"
        if self.is_expired:
            return "EXPIRED"
        if self.days_until_expiration == 0:
            return "EXPIRES_TODAY"
        return "FRESH"

    class Meta:
        # Sortir berdasarkan tanggal kedaluwarsa dulu.
        ordering = ["expiration_date", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.expiration_date < self.purchase_date:
            raise ValidationError("Expiration date cannot be before purchase date.")
