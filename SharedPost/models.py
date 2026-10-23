from django.db import models


class SharedPost(models.Model):
    food_item = models.ForeignKey('FoodItem.FoodItem', on_delete=models.CASCADE, related_name='shared_posts')
    location = models.ForeignKey('Location.Location', on_delete=models.PROTECT, related_name='shared_posts')
    description = models.CharField(max_length=1000)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['food_item'], condition=models.Q(is_active=True), name='one_active_post_per_food')]

    def __str__(self):
        return self.food_item.name

