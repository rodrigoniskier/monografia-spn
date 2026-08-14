from django.contrib import admin

from .models import Project, ProjectReference, Reference


class ProjectReferenceInline(admin.TabularInline):
    model = ProjectReference
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "default_style", "updated_at")
    list_filter = ("default_style", "updated_at")
    search_fields = ("name", "owner__username", "owner__email")
    inlines = (ProjectReferenceInline,)


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "reference_type",
        "year",
        "source_kind",
        "extraction_status",
    )
    list_filter = ("reference_type", "source_kind", "extraction_status", "created_at")
    search_fields = ("title", "doi", "container_title", "owner__username")
    readonly_fields = ("normalized_fingerprint", "created_at", "updated_at")
