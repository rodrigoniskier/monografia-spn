from django.urls import path

from . import views


app_name = "works"

urlpatterns = [
    path("", views.home, name="home"),
    path("criar-conta/", views.register, name="register"),
    path("boas-vindas/", views.onboarding, name="onboarding"),
    path("painel/", views.dashboard, name="dashboard"),
    path("monografias/nova/", views.create_monograph, name="create_monograph"),
    path("monografias/<int:pk>/excluir/", views.delete_monograph, name="delete_monograph"),
    path("monografias/<int:pk>/<slug:part_slug>/", views.workspace, name="workspace"),
    path("api/monografias/<int:pk>/salvar/", views.autosave, name="autosave"),
    path("api/monografias/<int:pk>/secoes/", views.add_section, name="add_section"),
    path("api/monografias/<int:pk>/secoes/<int:section_id>/", views.update_section, name="update_section"),
    path("api/monografias/<int:pk>/secoes/<int:section_id>/excluir/", views.delete_section, name="delete_section"),
    path("api/monografias/<int:pk>/ia/revisar/", views.ai_review, name="ai_review"),
    path("api/monografias/<int:pk>/ia/<int:revision_id>/aceitar/", views.accept_revision, name="accept_revision"),
    path("api/monografias/<int:pk>/pesquisar/", views.research_search, name="research_search"),
    path("api/monografias/<int:pk>/referencias/salvar/", views.save_publication, name="save_publication"),
    path("api/monografias/<int:pk>/referencias/<int:publication_id>/excluir/", views.delete_publication, name="delete_publication"),
    path("monografias/<int:pk>/exportar/docx/", views.export_docx, name="export_docx"),
]

