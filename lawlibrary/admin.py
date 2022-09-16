from django.contrib import admin

from peachjam.models import Article, UserProfile


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    pass


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    pass
