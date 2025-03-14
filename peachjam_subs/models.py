from django.contrib.auth.models import Group, User
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    group = models.OneToOneField(Group, on_delete=models.CASCADE, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.group:
            self.group, created = Group.objects.get_or_create(name=self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PricingPlan(models.Model):
    PERIODS = [("monthly", "Monthly"), ("annually", "Annually")]

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=50, choices=PERIODS)

    def __str__(self):
        return f"{self.name} - {self.period}"


class ProductOffering(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    pricing_plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("product", "pricing_plan")

    def __str__(self):
        return f"{self.product} - {self.pricing_plan}"


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product_offering = models.ForeignKey(ProductOffering, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Subscription<{self.user.username} - {self.product_offering}"
