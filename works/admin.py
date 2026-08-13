from django.contrib import admin

from .models import AIRevision, Monograph, Profile, Publication, Section


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


class PublicationInline(admin.TabularInline):
    model = Publication
    extra = 0
    readonly_fields = ("verified_at",)


@admin.register(Monograph)
class MonographAdmin(admin.ModelAdmin):
    list_display = ("display_title", "author_name", "owner", "status", "updated_at")
    list_filter = ("status", "year")
    search_fields = ("title", "author_name", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = (SectionInline, PublicationInline)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "onboarding_seen", "updated_at")
    search_fields = ("full_name", "user__username", "user__email")


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "year", "provider", "verified_at")
    list_filter = ("source_type", "provider")
    search_fields = ("title", "doi", "isbn")


@admin.register(AIRevision)
class AIRevisionAdmin(admin.ModelAdmin):
    list_display = ("monograph", "target_key", "action", "model_name", "accepted", "created_at")
    list_filter = ("action", "accepted", "model_name")
    search_fields = ("monograph__title", "target_key")
    readonly_fields = ("created_at",)

