from django.contrib import admin

from .models import (
    AIRevision,
    CitationNote,
    Monograph,
    Profile,
    Publication,
    ReferenceEntry,
    Section,
)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


class PublicationInline(admin.TabularInline):
    model = Publication
    extra = 0
    readonly_fields = ("verified_at",)


class ReferenceEntryInline(admin.TabularInline):
    model = ReferenceEntry
    extra = 0


class CitationNoteInline(admin.TabularInline):
    model = CitationNote
    extra = 0
    readonly_fields = ("marker", "created_at", "updated_at")


@admin.register(Monograph)
class MonographAdmin(admin.ModelAdmin):
    list_display = ("display_title", "author_name", "owner", "status", "updated_at")
    list_filter = ("status", "year")
    search_fields = ("title", "author_name", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = (SectionInline, PublicationInline, ReferenceEntryInline, CitationNoteInline)


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


@admin.register(ReferenceEntry)
class ReferenceEntryAdmin(admin.ModelAdmin):
    list_display = ("monograph", "source_filename", "order", "updated_at")
    search_fields = ("monograph__title", "text", "source_filename")
    readonly_fields = ("checksum", "created_at", "updated_at")


@admin.register(CitationNote)
class CitationNoteAdmin(admin.ModelAdmin):
    list_display = ("monograph", "sequence", "target_key", "updated_at")
    list_filter = ("target_key",)
    search_fields = ("monograph__title", "reference_text", "marker")
    readonly_fields = ("marker", "created_at", "updated_at")
