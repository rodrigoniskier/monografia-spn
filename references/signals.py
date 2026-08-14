from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Reference


@receiver(post_delete, sender=Reference)
def delete_reference_file(sender, instance, **kwargs):
    if instance.source_file:
        instance.source_file.delete(save=False)
