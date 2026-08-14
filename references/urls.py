from django.urls import path

from . import views

app_name = "references"

urlpatterns = [
    path("", views.home, name="home"),
    path("painel/", views.dashboard, name="dashboard"),
    path("projetos/", views.project_list, name="project_list"),
    path("projetos/novo/", views.project_create, name="project_create"),
    path("projetos/<uuid:pk>/", views.project_detail, name="project_detail"),
    path("projetos/<uuid:pk>/editar/", views.project_update, name="project_update"),
    path("projetos/<uuid:pk>/excluir/", views.project_delete, name="project_delete"),
    path("projetos/<uuid:pk>/importar/", views.import_sources, name="import_sources"),
    path("projetos/<uuid:pk>/adicionar/", views.add_existing, name="add_existing"),
    path("projetos/<uuid:pk>/gerar/", views.generate_list, name="generate_list"),
    path(
        "projetos/<uuid:pk>/exportar/<str:file_format>/",
        views.export_project,
        name="export_project",
    ),
    path(
        "projetos/<uuid:project_pk>/remover/<uuid:reference_pk>/",
        views.remove_from_project,
        name="remove_from_project",
    ),
    path("referencias/", views.reference_list, name="reference_list"),
    path("referencias/nova/", views.reference_create, name="reference_create"),
    path("referencias/<uuid:pk>/editar/", views.reference_edit, name="reference_edit"),
    path(
        "referencias/<uuid:pk>/excluir/",
        views.reference_delete,
        name="reference_delete",
    ),
    path("referencias/<uuid:pk>/arquivo/", views.reference_file, name="reference_file"),
]
